"""Rich analytics enrichment for sprint-snitch.

Pure computation module — no I/O, no subprocess calls. Takes already-parsed
data structures and computes file-type breakdowns, commit categorization,
daily activity timelines, change-type statistics, and file churn metrics.
"""

from __future__ import annotations

import os
import re
from collections import Counter
from datetime import datetime, timedelta

from sprint_snitch.models.data import (
    ChangeTypeStats,
    ChurnedFile,
    CommitCategory,
    CommitInfo,
    DailyActivity,
    FileTypeBreakdown,
    RepoAnalysis,
)

# ---------------------------------------------------------------------------
# File extension → language/category mapping
# ---------------------------------------------------------------------------

EXTENSION_MAP: dict[str, str] = {
    # Languages
    ".py": "Python",
    ".pyi": "Python",
    ".js": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".ts": "TypeScript",
    ".jsx": "JavaScript (JSX)",
    ".tsx": "TypeScript (TSX)",
    ".java": "Java",
    ".cs": "C#",
    ".cpp": "C++",
    ".cc": "C++",
    ".c": "C",
    ".h": "C/C++ Header",
    ".hpp": "C++ Header",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".scala": "Scala",
    ".r": "R",
    ".m": "MATLAB",
    ".lua": "Lua",
    ".sh": "Shell",
    ".bash": "Shell",
    ".ps1": "PowerShell",
    ".bat": "Batch",
    # Web / markup
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sass": "SASS",
    ".less": "LESS",
    ".vue": "Vue",
    ".svelte": "Svelte",
    # Data / config
    ".json": "JSON",
    ".xml": "XML",
    ".yml": "Configuration",
    ".yaml": "Configuration",
    ".toml": "Configuration",
    ".ini": "Configuration",
    ".cfg": "Configuration",
    ".env": "Configuration",
    ".properties": "Configuration",
    # Documentation
    ".md": "Documentation",
    ".rst": "Documentation",
    ".txt": "Documentation",
    ".adoc": "Documentation",
    # Build / CI
    ".tf": "Terraform",
    ".hcl": "Terraform",
    # SQL
    ".sql": "SQL",
    # Other
    ".proto": "Protobuf",
    ".graphql": "GraphQL",
    ".ipynb": "Jupyter Notebook",
}

# Filename-based detection for extensionless files
_FILENAME_MAP: dict[str, str] = {
    "dockerfile": "Docker",
    "makefile": "Build",
    "cmakelists.txt": "Build",
    "rakefile": "Build",
    "gemfile": "Ruby",
    "vagrantfile": "Configuration",
    ".gitignore": "Configuration",
    ".dockerignore": "Docker",
    ".editorconfig": "Configuration",
}


# ---------------------------------------------------------------------------
# Conventional commit classification
# ---------------------------------------------------------------------------

_CONVENTIONAL_RE = re.compile(
    r"^(feat|fix|refactor|docs|test|tests|chore|ci|style|perf|build|revert)"
    r"(?:\(.+?\))?!?:\s",
    re.IGNORECASE,
)

_KEYWORD_HEURISTICS: list[tuple[str, list[str]]] = [
    ("fix", ["fix", "bug", "patch", "hotfix", "resolve", "issue"]),
    ("feat", ["add", "feature", "new", "implement", "introduce"]),
    ("refactor", ["refactor", "restructure", "reorganize", "simplify", "clean"]),
    ("docs", ["doc", "readme", "comment", "changelog"]),
    ("test", ["test", "spec", "coverage"]),
    ("chore", ["chore", "update", "upgrade", "bump", "dependency", "deps"]),
    ("style", ["format", "lint", "style", "whitespace"]),
    ("perf", ["perf", "performance", "optimize", "speed"]),
    ("ci", ["ci", "pipeline", "workflow", "github action", "deploy"]),
    ("cleanup", ["remove", "delete", "drop", "deprecate", "clean up"]),
]

# Normalize some categories
_CATEGORY_ALIASES: dict[str, str] = {
    "tests": "test",
    "build": "chore",
    "revert": "fix",
}


# ---------------------------------------------------------------------------
# File type classification
# ---------------------------------------------------------------------------


