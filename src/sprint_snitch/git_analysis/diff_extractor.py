"""Commit extraction and diff parsing."""

from __future__ import annotations

import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from sprint_snitch.git_analysis.clone import GitError
from sprint_snitch.models.data import CommitInfo, FileChange

# The delimiter injected into --format so we can reliably split commits.
_COMMIT_SEP = "COMMIT_SEP"

# Maximum characters of file content to keep per file (for LLM context sizing).
_MAX_CONTENT_CHARS = 50_000


def extract_commits(
    repo_path: Path,
    date_from: datetime,
    date_to: datetime,
) -> list[CommitInfo]:
    """Extract parsed commits (with file contents) for a date range.

    Parameters
    ----------
    repo_path:
        Path to the local git repository.
    date_from / date_to:
        Inclusive date boundaries for the query.

    Returns
    -------
    list[CommitInfo]
        Fully enriched commits with file-level content.
    """
    after_str = date_from.date().isoformat()
    # --before is exclusive in git, so add one day to make date_to inclusive.
    before_str = (date_to.date() + timedelta(days=1)).isoformat()

    fmt = f"{_COMMIT_SEP}%nsha:%H%nauthor_name:%an%nauthor_email:%ae%ndate:%aI%nmessage:%s"

    result = subprocess.run(
        [
            "git", "log",
            f"--format={fmt}",
            "--numstat",
            f"--after={after_str}",
            f"--before={before_str}",
            "--all",
        ],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
        timeout=120,
        errors="replace",
    )

    if result.returncode != 0:
        raise GitError(
            message=f"git log failed: {result.stderr.strip()}",
            returncode=result.returncode,
            stderr=result.stderr,
        )

    commits = _parse_git_log(result.stdout)
    change_types = _get_change_type_map(repo_path, date_from, date_to)
    _apply_change_types(commits, change_types)
    _enrich_with_file_content(repo_path, commits)
    return commits


# ---------------------------------------------------------------------------
# Change type detection (--name-status)
# ---------------------------------------------------------------------------

_NAME_STATUS_MAP: dict[str, str] = {
    "A": "added",
    "M": "modified",
    "D": "deleted",
    "T": "modified",  # type change (e.g. file → symlink)
}


def _get_change_type_map(
    repo_path: Path,
    date_from: datetime,
    date_to: datetime,
) -> dict[tuple[str, str], str]:
    """Run ``git log --name-status`` to get the actual change type per file.

    Returns a mapping of ``(sha, filepath) -> change_type`` where change_type
    is one of ``"added"``, ``"modified"``, ``"deleted"``, ``"renamed"``.
    """
    after_str = date_from.date().isoformat()
    before_str = (date_to.date() + timedelta(days=1)).isoformat()

    fmt = f"{_COMMIT_SEP}%nsha:%H"

    result = subprocess.run(
        [
            "git", "log",
            f"--format={fmt}",
            "--name-status",
            f"--after={after_str}",
            f"--before={before_str}",
            "--all",
        ],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
        timeout=120,
        errors="replace",
    )

    if result.returncode != 0:
        return {}  # Graceful degradation — fall back to "modified" default

    return _parse_name_status_output(result.stdout)


def _parse_name_status_output(raw_output: str) -> dict[tuple[str, str], str]:
    """Parse ``git log --name-status`` output into a ``(sha, path) -> change_type`` map."""
    change_map: dict[tuple[str, str], str] = {}
    current_sha = ""

    blocks = raw_output.split(_COMMIT_SEP)
    for block in blocks:
        block = block.strip()
        if not block:
            continue

        current_sha = ""
        for line in block.splitlines():
            if line.startswith("sha:"):
                current_sha = line[4:]
                continue

            if not current_sha or not line.strip():
                continue

            parts = line.split("\t")
            if len(parts) < 2:
                continue

            status = parts[0]

            # Renames and copies: R### or C### followed by old_path \t new_path
            if status.startswith(("R", "C")):
                change_type = "renamed" if status.startswith("R") else "added"
                filepath = parts[2] if len(parts) >= 3 else parts[1]
            elif status in _NAME_STATUS_MAP:
                change_type = _NAME_STATUS_MAP[status]
                filepath = parts[1]
            else:
                continue

            change_map[(current_sha, filepath)] = change_type

    return change_map


