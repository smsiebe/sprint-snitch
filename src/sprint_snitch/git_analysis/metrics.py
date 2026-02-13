"""Quantitative metrics computation."""

from __future__ import annotations

import re
from datetime import datetime

from sprint_snitch.models.data import AuthorMetrics, CommitInfo, RepoAnalysis


def compute_author_metrics(commits: list[CommitInfo]) -> dict[str, AuthorMetrics]:
    """Aggregate per-author metrics from a list of commits.

    Parameters
    ----------
    commits:
        Parsed commits (as returned by :func:`extract_commits`).

    Returns
    -------
    dict[str, AuthorMetrics]
        Keyed by author email address.
    """
    authors: dict[str, AuthorMetrics] = {}

    for commit in commits:
        email = commit.author_email

        if email not in authors:
            authors[email] = AuthorMetrics(
                name=commit.author_name,
                email=email,
            )

        author = authors[email]
        author.commit_count += 1
        author.lines_added += commit.lines_added
        author.lines_removed += commit.lines_removed
        author.commits.append(commit)

        # Collect unique file paths touched by this author.
        for file_change in commit.files:
            if file_change.path not in author.files_touched:
                author.files_touched.append(file_change.path)

    return authors


def compute_repo_analysis(
    repo_url: str,
    commits: list[CommitInfo],
    date_from: datetime,
    date_to: datetime,
) -> RepoAnalysis:
    """Build a complete :class:`RepoAnalysis` for a single repository.

    Parameters
    ----------
    repo_url:
        The remote URL of the repository (used for metadata).
    commits:
        All commits within the date range.
    date_from / date_to:
        The queried date boundaries.

    Returns
    -------
    RepoAnalysis
    """
    authors = compute_author_metrics(commits)

    total_added = sum(c.lines_added for c in commits)
    total_removed = sum(c.lines_removed for c in commits)
    files_changed = get_changed_files(commits)

    # Derive a human-friendly repo name from the URL.
    # Take the last path segment and strip a trailing ".git".
    repo_name = repo_url.rstrip("/").rsplit("/", 1)[-1]
    repo_name = re.sub(r"\.git$", "", repo_name)

    analysis = RepoAnalysis(
        repo_url=repo_url,
        repo_name=repo_name,
        date_from=date_from,
        date_to=date_to,
        commits=commits,
        authors=authors,
        total_commits=len(commits),
        total_lines_added=total_added,
        total_lines_removed=total_removed,
        files_changed=files_changed,
    )

    # Enrich with analytics (file types, commit categories, daily activity, etc.)
    from sprint_snitch.git_analysis.enrichment import enrich_repo_analysis
    enrich_repo_analysis(analysis)

    return analysis


def get_changed_files(commits: list[CommitInfo]) -> list[str]:
    """Return a sorted list of unique file paths changed across all commits.

    Parameters
    ----------
    commits:
        Parsed commits to scan.

    Returns
    -------
    list[str]
        Deduplicated, alphabetically sorted file paths.
    """
    files: set[str] = set()
    for commit in commits:
        for file_change in commit.files:
            files.add(file_change.path)
    return sorted(files)
