"""Assembles SprintReport from quantitative and qualitative data."""

from __future__ import annotations

from datetime import datetime

from sprint_snitch.models.data import (
    AuthorMetrics,
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
                existing.lines_added += author.lines_added
                existing.lines_removed += author.lines_removed
                existing.commits.extend(author.commits)
            else:
                merged[email] = AuthorMetrics(
                    name=author.name,
                    email=author.email,
                    lines_added=author.lines_added,
                    lines_removed=author.lines_removed,
                    commits=list(author.commits),
                )

    return merged
