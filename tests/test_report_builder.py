"""Tests for report builder."""

from datetime import datetime

from sprint_snitch.models.data import (
    AuthorMetrics,
    CommitInfo,
    ContributorSummary,
    RepoAnalysis,
    RepoSummary,
)
from sprint_snitch.reporting.report_builder import ReportBuilder, merge_contributors_across_repos


def _make_analysis(repo_url="https://github.com/org/repo", authors=None):
    now = datetime(2025, 1, 1)
    return RepoAnalysis(
        repo_url=repo_url,
        repo_name="repo",
        date_from=now,
        date_to=now,
        authors=authors or {},
    )


def test_build_empty_report():
    builder = ReportBuilder(datetime(2025, 1, 1), datetime(2025, 1, 14))
    report = builder.build()
    assert report.repos == []
    assert report.contributors == []
    assert report.overall_narrative == ""


def test_build_single_repo():
    builder = ReportBuilder(datetime(2025, 1, 1), datetime(2025, 1, 14))
    am = AuthorMetrics(name="Alice", email="a@e.com", commit_count=3)
    analysis = _make_analysis(authors={"a@e.com": am})
    rs = RepoSummary(repo_url="u", repo_name="r", analysis=analysis, overall_summary="Good")
    cs = ContributorSummary(name="Alice", email="a@e.com", metrics=am)
    builder.add_repo_summary(rs)
    builder.add_contributor_summary(cs)
    builder.set_overall_narrative("Nice sprint")
    report = builder.build()
    assert len(report.repos) == 1
    assert len(report.contributors) == 1
    assert report.overall_narrative == "Nice sprint"


def test_build_multiple_repos():
    builder = ReportBuilder(datetime(2025, 1, 1), datetime(2025, 1, 14))
    for i in range(2):
        analysis = _make_analysis(repo_url=f"url{i}")
        rs = RepoSummary(repo_url=f"url{i}", repo_name=f"repo{i}", analysis=analysis)
        builder.add_repo_summary(rs)
    report = builder.build()
    assert len(report.repos) == 2


def test_build_sets_generated_at():
    before = datetime.now()
    builder = ReportBuilder(datetime(2025, 1, 1), datetime(2025, 1, 14))
    report = builder.build()
    after = datetime.now()
    assert before <= report.generated_at <= after


def test_merge_contributors_same_email():
    am1 = AuthorMetrics(
        name="Alice", email="a@e.com", commit_count=3,
        files_touched=["a.py", "b.py"], lines_added=100, lines_removed=20,
    )
    am2 = AuthorMetrics(
        name="Alice", email="a@e.com", commit_count=2,
        files_touched=["b.py", "c.py"], lines_added=50, lines_removed=10,
    )
    a1 = _make_analysis(repo_url="r1", authors={"a@e.com": am1})
    a2 = _make_analysis(repo_url="r2", authors={"a@e.com": am2})
    merged = merge_contributors_across_repos([a1, a2])
    assert len(merged) == 1
    m = merged["a@e.com"]
    assert m.commit_count == 5
    assert m.lines_added == 150
    assert m.lines_removed == 30
    # files_touched should be union: a.py, b.py, c.py
    assert set(m.files_touched) == {"a.py", "b.py", "c.py"}


def test_merge_contributors_different_emails():
    am1 = AuthorMetrics(name="Alice", email="a@e.com", commit_count=3)
    am2 = AuthorMetrics(name="Bob", email="b@e.com", commit_count=2)
    a = _make_analysis(authors={"a@e.com": am1, "b@e.com": am2})
    merged = merge_contributors_across_repos([a])
    assert len(merged) == 2
    assert "a@e.com" in merged
    assert "b@e.com" in merged


def test_merge_contributors_empty():
    merged = merge_contributors_across_repos([])
    assert merged == {}
