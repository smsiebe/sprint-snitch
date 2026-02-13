"""Assembles SprintReport from quantitative and qualitative data."""

from __future__ import annotations

from datetime import datetime

from sprint_snitch.git_analysis.enrichment import (
    merge_change_type_stats,
    merge_commit_categories,
    merge_daily_activity,
    merge_file_type_breakdowns,
)
from sprint_snitch.models.data import (
    AuthorMetrics,
    ChangeTypeStats,
    ContributorSummary,
    RepoAnalysis,
    RepoSummary,
    SprintReport,
)


class ReportBuilder:
    """Builder for assembling a SprintReport from components."""

    def __init__(self, date_from: datetime, date_to: datetime):
        self._date_from = date_from
        self._date_to = date_to
        self._repo_summaries: list[RepoSummary] = []
        self._contributor_summaries: list[ContributorSummary] = []
        self._overall_narrative: str = ""
        self._token_usage: dict = {}

    def add_repo_summary(self, summary: RepoSummary) -> None:
        self._repo_summaries.append(summary)

    def add_contributor_summary(self, summary: ContributorSummary) -> None:
        self._contributor_summaries.append(summary)

    def set_overall_narrative(self, narrative: str) -> None:
        self._overall_narrative = narrative

    def set_token_usage(self, usage: dict) -> None:
        self._token_usage = usage

    def build(self) -> SprintReport:
        return SprintReport(
            date_from=self._date_from,
            date_to=self._date_to,
            repos=list(self._repo_summaries),
            contributors=list(self._contributor_summaries),
            overall_narrative=self._overall_narrative,
            generated_at=datetime.now(),
            token_usage=dict(self._token_usage),
        )


def merge_contributors_across_repos(
    analyses: list[RepoAnalysis],
) -> dict[str, AuthorMetrics]:
    """Merge AuthorMetrics by email across multiple repos.

    For the same email across repos: sums commit_count, lines_added,
    lines_removed; unions files_touched; concatenates commits lists.
    """
    merged: dict[str, AuthorMetrics] = {}

    for analysis in analyses:
        for email, author in analysis.authors.items():
            if email in merged:
                existing = merged[email]
                existing.commit_count += author.commit_count
                existing.lines_added += author.lines_added
                existing.lines_removed += author.lines_removed
                # Union of files_touched
                existing_files = set(existing.files_touched)
                for f in author.files_touched:
                    if f not in existing_files:
                        existing.files_touched.append(f)
                        existing_files.add(f)
                existing.commits.extend(author.commits)
                # Merge enrichment fields
                existing.file_type_breakdown = merge_file_type_breakdowns(
                    existing.file_type_breakdown, author.file_type_breakdown,
                )
                existing.commit_categories = merge_commit_categories(
                    existing.commit_categories, author.commit_categories,
                )
                existing.daily_activity = merge_daily_activity(
                    existing.daily_activity, author.daily_activity,
                )
                existing.change_type_stats = merge_change_type_stats(
                    existing.change_type_stats, author.change_type_stats,
                )
            else:
                merged[email] = AuthorMetrics(
                    name=author.name,
                    email=author.email,
                    commit_count=author.commit_count,
                    files_touched=list(author.files_touched),
                    lines_added=author.lines_added,
                    lines_removed=author.lines_removed,
                    commits=list(author.commits),
                    file_type_breakdown=list(author.file_type_breakdown),
                    commit_categories=list(author.commit_categories),
                    daily_activity=list(author.daily_activity),
                    change_type_stats=ChangeTypeStats(
                        files_added=author.change_type_stats.files_added,
                        files_modified=author.change_type_stats.files_modified,
                        files_deleted=author.change_type_stats.files_deleted,
                        files_renamed=author.change_type_stats.files_renamed,
                    ),
                )

    return merged
