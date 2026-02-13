"""Tests for data models."""

import json
from datetime import datetime

from sprint_snitch.models.data import (
    AuthorMetrics,
    ChangeTypeStats,
    ChurnedFile,
    CommitCategory,
    CommitInfo,
    ContributorSummary,
    DailyActivity,
    FileChange,
    FileTypeBreakdown,
    RepoAnalysis,
    RepoSummary,
    SprintReport,
    _serialize,
)


def test_file_change_creation():
    fc = FileChange(
        path="src/main.py",
        lines_added=10,
        lines_removed=3,
        change_type="modified",
        content="print('hello')",
    )
    assert fc.path == "src/main.py"
    assert fc.lines_added == 10
    assert fc.lines_removed == 3
    assert fc.change_type == "modified"
    assert fc.content == "print('hello')"


def test_commit_info_defaults():
    ci = CommitInfo(
        sha="abc123",
        author_name="Alice",
        author_email="alice@example.com",
        message="fix bug",
        timestamp=datetime(2025, 1, 15, 10, 30),
    )
    assert ci.files == []
    assert ci.lines_added == 0
    assert ci.lines_removed == 0
    assert ci.sha == "abc123"


def test_author_metrics_empty():
    am = AuthorMetrics(name="Bob", email="bob@example.com")
    assert am.commit_count == 0
    assert am.files_touched == []
    assert am.lines_added == 0
    assert am.lines_removed == 0
    assert am.commits == []


def test_repo_analysis_stores_authors():
    now = datetime.now()
    am1 = AuthorMetrics(name="Alice", email="alice@example.com", commit_count=3)
    am2 = AuthorMetrics(name="Bob", email="bob@example.com", commit_count=5)
    ra = RepoAnalysis(
        repo_url="https://github.com/org/repo",
        repo_name="repo",
        date_from=now,
        date_to=now,
        authors={"alice@example.com": am1, "bob@example.com": am2},
    )
    assert ra.authors["alice@example.com"].commit_count == 3
    assert ra.authors["bob@example.com"].commit_count == 5


def test_contributor_summary_empty_qualitative():
    am = AuthorMetrics(name="Alice", email="alice@example.com")
    cs = ContributorSummary(name="Alice", email="alice@example.com", metrics=am)
    assert cs.qualitative_summary == ""


def test_sprint_report_to_dict_serializable():
    now = datetime(2025, 1, 15, 10, 30)
    am = AuthorMetrics(name="Alice", email="alice@example.com", commit_count=2)
    ra = RepoAnalysis(
        repo_url="https://github.com/org/repo",
        repo_name="repo",
        date_from=now,
        date_to=now,
        authors={"alice@example.com": am},
        total_commits=2,
    )
    rs = RepoSummary(
        repo_url=ra.repo_url,
        repo_name=ra.repo_name,
        analysis=ra,
        overall_summary="Good sprint",
        key_areas=["backend", "tests"],
    )
    cs = ContributorSummary(
        name="Alice",
        email="alice@example.com",
        metrics=am,
        qualitative_summary="Alice did great work",
    )
    report = SprintReport(
        date_from=now,
        date_to=now,
        repos=[rs],
        contributors=[cs],
        overall_narrative="A productive sprint.",
        generated_at=now,
        token_usage={"input_tokens": 100, "output_tokens": 50},
    )
    d = report.to_dict()
    # Must be JSON-serializable
    serialized = json.dumps(d)
    assert isinstance(serialized, str)
    assert len(serialized) > 0


def test_sprint_report_to_dict_datetime_format():
    now = datetime(2025, 6, 15, 14, 30, 0)
    report = SprintReport(date_from=now, date_to=now, generated_at=now)
    d = report.to_dict()
    assert d["date_from"] == "2025-06-15T14:30:00"
    assert d["date_to"] == "2025-06-15T14:30:00"
    assert d["generated_at"] == "2025-06-15T14:30:00"


def test_sprint_report_generated_at_auto():
    before = datetime.now()
    report = SprintReport(
        date_from=datetime(2025, 1, 1),
        date_to=datetime(2025, 1, 14),
    )
    after = datetime.now()
    assert before <= report.generated_at <= after


def test_new_dataclasses_serialize():
    """All new analytics dataclasses should serialize via _serialize()."""
    objects = [
        FileTypeBreakdown("Python", ".py", 3, 100, 20, 5),
        CommitCategory("feat", 4),
        DailyActivity(datetime(2025, 1, 6), 3, 50, 10, ["a@e.com"]),
        ChangeTypeStats(1, 5, 2, 0),
        ChurnedFile("main.py", 4, 80, 15),
    ]
    for obj in objects:
        serialized = _serialize(obj)
        assert isinstance(serialized, dict)
        # Must be JSON-serializable
        result = json.dumps(serialized)
        assert isinstance(result, str)
