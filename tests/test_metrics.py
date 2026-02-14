"""Tests for metrics computation."""

from datetime import datetime

from sprint_snitch.git_analysis.metrics import (
    compute_author_metrics,
    compute_repo_analysis,
    get_changed_files,
)
from sprint_snitch.models.data import CommitInfo, FileChange


def _make_commit(sha, author_name, author_email, files=None, lines_added=0, lines_removed=0):
    return CommitInfo(
        sha=sha,
        author_name=author_name,
        author_email=author_email,
        message=f"commit {sha}",
        timestamp=datetime(2025, 1, 10),
        files=files or [],
        lines_added=lines_added,
        lines_removed=lines_removed,
    )


def _make_file(path, added=1, removed=0):
    return FileChange(path=path, lines_added=added, lines_removed=removed, change_type="modified")


def test_compute_author_metrics_single_author():
    commits = [
        _make_commit("a1", "Alice", "a@e.com", [_make_file("x.py")], 10, 2),
        _make_commit("a2", "Alice", "a@e.com", [_make_file("y.py")], 5, 1),
        _make_commit("a3", "Alice", "a@e.com", [_make_file("x.py")], 3, 0),
    ]
    result = compute_author_metrics(commits)
    assert len(result) == 1
    m = result["a@e.com"]
    assert m.lines_added == 18
    assert m.lines_removed == 3
    assert len(m.commits) == 3


def test_compute_author_metrics_multiple_authors():
    commits = [
        _make_commit("a1", "Alice", "a@e.com", [_make_file("a.py")], 10, 0),
        _make_commit("b1", "Bob", "b@e.com", [_make_file("b.py")], 5, 2),
    ]
    result = compute_author_metrics(commits)
    assert len(result) == 2
    assert result["a@e.com"].name == "Alice"
    assert result["b@e.com"].name == "Bob"
    assert len(result["a@e.com"].commits) == 1
    assert len(result["b@e.com"].commits) == 1


def test_compute_repo_analysis_totals():
    commits = [
        _make_commit("a1", "Alice", "a@e.com", [_make_file("f.py", 10, 3)], 10, 3),
        _make_commit("a2", "Bob", "b@e.com", [_make_file("g.py", 5, 1)], 5, 1),
    ]
    analysis = compute_repo_analysis(
        "https://github.com/org/myrepo.git", commits,
        datetime(2025, 1, 1), datetime(2025, 1, 14),
    )
    assert analysis.total_commits == 2
    assert analysis.total_lines_added == 15
    assert analysis.total_lines_removed == 4
    assert len(analysis.authors) == 2


def test_compute_repo_analysis_repo_name():
    analysis = compute_repo_analysis(
        "https://github.com/org/myrepo.git", [],
        datetime(2025, 1, 1), datetime(2025, 1, 14),
    )
    assert analysis.repo_name == "myrepo"


def test_get_changed_files_deduplication():
    commits = [
        _make_commit("a1", "A", "a@e.com", [_make_file("shared.py"), _make_file("only_a.py")]),
        _make_commit("b1", "B", "b@e.com", [_make_file("shared.py"), _make_file("only_b.py")]),
        _make_commit("c1", "C", "c@e.com", [_make_file("shared.py")]),
    ]
    result = get_changed_files(commits)
    assert result.count("shared.py") == 1  # Deduplicated
    assert len(result) == 3


def test_get_changed_files_sorted():
    commits = [
        _make_commit("a1", "A", "a@e.com", [_make_file("z.py"), _make_file("a.py"), _make_file("m.py")]),
    ]
    result = get_changed_files(commits)
    assert result == ["a.py", "m.py", "z.py"]
