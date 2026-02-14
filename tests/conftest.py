"""Shared test fixtures for sprint-snitch."""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from sprint_snitch.models.data import (
    AuthorMetrics,
    CommitInfo,
    ContributorSummary,
    FileChange,
    RepoAnalysis,
    RepoSummary,
    SprintReport,
)


@pytest.fixture
def sample_file_change():
    return FileChange(
        path="src/main.py",
        lines_added=15,
        lines_removed=3,
        change_type="modified",
        content="def main():\n    print('hello')\n",
    )


@pytest.fixture
def sample_commit_info(sample_file_change):
    return CommitInfo(
        sha="abc123def456",
        author_name="Alice Smith",
        author_email="alice@example.com",
        message="Improve main function",
        timestamp=datetime(2025, 1, 10, 14, 30),
        files=[
            sample_file_change,
            FileChange(
                path="src/utils.py", lines_added=5, lines_removed=0,
                change_type="added", content="# Utility functions\n",
            ),
        ],
        lines_added=20,
        lines_removed=3,
    )


@pytest.fixture
def sample_author_metrics(sample_commit_info):
    return AuthorMetrics(
        name="Alice Smith",
        email="alice@example.com",
        lines_added=60,
        lines_removed=12,
        commits=[sample_commit_info],
    )


@pytest.fixture
def sample_repo_analysis(sample_commit_info, sample_author_metrics):
    bob = AuthorMetrics(
        name="Bob Jones",
        email="bob@example.com",
        lines_added=40,
        lines_removed=5,
    )
    return RepoAnalysis(
        repo_url="https://github.com/org/myrepo.git",
        repo_name="myrepo",
        date_from=datetime(2025, 1, 1),
        date_to=datetime(2025, 1, 14),
        commits=[sample_commit_info],
        authors={
            "alice@example.com": sample_author_metrics,
            "bob@example.com": bob,
        },
        total_commits=5,
        total_lines_added=100,
        total_lines_removed=17,
        files_changed=["src/main.py", "src/utils.py", "src/api.py", "tests/test_main.py"],
    )


@pytest.fixture
def sample_sprint_report(sample_repo_analysis, sample_author_metrics):
    rs = RepoSummary(
        repo_url=sample_repo_analysis.repo_url,
        repo_name=sample_repo_analysis.repo_name,
        analysis=sample_repo_analysis,
        overall_summary="Good progress on the backend.",
        key_areas=["backend", "testing"],
    )
    cs = ContributorSummary(
        name="Alice Smith",
        email="alice@example.com",
        metrics=sample_author_metrics,
        qualitative_summary="Alice focused on improving the main module.",
    )
    return SprintReport(
        date_from=datetime(2025, 1, 1),
        date_to=datetime(2025, 1, 14),
        repos=[rs],
        contributors=[cs],
        overall_narrative="A productive sprint with backend improvements.",
        generated_at=datetime(2025, 1, 14, 16, 0),
        token_usage={"input_tokens": 200, "output_tokens": 100, "calls": 5},
    )


@pytest.fixture
def enriched_repo_analysis(sample_repo_analysis):
    """Sample repo analysis with all enrichment fields populated."""
    from sprint_snitch.git_analysis.enrichment import enrich_repo_analysis
    enrich_repo_analysis(sample_repo_analysis)
    return sample_repo_analysis


@pytest.fixture
def mock_fabric_bridge():
    bridge = MagicMock()
    bridge.is_available.return_value = True
    bridge.execute.return_value = "Mocked LLM summary response."
    bridge.get_token_usage.return_value = {
        "input_tokens": 100,
        "output_tokens": 50,
        "calls": 1,
    }
    return bridge
