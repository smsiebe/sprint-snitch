"""Repository cloning and fetching via git CLI."""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path


class GitError(Exception):
    """Raised when a git subprocess fails."""

    def __init__(self, message: str, returncode: int = 1, stderr: str = "") -> None:
        self.message = message
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(message)


def clone_or_fetch(repo_url: str, work_dir: str | None = None) -> Path:
    """Clone a repository, or fetch updates if it already exists locally.

    Parameters
    ----------
    repo_url:
        Remote git URL (HTTPS or SSH).
    work_dir:
        Parent directory for the local clone.  A temp directory is created
        when *None*.

    Returns
    -------
    Path
        Absolute path to the local repository directory.

    Raises
    ------
    GitError
        If any git subprocess exits with a non-zero return code.
    """
    if work_dir is None:
        work_dir = tempfile.mkdtemp(prefix="sprint_snitch_")

    work_path = Path(work_dir)
    repo_dir_name = _repo_dir_name(repo_url)
    repo_path = work_path / repo_dir_name

    if repo_path.exists() and (repo_path / ".git").is_dir():
        # Repository already cloned — fetch latest changes.
        result = subprocess.run(
            ["git", "fetch", "--all"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise GitError(
                message=f"git fetch failed for {repo_url}: {result.stderr.strip()}",
                returncode=result.returncode,
                stderr=result.stderr,
            )
    else:
        # Fresh clone.
        result = subprocess.run(
            ["git", "clone", repo_url, str(repo_path)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise GitError(
                message=f"git clone failed for {repo_url}: {result.stderr.strip()}",
                returncode=result.returncode,
                stderr=result.stderr,
            )

    return repo_path


def _repo_dir_name(repo_url: str) -> str:
    """Derive a safe directory name from a git remote URL.

    Examples
    --------
    >>> _repo_dir_name("https://github.com/org/repo.git")
    'github.com_org_repo'
    >>> _repo_dir_name("git@github.com:org/repo.git")
    'github.com_org_repo'
    """
    name = repo_url

    # Strip common protocols.
    name = re.sub(r"^https?://", "", name)
    name = re.sub(r"^git@", "", name)

    # Strip trailing .git suffix.
    name = re.sub(r"\.git$", "", name)

    # Replace separators (: / and any other non-alphanumeric-dot-underscore-dash)
    # with underscores, then collapse consecutive underscores.
    name = re.sub(r"[/:]+", "_", name)
    name = re.sub(r"[^a-zA-Z0-9._\-]", "_", name)
    name = re.sub(r"_+", "_", name)
    name = name.strip("_")

    return name
