"""Tests for rich analytics enrichment module."""

from datetime import datetime

import pytest

from sprint_snitch.git_analysis.enrichment import (
    classify_commit,
    classify_file_type,
    compute_change_type_stats,
    compute_churned_files,
    compute_commit_categories,
    compute_daily_activity,
    compute_file_type_breakdown,
    compute_weekday_weekend_split,
    enrich_repo_analysis,
    identify_peak_day,
)
from sprint_snitch.models.data import (
    AuthorMetrics,
    CommitInfo,
    DailyActivity,
    FileChange,
    RepoAnalysis,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _commit(sha, message, timestamp, files=None, author_email="alice@example.com"):
    """Shorthand for building a CommitInfo with sensible defaults."""
    files = files or []
    added = sum(f.lines_added for f in files)
    removed = sum(f.lines_removed for f in files)
    return CommitInfo(
        sha=sha, author_name="Alice", author_email=author_email,
        message=message, timestamp=timestamp, files=files,
        lines_added=added, lines_removed=removed,
    )


def _fc(path, added=5, removed=1, change_type="modified"):
    return FileChange(path=path, lines_added=added, lines_removed=removed, change_type=change_type)


# ---------------------------------------------------------------------------
# File type classification
# ---------------------------------------------------------------------------

def test_classify_file_type_python():
    ft, ext = classify_file_type("src/main.py")
    assert ft == "Python"
    assert ext == ".py"


def test_classify_file_type_unknown_extension():
    ft, ext = classify_file_type("data/output.xyz")
    assert ft == "Other"
    assert ext == ".xyz"


def test_classify_file_type_no_extension():
    ft, ext = classify_file_type("Dockerfile")
    assert ft == "Docker"


def test_classify_file_type_case_insensitive():
    ft, ext = classify_file_type("MODULE.PY")
    assert ft == "Python"
    assert ext == ".py"


# ---------------------------------------------------------------------------
# File type breakdown
# ---------------------------------------------------------------------------

def test_compute_file_type_breakdown_mixed():
    commits = [
        _commit("a1", "fix", datetime(2025, 1, 10), [
            _fc("src/main.py", added=10, removed=2),
            _fc("src/utils.js", added=5, removed=0),
        ]),
        _commit("b2", "add docs", datetime(2025, 1, 11), [
            _fc("README.md", added=20, removed=0),
            _fc("src/main.py", added=3, removed=1),
        ]),
    ]
    breakdown = compute_file_type_breakdown(commits)
    assert len(breakdown) >= 3

    by_type = {b.file_type: b for b in breakdown}
    assert "Python" in by_type
    assert by_type["Python"].lines_added == 13  # 10 + 3
    assert by_type["Python"].lines_removed == 3  # 2 + 1
    assert by_type["Python"].file_count == 1  # same file
    assert by_type["Python"].commit_count == 2  # two commits touch it

    assert "Documentation" in by_type
    assert by_type["Documentation"].lines_added == 20


def test_compute_file_type_breakdown_empty():
    assert compute_file_type_breakdown([]) == []


# ---------------------------------------------------------------------------
# Commit classification
# ---------------------------------------------------------------------------

def test_classify_commit_conventional_feat():
    assert classify_commit("feat: add login page") == "feat"


def test_classify_commit_conventional_with_scope():
    assert classify_commit("fix(auth): resolve token expiry") == "fix"


def test_classify_commit_keyword_fallback():
    assert classify_commit("Fix the login bug") == "fix"


def test_classify_commit_no_match():
    assert classify_commit("Merge branch 'main'") == "other"


def test_classify_commit_case_insensitive():
    assert classify_commit("FEAT: big change") == "feat"


# ---------------------------------------------------------------------------
# Commit categories
# ---------------------------------------------------------------------------

def test_compute_commit_categories_distribution():
    commits = [
        _commit("a1", "feat: add X", datetime(2025, 1, 10)),
        _commit("a2", "feat: add Y", datetime(2025, 1, 11)),
        _commit("a3", "feat: add Z", datetime(2025, 1, 12)),
        _commit("b1", "fix: repair widget", datetime(2025, 1, 13)),
        _commit("b2", "fix: patch bug", datetime(2025, 1, 14)),
    ]
    categories = compute_commit_categories(commits)
    by_cat = {c.category: c.count for c in categories}
    assert by_cat["feat"] == 3
    assert by_cat["fix"] == 2


def test_compute_commit_categories_sets_category_field():
    commits = [
        _commit("a1", "feat: add X", datetime(2025, 1, 10)),
        _commit("a2", "docs: update readme", datetime(2025, 1, 11)),
    ]
    compute_commit_categories(commits)
    assert commits[0].category == "feat"
    assert commits[1].category == "docs"


# ---------------------------------------------------------------------------
# Daily activity
# ---------------------------------------------------------------------------

def test_compute_daily_activity_fills_gaps():
    """Days with zero commits should still have entries."""
    commits = [
        _commit("a1", "work", datetime(2025, 1, 1, 10, 0)),
        _commit("a2", "more", datetime(2025, 1, 5, 15, 0)),
    ]
    daily = compute_daily_activity(commits, datetime(2025, 1, 1), datetime(2025, 1, 5))
    assert len(daily) == 5
    # Day 1 and Day 5 have commits; days 2-4 are zero
    assert daily[0].commit_count == 1
    assert daily[1].commit_count == 0
    assert daily[2].commit_count == 0
    assert daily[3].commit_count == 0
    assert daily[4].commit_count == 1


def test_compute_daily_activity_correct_binning():
    """Multiple commits on same day should be aggregated."""
    commits = [
        _commit("a1", "first", datetime(2025, 1, 3, 9, 0), [_fc("a.py", 10, 2)]),
        _commit("a2", "second", datetime(2025, 1, 3, 14, 0), [_fc("b.py", 5, 1)]),
    ]
    daily = compute_daily_activity(commits, datetime(2025, 1, 3), datetime(2025, 1, 3))
    assert len(daily) == 1
    assert daily[0].commit_count == 2
    assert daily[0].lines_added == 15


def test_compute_daily_activity_authors_tracked():
    commits = [
        _commit("a1", "alice", datetime(2025, 1, 1, 10, 0), author_email="alice@e.com"),
        _commit("b1", "bob", datetime(2025, 1, 1, 11, 0), author_email="bob@e.com"),
        _commit("a2", "alice", datetime(2025, 1, 1, 12, 0), author_email="alice@e.com"),
    ]
    daily = compute_daily_activity(commits, datetime(2025, 1, 1), datetime(2025, 1, 1))
    assert len(daily[0].authors) == 2
    assert "alice@e.com" in daily[0].authors
    assert "bob@e.com" in daily[0].authors


# ---------------------------------------------------------------------------
# Peak day + weekday/weekend
# ---------------------------------------------------------------------------

def test_identify_peak_day():
    daily = [
        DailyActivity(date=datetime(2025, 1, 6), commit_count=3),  # Mon
        DailyActivity(date=datetime(2025, 1, 7), commit_count=8),  # Tue (peak)
        DailyActivity(date=datetime(2025, 1, 8), commit_count=2),  # Wed
    ]
    peak = identify_peak_day(daily)
    assert peak is not None
    assert peak.commit_count == 8
    assert peak.date == datetime(2025, 1, 7)


def test_compute_weekday_weekend_split():
    commits = [
        _commit("a1", "m", datetime(2025, 1, 6, 10, 0)),   # Monday
        _commit("a2", "t", datetime(2025, 1, 7, 10, 0)),   # Tuesday
        _commit("a3", "w", datetime(2025, 1, 8, 10, 0)),   # Wednesday
        _commit("a4", "s", datetime(2025, 1, 11, 10, 0)),  # Saturday
    ]
    weekday, weekend = compute_weekday_weekend_split(commits)
    assert weekday == 3
    assert weekend == 1


# ---------------------------------------------------------------------------
# Change type stats
# ---------------------------------------------------------------------------

def test_compute_change_type_stats_mixed():
    commits = [
        _commit("a1", "work", datetime(2025, 1, 10), [
            _fc("new.py", change_type="added"),
            _fc("old.py", change_type="modified"),
        ]),
        _commit("a2", "more", datetime(2025, 1, 11), [
            _fc("dead.py", change_type="deleted"),
            _fc("old.py", change_type="modified"),
            _fc("moved.py", change_type="renamed"),
        ]),
    ]
    stats = compute_change_type_stats(commits)
    assert stats.files_added == 1
    assert stats.files_modified == 2
    assert stats.files_deleted == 1
    assert stats.files_renamed == 1


# ---------------------------------------------------------------------------
# Churned files
# ---------------------------------------------------------------------------

def test_compute_churned_files_filters_and_sorts():
    commits = [
        _commit("a1", "w1", datetime(2025, 1, 10), [_fc("hot.py"), _fc("cold.py")]),
        _commit("a2", "w2", datetime(2025, 1, 11), [_fc("hot.py"), _fc("warm.py")]),
        _commit("a3", "w3", datetime(2025, 1, 12), [_fc("hot.py"), _fc("warm.py")]),
    ]
    churned = compute_churned_files(commits, min_changes=2)
    paths = [c.path for c in churned]
    assert "hot.py" in paths
    assert "warm.py" in paths
    assert "cold.py" not in paths
    assert churned[0].path == "hot.py"
    assert churned[0].change_count == 3


def test_compute_churned_files_top_n():
    commits = [
        _commit("a1", "w", datetime(2025, 1, 10), [_fc("a.py"), _fc("b.py"), _fc("c.py")]),
        _commit("a2", "w", datetime(2025, 1, 11), [_fc("a.py"), _fc("b.py"), _fc("c.py")]),
    ]
    churned = compute_churned_files(commits, min_changes=2, top_n=2)
    assert len(churned) == 2


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def test_enrich_repo_analysis_populates_all():
    fc = _fc("src/main.py", 10, 2)
    commit = _commit("abc", "feat: add main", datetime(2025, 1, 10, 14, 0), [fc])
    author = AuthorMetrics(
        name="Alice", email="alice@example.com",
        lines_added=10, lines_removed=2, commits=[commit],
    )
    analysis = RepoAnalysis(
        repo_url="https://github.com/org/repo.git",
        repo_name="repo",
        date_from=datetime(2025, 1, 1),
        date_to=datetime(2025, 1, 14),
        commits=[commit],
        authors={"alice@example.com": author},
        total_commits=1, total_lines_added=10, total_lines_removed=2,
        files_changed=["src/main.py"],
    )
    enrich_repo_analysis(analysis)

    # Repo-level
    assert len(analysis.file_type_breakdown) > 0
    assert len(analysis.commit_categories) > 0
    assert len(analysis.daily_activity) == 14
    assert analysis.peak_day is not None
    assert analysis.weekday_commits + analysis.weekend_commits == 1
    assert analysis.change_type_stats.files_modified == 1
    assert commit.category == "feat"