def classify_file_type(file_path: str) -> tuple[str, str]:
    """Determine the language/category and extension from a file path.

    Returns
    -------
    tuple[str, str]
        (file_type_name, extension). Falls back to ("Other", ext) for
        unknown extensions, or ("Other", "") for extensionless files.
    """
    basename = os.path.basename(file_path).lower()

    # Check filename-based map first (Dockerfile, Makefile, etc.)
    if basename in _FILENAME_MAP:
        _, ext = os.path.splitext(file_path)
        return _FILENAME_MAP[basename], ext.lower()

    _, ext = os.path.splitext(file_path)
    ext_lower = ext.lower()

    if ext_lower in EXTENSION_MAP:
        return EXTENSION_MAP[ext_lower], ext_lower

    return "Other", ext_lower if ext_lower else ""


def compute_file_type_breakdown(
    commits: list[CommitInfo],
) -> list[FileTypeBreakdown]:
    """Aggregate lines added/removed and commit counts by file type.

    Returns list sorted descending by total lines changed.
    """
    # Track per-type stats
    stats: dict[str, dict] = {}  # file_type -> {ext, files, added, removed, commit_shas}

    for commit in commits:
        for fc in commit.files:
            ft, ext = classify_file_type(fc.path)
            if ft not in stats:
                stats[ft] = {
                    "ext": ext,
                    "files": set(),
                    "added": 0,
                    "removed": 0,
                    "commit_shas": set(),
                }
            s = stats[ft]
            s["files"].add(fc.path)
            s["added"] += fc.lines_added
            s["removed"] += fc.lines_removed
            s["commit_shas"].add(commit.sha)

    result = []
    for ft, s in stats.items():
        result.append(FileTypeBreakdown(
            file_type=ft,
            extension=s["ext"],
            file_count=len(s["files"]),
            lines_added=s["added"],
            lines_removed=s["removed"],
            commit_count=len(s["commit_shas"]),
        ))

    result.sort(key=lambda b: b.lines_added + b.lines_removed, reverse=True)
    return result


# ---------------------------------------------------------------------------
# Commit classification
# ---------------------------------------------------------------------------


def classify_commit(message: str) -> str:
    """Classify a commit message into a conventional commit category.

    Tries conventional commit prefix first (e.g. "feat: ..." or "fix(scope): ...").
    Falls back to keyword heuristic matching on the full message.
    Returns "other" if no match.
    """
    # Try conventional prefix
    m = _CONVENTIONAL_RE.match(message)
    if m:
        cat = m.group(1).lower()
        return _CATEGORY_ALIASES.get(cat, cat)

    # Keyword fallback
    lower = message.lower()
    for category, keywords in _KEYWORD_HEURISTICS:
        for kw in keywords:
            if kw in lower:
                return category

    return "other"


def compute_commit_categories(
    commits: list[CommitInfo],
) -> list[CommitCategory]:
    """Aggregate commits by classified category.

    Also sets each commit's ``category`` field in-place.

    Returns list sorted descending by count.
    """
    counts: Counter[str] = Counter()
    for commit in commits:
        cat = classify_commit(commit.message)
        commit.category = cat
        counts[cat] += 1

    result = [CommitCategory(category=cat, count=n) for cat, n in counts.items()]
    result.sort(key=lambda c: c.count, reverse=True)
    return result


# ---------------------------------------------------------------------------
# Time-based metrics
# ---------------------------------------------------------------------------


def compute_daily_activity(
    commits: list[CommitInfo],
    date_from: datetime,
    date_to: datetime,
) -> list[DailyActivity]:
    """Compute per-day commit frequency across the full date range.

    Produces an entry for every day in [date_from, date_to], even days
    with zero commits.
    """
    # Build a day-keyed dict covering the full range
    start = date_from.date() if hasattr(date_from, "date") else date_from
    end = date_to.date() if hasattr(date_to, "date") else date_to

    days: dict[object, DailyActivity] = {}
    current = start
    while current <= end:
        days[current] = DailyActivity(
            date=datetime(current.year, current.month, current.day),
        )
        current += timedelta(days=1)

    # Bin commits
    for commit in commits:
        day = commit.timestamp.date() if hasattr(commit.timestamp, "date") else commit.timestamp
        if day in days:
            da = days[day]
            da.commit_count += 1
            da.lines_added += commit.lines_added
            da.lines_removed += commit.lines_removed
            if commit.author_email not in da.authors:
                da.authors.append(commit.author_email)

    return sorted(days.values(), key=lambda d: d.date)


