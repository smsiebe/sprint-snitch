"""Data models for sprint-snitch pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class FileChange:
    """A single file's change within a commit."""

    path: str
    lines_added: int
    lines_removed: int
    change_type: str  # "added", "modified", "deleted", "renamed"
    content: str = ""  # Full file content at this commit (for LLM context)


@dataclass
class FileTypeBreakdown:
    """Aggregated statistics for a single file type/language category."""

    file_type: str  # e.g. "Python", "JavaScript", "Documentation"
    extension: str  # e.g. ".py", ".js", ".md"
    file_count: int = 0
    lines_added: int = 0
    lines_removed: int = 0
    commit_count: int = 0


@dataclass
class CommitCategory:
    """Distribution count for a single commit category."""

    category: str  # e.g. "feat", "fix", "refactor", "docs", "other"
    count: int = 0


@dataclass
class DailyActivity:
    """Commit activity for a single day."""

    date: datetime
    commit_count: int = 0
    lines_added: int = 0
    lines_removed: int = 0
    authors: list[str] = field(default_factory=list)


@dataclass
class ChangeTypeStats:
    """Breakdown of file change types (added/modified/deleted/renamed)."""

    files_added: int = 0
    files_modified: int = 0
    files_deleted: int = 0
    files_renamed: int = 0


@dataclass
class ChurnedFile:
    """A file modified across multiple commits."""

    path: str
    change_count: int = 0
    total_lines_added: int = 0
    total_lines_removed: int = 0


@dataclass
class DiscoveredIdentity:
    """A unique (name, email) pair found across extracted commits."""

    name: str
    email: str
    commit_count: int = 0


@dataclass
class CommitInfo:
    """A single parsed git commit."""

    sha: str
    author_name: str
    author_email: str
    message: str
    timestamp: datetime
    files: list[FileChange] = field(default_factory=list)
    lines_added: int = 0
    lines_removed: int = 0
    category: str = ""  # Conventional commit category (populated by enrichment)


@dataclass
class AuthorMetrics:
    """Aggregated metrics for one contributor within a repo."""

    name: str
    email: str
    lines_added: int = 0
    lines_removed: int = 0
    commits: list[CommitInfo] = field(default_factory=list)


@dataclass
class RepoAnalysis:
    """Complete quantitative analysis of one repo within the date range."""

    repo_url: str
    repo_name: str
    date_from: datetime
    date_to: datetime
    commits: list[CommitInfo] = field(default_factory=list)
    authors: dict[str, AuthorMetrics] = field(default_factory=dict)
    total_commits: int = 0
    total_lines_added: int = 0
    total_lines_removed: int = 0
    files_changed: list[str] = field(default_factory=list)
    file_type_breakdown: list[FileTypeBreakdown] = field(default_factory=list)
    commit_categories: list[CommitCategory] = field(default_factory=list)
    daily_activity: list[DailyActivity] = field(default_factory=list)
    change_type_stats: ChangeTypeStats = field(default_factory=ChangeTypeStats)
    churned_files: list[ChurnedFile] = field(default_factory=list)
    peak_day: DailyActivity | None = None
    weekend_commits: int = 0
    weekday_commits: int = 0


@dataclass
class ContributorSummary:
    """Combines quantitative metrics with LLM-generated qualitative summary."""

    name: str
    email: str
    metrics: AuthorMetrics
    qualitative_summary: str = ""


@dataclass
class RepoSummary:
    """Combined quantitative and qualitative analysis for one repo."""

    repo_url: str
    repo_name: str
    analysis: RepoAnalysis
    overall_summary: str = ""
    key_areas: list[str] = field(default_factory=list)


@dataclass
class SprintReport:
    """Top-level output of the entire pipeline."""

    date_from: datetime
    date_to: datetime
    repos: list[RepoSummary] = field(default_factory=list)
    contributors: list[ContributorSummary] = field(default_factory=list)
    overall_narrative: str = ""
    generated_at: datetime = field(default_factory=datetime.now)
    token_usage: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Recursively serialize to a JSON-compatible dict."""
        return _serialize(self)


def _serialize(obj):
    """Recursive serializer for dataclasses, datetimes, and basic types."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {str(k): _serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize(item) for item in obj]
    if hasattr(obj, "__dataclass_fields__"):
        return {name: _serialize(getattr(obj, name)) for name in obj.__dataclass_fields__}
    return obj
