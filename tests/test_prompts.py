"""Tests for prompt templates."""

from datetime import datetime

from sprint_snitch.llm_integration.prompts import (
    build_contributor_prompt,
    build_file_context,
    build_repo_prompt,
    build_sprint_narrative_prompt,
    truncate_context,
)
from sprint_snitch.models.data import (
    AuthorMetrics,
    ChangeTypeStats,
    ChurnedFile,
    CommitInfo,
    DailyActivity,
    FileChange,
    RepoAnalysis,
)


def _make_metrics(name="Alice", email="a@e.com", lines_added=100, lines_removed=20):
    return AuthorMetrics(
        name=name, email=email,
        lines_added=lines_added, lines_removed=lines_removed,
    )


def test_contributor_prompt_contains_name():
    metrics = _make_metrics()
    prompt = build_contributor_prompt("Alice", metrics, {"main.py": "code"})
    assert "Alice" in prompt


def test_contributor_prompt_contains_metrics():
    metrics = _make_metrics(lines_added=200, lines_removed=30)
    prompt = build_contributor_prompt("Alice", metrics, {})
    assert "200" in prompt  # lines added
    assert "30" in prompt  # lines removed


def test_repo_prompt_contains_repo_name():
    analysis = RepoAnalysis(
        repo_url="https://github.com/org/myrepo",
        repo_name="myrepo",
        date_from=datetime(2025, 1, 1),
        date_to=datetime(2025, 1, 14),
        total_commits=10,
    )
    prompt = build_repo_prompt("myrepo", analysis, {})
    assert "myrepo" in prompt


def test_sprint_narrative_prompt_includes_summaries():
    repos = ["Repo A did great things.", "Repo B improved performance."]
    contribs = ["Alice focused on backend.", "Bob worked on frontend."]
    prompt = build_sprint_narrative_prompt(repos, contribs)
    assert "Repo A did great things" in prompt
    assert "Bob worked on frontend" in prompt


def test_truncate_context_short():
    text = "short text"
    assert truncate_context(text, max_chars=100) == text


def test_truncate_context_long():
    text = "x" * 200
    result = truncate_context(text, max_chars=100)
    assert len(result) < 250  # truncated + note
    assert "truncated" in result
    assert "100 chars omitted" in result


def test_build_file_context_dedup():
    """Same file in two commits — latest commit wins."""
    fc1 = FileChange(path="a.py", lines_added=1, lines_removed=0, change_type="modified", content="old")
    fc2 = FileChange(path="a.py", lines_added=1, lines_removed=0, change_type="modified", content="new")
    commits = [
        CommitInfo(sha="c1", author_name="A", author_email="a@e.com", message="first",
                   timestamp=datetime(2025, 1, 1), files=[fc1]),
        CommitInfo(sha="c2", author_name="A", author_email="a@e.com", message="second",
                   timestamp=datetime(2025, 1, 2), files=[fc2]),
    ]
    ctx = build_file_context(commits, max_chars=100000)
    assert ctx["a.py"] == "new"


def test_build_file_context_budget():
    """When total content exceeds budget, largest files are dropped."""
    fc_big = FileChange(path="big.py", lines_added=1, lines_removed=0, change_type="modified",
                        content="x" * 10000)
    fc_small = FileChange(path="small.py", lines_added=1, lines_removed=0, change_type="modified",
                          content="y" * 100)
    commits = [
        CommitInfo(sha="c1", author_name="A", author_email="a@e.com", message="msg",
                   timestamp=datetime(2025, 1, 1), files=[fc_big, fc_small]),
    ]
    ctx = build_file_context(commits, max_chars=500)
    # big.py should have been dropped to fit budget
    assert "small.py" in ctx
    assert "big.py" not in ctx


# ---------------------------------------------------------------------------
# Analytics enrichment in prompts (repo-level only)
# ---------------------------------------------------------------------------


def test_repo_prompt_includes_timeline_context():
    analysis = RepoAnalysis(
        repo_url="https://github.com/org/myrepo",
        repo_name="myrepo",
        date_from=datetime(2025, 1, 1),
        date_to=datetime(2025, 1, 14),
        total_commits=10,
        daily_activity=[
            DailyActivity(datetime(2025, 1, 6), 5, 100, 20, ["a@e.com"]),
            DailyActivity(datetime(2025, 1, 7), 3, 60, 10, ["a@e.com"]),
        ],
        peak_day=DailyActivity(datetime(2025, 1, 6), 5, 100, 20, ["a@e.com"]),
        weekday_commits=8,
        weekend_commits=2,
    )
    prompt = build_repo_prompt("myrepo", analysis, {})
    assert "Sprint Timeline" in prompt
    assert "Peak day" in prompt


def test_repo_prompt_includes_change_analysis():
    analysis = RepoAnalysis(
        repo_url="https://github.com/org/myrepo",
        repo_name="myrepo",
        date_from=datetime(2025, 1, 1),
        date_to=datetime(2025, 1, 14),
        total_commits=10,
        change_type_stats=ChangeTypeStats(files_added=3, files_modified=7, files_deleted=1, files_renamed=0),
        churned_files=[ChurnedFile("main.py", 5, 100, 20)],
    )
    prompt = build_repo_prompt("myrepo", analysis, {})
    assert "Change Analysis" in prompt
    assert "main.py" in prompt