def identify_peak_day(daily_activity: list[DailyActivity]) -> DailyActivity | None:
    """Return the DailyActivity with the highest commit count."""
    if not daily_activity:
        return None
    return max(daily_activity, key=lambda d: d.commit_count)


def compute_weekday_weekend_split(commits: list[CommitInfo]) -> tuple[int, int]:
    """Count commits on weekdays vs weekends.

    Returns (weekday_count, weekend_count). Monday-Friday = weekday.
    """
    weekday = 0
    weekend = 0
    for commit in commits:
        if commit.timestamp.weekday() < 5:
            weekday += 1
        else:
            weekend += 1
    return weekday, weekend


# ---------------------------------------------------------------------------
# Change type statistics
# ---------------------------------------------------------------------------


def compute_change_type_stats(commits: list[CommitInfo]) -> ChangeTypeStats:
    """Count files by change type across all commits."""
    stats = ChangeTypeStats()
    for commit in commits:
        for fc in commit.files:
            ct = fc.change_type.lower()
            if ct == "added":
                stats.files_added += 1
            elif ct == "modified":
                stats.files_modified += 1
            elif ct == "deleted":
                stats.files_deleted += 1
            elif ct == "renamed":
                stats.files_renamed += 1
    return stats


def compute_churned_files(
    commits: list[CommitInfo],
    min_changes: int = 2,
    top_n: int = 10,
) -> list[ChurnedFile]:
    """Identify files modified across multiple commits.

    Returns top_n files sorted descending by change_count, filtered
    to those with at least min_changes modifications.
    """
    churn: dict[str, ChurnedFile] = {}
    for commit in commits:
        for fc in commit.files:
            if fc.path not in churn:
                churn[fc.path] = ChurnedFile(path=fc.path)
            cf = churn[fc.path]
            cf.change_count += 1
            cf.total_lines_added += fc.lines_added
            cf.total_lines_removed += fc.lines_removed

    result = [cf for cf in churn.values() if cf.change_count >= min_changes]
    result.sort(key=lambda c: c.change_count, reverse=True)
    return result[:top_n]


# ---------------------------------------------------------------------------
# Per-author enrichment helpers
# ---------------------------------------------------------------------------


def compute_author_file_type_breakdown(author_commits: list[CommitInfo]) -> list[FileTypeBreakdown]:
    """Compute file type breakdown for a single author's commits."""
    return compute_file_type_breakdown(author_commits)


def compute_author_commit_categories(author_commits: list[CommitInfo]) -> list[CommitCategory]:
    """Compute commit category distribution for a single author.

    Assumes commit.category has already been populated by
    compute_commit_categories on the full commit list.
    """
    counts: Counter[str] = Counter()
    for c in author_commits:
        cat = c.category or "other"
        counts[cat] += 1
    result = [CommitCategory(category=cat, count=n) for cat, n in counts.items()]
    result.sort(key=lambda c: c.count, reverse=True)
    return result


def compute_author_daily_activity(
    author_commits: list[CommitInfo],
    date_from: datetime,
    date_to: datetime,
) -> list[DailyActivity]:
    """Compute daily activity for a single author."""
    return compute_daily_activity(author_commits, date_from, date_to)


def compute_author_change_type_stats(author_commits: list[CommitInfo]) -> ChangeTypeStats:
    """Compute change type breakdown for a single author's commits."""
    return compute_change_type_stats(author_commits)


# ---------------------------------------------------------------------------
# Merge helpers (for cross-repo contributor merging)
# ---------------------------------------------------------------------------


