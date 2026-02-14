"""Tests for GUI background workers."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication

from sprint_snitch.gui.workers import AnalysisWorker
from sprint_snitch.models.data import (
    AuthorMetrics,
    CommitInfo,
    ContributorSummary,
    FileChange,
    RepoAnalysis,
    RepoSummary,
    SprintReport,
)


@pytest.fixture(scope="session")
def qapp():
    """Create a QCoreApplication for signal/slot testing."""
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    return app


def _make_worker(use_llm=False) -> AnalysisWorker:
    return AnalysisWorker(
        repo_urls=["https://github.com/org/repo.git"],
        date_from=datetime(2025, 1, 1),
        date_to=datetime(2025, 1, 14),
        config_path=None,
        use_llm=use_llm,
        work_dir="/tmp/test_workdir",
    )


def _fake_analysis() -> RepoAnalysis:
    fc = FileChange(path="src/main.py", lines_added=10, lines_removed=2, change_type="modified")
    commit = CommitInfo(
        sha="abc123", author_name="Alice", author_email="alice@example.com",
        message="test commit", timestamp=datetime(2025, 1, 10, 14, 0),
        files=[fc], lines_added=10, lines_removed=2,
    )
    author = AuthorMetrics(
        name="Alice", email="alice@example.com",
        lines_added=10, lines_removed=2, commits=[commit],
    )
    return RepoAnalysis(
        repo_url="https://github.com/org/repo.git",
        repo_name="repo",
        date_from=datetime(2025, 1, 1),
        date_to=datetime(2025, 1, 14),
        commits=[commit],
        authors={"alice@example.com": author},
        total_commits=1, total_lines_added=10, total_lines_removed=2,
        files_changed=["src/main.py"],
    )


def _auto_accept(worker: AnalysisWorker) -> None:
    """Connect the identities_discovered signal to auto-accept (no remapping).

    In synchronous tests (calling ``worker.run()`` directly on the same
    thread), the signal is delivered via a direct connection, so the slot
    executes *before* the worker reaches the QWaitCondition.  Setting the
    mapping to ``{}`` causes the while-loop to exit immediately.
    """
    worker.identities_discovered.connect(
        lambda _ids, _commits: worker.set_identity_mapping({})
    )


def test_worker_emits_progress(qapp):
    """Worker should emit progress signals during the pipeline."""
    worker = _make_worker(use_llm=False)
    _auto_accept(worker)
    progress_calls = []
    worker.progress.connect(lambda cur, tot, msg: progress_calls.append((cur, tot, msg)))

    analysis = _fake_analysis()

    with patch("sprint_snitch.gui.workers.clone_or_fetch", return_value=Path("/fake/repo")), \
         patch("sprint_snitch.gui.workers.extract_commits", return_value=analysis.commits), \
         patch("sprint_snitch.gui.workers.compute_repo_analysis", return_value=analysis):
        worker.run()

    assert len(progress_calls) >= 3  # at least clone + extract + analyze steps
    # Steps should increment
    steps = [c[0] for c in progress_calls]
    assert steps == sorted(steps)


def test_worker_emits_finished_with_report(qapp):
    """Worker should emit finished with a SprintReport on success."""
    worker = _make_worker(use_llm=False)
    _auto_accept(worker)
    results = []
    worker.finished.connect(lambda report: results.append(report))

    analysis = _fake_analysis()

    with patch("sprint_snitch.gui.workers.clone_or_fetch", return_value=Path("/fake/repo")), \
         patch("sprint_snitch.gui.workers.extract_commits", return_value=analysis.commits), \
         patch("sprint_snitch.gui.workers.compute_repo_analysis", return_value=analysis):
        worker.run()

    assert len(results) == 1
    report = results[0]
    assert isinstance(report, SprintReport)
    assert len(report.repos) == 1
    assert report.repos[0].repo_name == "repo"
    assert len(report.contributors) == 1


def test_worker_emits_error_on_clone_failure(qapp):
    """Clone failure should emit error signal, not crash."""
    from sprint_snitch.git_analysis.clone import GitError

    worker = _make_worker(use_llm=False)
    errors = []
    worker.error.connect(lambda msg: errors.append(msg))

    with patch(
        "sprint_snitch.gui.workers.clone_or_fetch",
        side_effect=GitError("clone failed", 128, "fatal: repo not found"),
    ):
        worker.run()

    assert len(errors) == 1
    assert "clone failed" in errors[0]


def test_worker_no_llm_mode(qapp):
    """With use_llm=False, worker should skip LLM and produce quantitative-only report."""
    worker = _make_worker(use_llm=False)
    _auto_accept(worker)
    results = []
    worker.finished.connect(lambda report: results.append(report))

    analysis = _fake_analysis()

    with patch("sprint_snitch.gui.workers.clone_or_fetch", return_value=Path("/fake/repo")), \
         patch("sprint_snitch.gui.workers.extract_commits", return_value=analysis.commits), \
         patch("sprint_snitch.gui.workers.compute_repo_analysis", return_value=analysis):
        worker.run()

    report = results[0]
    # No qualitative summary in quantitative-only mode
    assert report.overall_narrative == ""
    # Contributors should still be populated from merged metrics
    assert report.contributors[0].qualitative_summary == ""


def test_worker_llm_unavailable_graceful(qapp):
    """When use_llm=True but bridge unavailable, worker should still finish."""
    worker = _make_worker(use_llm=True)
    _auto_accept(worker)
    results = []
    worker.finished.connect(lambda report: results.append(report))

    analysis = _fake_analysis()

    mock_bridge = MagicMock()
    mock_bridge.is_available.return_value = False

    with patch("sprint_snitch.gui.workers.clone_or_fetch", return_value=Path("/fake/repo")), \
         patch("sprint_snitch.gui.workers.extract_commits", return_value=analysis.commits), \
         patch("sprint_snitch.gui.workers.compute_repo_analysis", return_value=analysis), \
         patch("sprint_snitch.gui.workers.FabricBridge", return_value=mock_bridge):
        worker.run()

    assert len(results) == 1
    report = results[0]
    # Should fall back to quantitative-only
    assert report.overall_narrative == ""
    assert len(report.repos) == 1


# ---------------------------------------------------------------------------
# Identity reconciliation integration tests
# ---------------------------------------------------------------------------


def test_worker_emits_identities_discovered(qapp):
    """Worker should emit identities_discovered after extraction."""
    worker = _make_worker(use_llm=False)

    discovered = []

    def _capture_and_accept(identities, all_commits):
        discovered.append((identities, all_commits))
        worker.set_identity_mapping({})

    worker.identities_discovered.connect(_capture_and_accept)

    analysis = _fake_analysis()

    with patch("sprint_snitch.gui.workers.clone_or_fetch", return_value=Path("/fake/repo")), \
         patch("sprint_snitch.gui.workers.extract_commits", return_value=analysis.commits), \
         patch("sprint_snitch.gui.workers.compute_repo_analysis", return_value=analysis):
        worker.run()

    assert len(discovered) == 1
    identities, all_commits = discovered[0]
    assert len(identities) == 1
    assert identities[0].email == "alice@example.com"


def test_worker_applies_identity_mapping(qapp):
    """Worker should apply identity mapping before computing analysis."""
    worker = _make_worker(use_llm=False)

    def _remap_and_accept(_identities, _all_commits):
        worker.set_identity_mapping({
            "alice@example.com": ("Alice Renamed", "alice-renamed@co.com"),
        })

    worker.identities_discovered.connect(_remap_and_accept)

    results = []
    worker.finished.connect(lambda report: results.append(report))

    analysis = _fake_analysis()

    # We need compute_repo_analysis to reflect the rewritten commits.
    # The real function will be called with rewritten commits — use a
    # passthrough that captures what it receives.
    captured_commits = []

    def _capture_analysis(url, commits, date_from, date_to):
        captured_commits.extend(commits)
        return analysis

    with patch("sprint_snitch.gui.workers.clone_or_fetch", return_value=Path("/fake/repo")), \
         patch("sprint_snitch.gui.workers.extract_commits", return_value=analysis.commits), \
         patch("sprint_snitch.gui.workers.compute_repo_analysis", side_effect=_capture_analysis):
        worker.run()

    assert len(results) == 1
    # Commits passed to compute_repo_analysis should have rewritten identity
    assert captured_commits[0].author_name == "Alice Renamed"
    assert captured_commits[0].author_email == "alice-renamed@co.com"
