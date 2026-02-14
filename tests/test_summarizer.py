"""Tests for sprint summarizer."""

from datetime import datetime
from unittest.mock import MagicMock

from sprint_snitch.llm_integration.summarizer import SprintSummarizer
from sprint_snitch.models.data import AuthorMetrics, CommitInfo, FileChange, RepoAnalysis


def _make_bridge(return_value="LLM summary text"):
    bridge = MagicMock()
    bridge.is_available.return_value = True
    bridge.execute.return_value = return_value
    return bridge


def _make_author(name="Alice", email="a@e.com"):
    fc = FileChange(path="main.py", lines_added=10, lines_removed=2, change_type="modified", content="code")
    commit = CommitInfo(
        sha="abc", author_name=name, author_email=email,
        message="fix", timestamp=datetime(2025, 1, 10), files=[fc],
        lines_added=10, lines_removed=2,
    )
    return AuthorMetrics(
        name=name, email=email,
        lines_added=10, lines_removed=2,
        commits=[commit],
    )


def _make_analysis(authors=None):
    if authors is None:
        authors = {"a@e.com": _make_author()}
    fc = FileChange(path="main.py", lines_added=10, lines_removed=2, change_type="modified", content="code")
    commit = CommitInfo(
        sha="abc", author_name="Alice", author_email="a@e.com",
        message="fix", timestamp=datetime(2025, 1, 10), files=[fc],
        lines_added=10, lines_removed=2,
    )
    return RepoAnalysis(
        repo_url="https://github.com/org/repo",
        repo_name="repo",
        date_from=datetime(2025, 1, 1),
        date_to=datetime(2025, 1, 14),
        commits=[commit],
        authors=authors,
        total_commits=1,
    )


def test_summarize_contributor_success():
    bridge = _make_bridge("Alice did great work on the backend.")
    summarizer = SprintSummarizer(bridge)
    result = summarizer.summarize_contributor(_make_author(), {"main.py": "code"})
    assert result == "Alice did great work on the backend."
    bridge.execute.assert_called_once()


def test_summarize_contributor_fallback():
    bridge = _make_bridge(None)
    summarizer = SprintSummarizer(bridge)
    result = summarizer.summarize_contributor(_make_author(), {})
    assert "unavailable" in result.lower()


def test_summarize_repo_success():
    bridge = _make_bridge("The repo saw significant backend improvements.")
    summarizer = SprintSummarizer(bridge)
    result = summarizer.summarize_repo(_make_analysis(), {"main.py": "code"})
    assert "backend improvements" in result


def test_generate_sprint_narrative():
    bridge = _make_bridge("A productive sprint overall.")
    summarizer = SprintSummarizer(bridge)
    result = summarizer.generate_sprint_narrative(["repo summary"], ["contrib summary"])
    assert "productive" in result


def test_summarize_all_progress():
    bridge = _make_bridge("summary")
    summarizer = SprintSummarizer(bridge)
    progress_calls = []

    def on_progress(current, total, desc):
        progress_calls.append((current, total, desc))

    analysis = _make_analysis()
    contributors, repos, narrative = summarizer.summarize_all([analysis], on_progress=on_progress)

    # Should have: 1 author + 1 repo + 1 narrative = 3 progress calls
    assert len(progress_calls) == 3
    assert progress_calls[-1][0] == progress_calls[-1][1]  # last call: current == total


def test_summarize_all_dedup_contributors():
    """Same author email in two repos should produce single merged ContributorSummary."""
    bridge = _make_bridge("summary")
    summarizer = SprintSummarizer(bridge)

    a1 = _make_analysis(authors={"a@e.com": _make_author()})
    a2 = _make_analysis(authors={"a@e.com": _make_author("Alice", "a@e.com")})

    contributors, repos, narrative = summarizer.summarize_all([a1, a2])
    # One contributor (deduplicated by email)
    assert len(contributors) == 1
    assert contributors[0].email == "a@e.com"


def test_summarize_all_handles_empty():
    bridge = _make_bridge("narrative")
    summarizer = SprintSummarizer(bridge)
    contributors, repos, narrative = summarizer.summarize_all([])
    assert contributors == []
    assert repos == []
    assert "narrative" in narrative or "unavailable" in narrative.lower()