def merge_file_type_breakdowns(
    a: list[FileTypeBreakdown], b: list[FileTypeBreakdown],
) -> list[FileTypeBreakdown]:
    """Merge two file type breakdown lists by summing matching types."""
    merged: dict[str, FileTypeBreakdown] = {}
    for item in a:
        merged[item.file_type] = FileTypeBreakdown(
            file_type=item.file_type, extension=item.extension,
            file_count=item.file_count, lines_added=item.lines_added,
            lines_removed=item.lines_removed, commit_count=item.commit_count,
        )
    for item in b:
        if item.file_type in merged:
            m = merged[item.file_type]
            m.file_count += item.file_count
            m.lines_added += item.lines_added
            m.lines_removed += item.lines_removed
            m.commit_count += item.commit_count
        else:
            merged[item.file_type] = FileTypeBreakdown(
                file_type=item.file_type, extension=item.extension,
                file_count=item.file_count, lines_added=item.lines_added,
                lines_removed=item.lines_removed, commit_count=item.commit_count,
            )
    result = list(merged.values())
    result.sort(key=lambda x: x.lines_added + x.lines_removed, reverse=True)
    return result


def merge_commit_categories(
    a: list[CommitCategory], b: list[CommitCategory],
) -> list[CommitCategory]:
    """Merge two commit category lists by summing matching categories."""
    counts: dict[str, int] = {}
    for item in a:
        counts[item.category] = counts.get(item.category, 0) + item.count
    for item in b:
        counts[item.category] = counts.get(item.category, 0) + item.count
    result = [CommitCategory(category=cat, count=n) for cat, n in counts.items()]
    result.sort(key=lambda c: c.count, reverse=True)
    return result


def merge_daily_activity(
    a: list[DailyActivity], b: list[DailyActivity],
) -> list[DailyActivity]:
    """Merge two daily activity lists by summing matching dates."""
    by_date: dict[datetime, DailyActivity] = {}
    for item in a:
        by_date[item.date] = DailyActivity(
            date=item.date, commit_count=item.commit_count,
            lines_added=item.lines_added, lines_removed=item.lines_removed,
            authors=list(item.authors),
        )
    for item in b:
        if item.date in by_date:
            m = by_date[item.date]
            m.commit_count += item.commit_count
            m.lines_added += item.lines_added
            m.lines_removed += item.lines_removed
            for author in item.authors:
                if author not in m.authors:
                    m.authors.append(author)
        else:
            by_date[item.date] = DailyActivity(
                date=item.date, commit_count=item.commit_count,
                lines_added=item.lines_added, lines_removed=item.lines_removed,
                authors=list(item.authors),
            )
    return sorted(by_date.values(), key=lambda d: d.date)


def merge_change_type_stats(a: ChangeTypeStats, b: ChangeTypeStats) -> ChangeTypeStats:
    """Sum two ChangeTypeStats."""
    return ChangeTypeStats(
        files_added=a.files_added + b.files_added,
        files_modified=a.files_modified + b.files_modified,
        files_deleted=a.files_deleted + b.files_deleted,
        files_renamed=a.files_renamed + b.files_renamed,
    )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def enrich_repo_analysis(analysis: RepoAnalysis) -> None:
    """Enrich a RepoAnalysis in-place with all analytics.

    Populates file type breakdowns, commit categories, daily activity,
    change type stats, churned files, peak day, and weekend/weekday
    splits — both at repo level and per-author.
    """
    # 1. Classify all commits (sets commit.category in-place)
    analysis.commit_categories = compute_commit_categories(analysis.commits)

    # 2. File type breakdown
    analysis.file_type_breakdown = compute_file_type_breakdown(analysis.commits)

    # 3. Daily activity + peak day
    analysis.daily_activity = compute_daily_activity(
        analysis.commits, analysis.date_from, analysis.date_to,
    )
    analysis.peak_day = identify_peak_day(analysis.daily_activity)

    # 4. Weekday/weekend split
    analysis.weekday_commits, analysis.weekend_commits = compute_weekday_weekend_split(
        analysis.commits,
    )

    # 5. Change type stats
    analysis.change_type_stats = compute_change_type_stats(analysis.commits)

    # 6. Churned files
    analysis.churned_files = compute_churned_files(analysis.commits)

    # 7. Per-author enrichment
    for _email, author in analysis.authors.items():
        author.file_type_breakdown = compute_author_file_type_breakdown(author.commits)
        author.commit_categories = compute_author_commit_categories(author.commits)
        author.daily_activity = compute_author_daily_activity(
            author.commits, analysis.date_from, analysis.date_to,
        )
        author.change_type_stats = compute_author_change_type_stats(author.commits)