def _apply_change_types(
    commits: list[CommitInfo],
    change_map: dict[tuple[str, str], str],
) -> None:
    """Apply change types from ``--name-status`` to parsed commits in-place."""
    for commit in commits:
        for fc in commit.files:
            key = (commit.sha, fc.path)
            if key in change_map:
                fc.change_type = change_map[key]


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_git_log(raw_output: str) -> list[CommitInfo]:
    """Split raw ``git log`` output into structured :class:`CommitInfo` objects."""
    blocks = raw_output.split(_COMMIT_SEP)
    commits: list[CommitInfo] = []

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        fields: dict[str, str] = {}
        numstat_lines: list[str] = []
        in_numstat = False

        for line in block.splitlines():
            # Once we start seeing numstat data (tab-separated numbers) or
            # a blank line after the header, switch modes.
            if not in_numstat:
                matched = False
                for key in ("sha", "author_name", "author_email", "date", "message"):
                    prefix = f"{key}:"
                    if line.startswith(prefix):
                        fields[key] = line[len(prefix):]
                        matched = True
                        break
                if not matched and line == "":
                    # Blank line separates header from numstat.
                    in_numstat = True
                elif not matched:
                    # Could be a numstat line immediately after header.
                    parsed = _parse_numstat_line(line)
                    if parsed is not None:
                        in_numstat = True
                        numstat_lines.append(line)
            else:
                if line.strip():
                    numstat_lines.append(line)

        # We need at least the sha to consider this a valid commit block.
        if "sha" not in fields:
            continue

        # Parse the ISO-8601 timestamp.
        try:
            timestamp = datetime.fromisoformat(fields.get("date", ""))
        except (ValueError, TypeError):
            timestamp = datetime.min

        # Build FileChange list from numstat lines.
        files: list[FileChange] = []
        for ns_line in numstat_lines:
            fc = _parse_numstat_line(ns_line)
            if fc is not None:
                files.append(fc)

        # Sum lines across files.
        total_added = sum(f.lines_added for f in files)
        total_removed = sum(f.lines_removed for f in files)

        commits.append(
            CommitInfo(
                sha=fields.get("sha", ""),
                author_name=fields.get("author_name", ""),
                author_email=fields.get("author_email", ""),
                message=fields.get("message", ""),
                timestamp=timestamp,
                files=files,
                lines_added=total_added,
                lines_removed=total_removed,
            )
        )

    return commits


def _parse_numstat_line(line: str) -> FileChange | None:
    """Parse a single ``--numstat`` line into a :class:`FileChange`.

    Handles three cases:

    1. Standard: ``<added>\\t<removed>\\t<filepath>``
    2. Binary:   ``-\\t-\\t<filepath>``
    3. Rename:   path contains ``{old => new}`` notation
    """
    line = line.strip()
    if not line:
        return None

    parts = line.split("\t", 2)
    if len(parts) < 3:
        return None

    added_str, removed_str, filepath = parts

    # Binary files are reported as "-\t-\t<path>".
    if added_str == "-" and removed_str == "-":
        lines_added = 0
        lines_removed = 0
    else:
        try:
            lines_added = int(added_str)
            lines_removed = int(removed_str)
        except ValueError:
            return None

    # Detect renames: e.g. "src/{old.py => new.py}" or "{old => new}/file.py".
    change_type = "modified"
    rename_match = re.search(r"\{(.+?) => (.+?)\}", filepath)
    if rename_match:
        change_type = "renamed"
        # Reconstruct the *new* path.
        prefix = filepath[: rename_match.start()]
        suffix = filepath[rename_match.end() :]
        new_part = rename_match.group(2)
        filepath = prefix + new_part + suffix
        # Clean up any double slashes.
        filepath = filepath.replace("//", "/")

    return FileChange(
        path=filepath,
        lines_added=lines_added,
        lines_removed=lines_removed,
        change_type=change_type,
    )


# ---------------------------------------------------------------------------
# Content enrichment
# ---------------------------------------------------------------------------

def _enrich_with_file_content(
    repo_path: Path,
    commits: list[CommitInfo],
) -> None:
    """Fetch file contents at each commit and attach to :class:`FileChange`.

    Modifies *commits* in-place.
    """
    for commit in commits:
        for file_change in commit.files:
            if file_change.change_type == "deleted":
                file_change.content = "(file deleted)"
                continue

            try:
                result = subprocess.run(
                    ["git", "show", f"{commit.sha}:{file_change.path}"],
                    cwd=str(repo_path),
                    capture_output=True,
                    text=True,
                    timeout=120,
                    errors="replace",
                )
                if result.returncode != 0:
                    file_change.content = "(binary file)"
                    continue

                content = result.stdout
                if len(content) > _MAX_CONTENT_CHARS:
                    content = (
                        content[:_MAX_CONTENT_CHARS]
                        + f"\n\n... (truncated at {_MAX_CONTENT_CHARS} characters)"
                    )
                file_change.content = content

            except (subprocess.TimeoutExpired, UnicodeDecodeError, OSError):
                file_change.content = "(binary file)"


# ---------------------------------------------------------------------------
# Raw diff output
# ---------------------------------------------------------------------------

def get_diff_text(
    repo_path: Path,
    date_from: datetime,
    date_to: datetime,
) -> str:
    """Return raw unified diff output for the given date range.

    Useful when the caller needs the full patch text (e.g. for an LLM
    prompt) rather than structured commit objects.
    """
    after_str = date_from.date().isoformat()
    before_str = (date_to.date() + timedelta(days=1)).isoformat()

    result = subprocess.run(
        [
            "git", "log",
            "-p",
            f"--after={after_str}",
            f"--before={before_str}",
            "--all",
        ],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
        timeout=120,
        errors="replace",
    )

    if result.returncode != 0:
        raise GitError(
            message=f"git log -p failed: {result.stderr.strip()}",
            returncode=result.returncode,
            stderr=result.stderr,
        )

    return result.stdout
