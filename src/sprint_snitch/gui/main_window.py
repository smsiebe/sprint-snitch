"""Main application window.

Follows AuraRouter's ``AuraRouterWindow`` patterns:

- ``_build_ui()`` / ``_wire_signals()`` for construction
- ``_on_*()`` naming for all slot methods
- ``QThread`` + ``QObject.moveToThread()`` for the background worker
- ``deleteLater()`` cleanup on both thread and worker
- ``error`` / ``finished`` signals both connect to ``thread.quit``
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from PySide6.QtCore import QThread
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QMainWindow,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from sprint_snitch.gui.input_panel import InputPanel
from sprint_snitch.gui.progress_panel import ProgressPanel
from sprint_snitch.gui.report_viewer import ReportViewer
from sprint_snitch.gui.workers import AnalysisWorker
from sprint_snitch.models.data import SprintReport

logger = logging.getLogger(__name__)

# Tab indices for programmatic switching.
_TAB_INPUT = 0
_TAB_PROGRESS = 1
_TAB_REPORT = 2


class SprintSnitchWindow(QMainWindow):
    """Top-level window for Sprint Snitch.

    Houses three tabbed panels (Input, Progress, Report) and manages the
    lifecycle of the background :class:`AnalysisWorker` thread.
    """

    def __init__(self) -> None:
        super().__init__()
        self._thread: Optional[QThread] = None
        self._worker: Optional[AnalysisWorker] = None

        self.setWindowTitle("Sprint Snitch")
        self.setMinimumSize(900, 600)

        self._build_ui()
        self._wire_signals()
        self._setup_shortcuts()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)

        # ---- Tab widget ------------------------------------------------------
        self._tabs = QTabWidget()

        self._input_panel = InputPanel()
        self._tabs.addTab(self._input_panel, "Input")

        self._progress_panel = ProgressPanel()
        self._tabs.addTab(self._progress_panel, "Progress")

        self._report_viewer = ReportViewer()
        self._tabs.addTab(self._report_viewer, "Report")

        root_layout.addWidget(self._tabs)

        # ---- Status bar ------------------------------------------------------
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Ready")

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _wire_signals(self) -> None:
        self._input_panel.analyze_requested.connect(self._on_analyze)
        self._progress_panel.cancel_requested.connect(self._on_cancel)

    # ------------------------------------------------------------------
    # Keyboard shortcuts
    # ------------------------------------------------------------------

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+Return"), self, self._on_shortcut_analyze)
        QShortcut(QKeySequence("Escape"), self, self._on_cancel)

    def _on_shortcut_analyze(self) -> None:
        """Trigger analyze from the keyboard only when on the Input tab."""
        if self._tabs.currentIndex() == _TAB_INPUT:
            self._input_panel._on_analyze_clicked()

    # ------------------------------------------------------------------
    # Analysis lifecycle
    # ------------------------------------------------------------------

    def _on_analyze(
        self,
        urls: list[str],
        date_from: datetime,
        date_to: datetime,
        use_llm: bool,
    ) -> None:
        """Create the worker + thread and kick off the analysis pipeline."""
        # Prevent double-launch.
        if self._thread and self._thread.isRunning():
            self._status_bar.showMessage("Analysis already in progress.")
            return

        # Reset panels.
        self._progress_panel.reset()
        self._report_viewer.reset()

        # Switch to the Progress tab.
        self._tabs.setCurrentIndex(_TAB_PROGRESS)

        # Disable input controls while running.
        self._input_panel.set_enabled(False)
        self._status_bar.showMessage("Analysis in progress...")

        # Build worker.
        self._worker = AnalysisWorker(
            repo_urls=urls,
            date_from=date_from,
            date_to=date_to,
            config_path=None,
            use_llm=use_llm,
            work_dir=None,
        )
        self._thread = QThread()
        self._worker.moveToThread(self._thread)

        # Wire worker signals → UI slots.
        self._thread.started.connect(self._worker.run)

        self._worker.progress.connect(self._progress_panel.on_progress)
        self._worker.repo_cloned.connect(self._progress_panel.on_repo_cloned)
        self._worker.repo_analyzed.connect(self._progress_panel.on_repo_analyzed)
        self._worker.llm_progress.connect(self._progress_panel.on_llm_progress)
        self._worker.model_tried.connect(self._progress_panel.on_model_tried)

        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)

        # Both finished and error must quit the thread (AuraRouter pattern).
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)

        # Thread cleanup after it actually finishes.
        self._thread.finished.connect(self._cleanup_thread)

        self._thread.start()

    def _on_finished(self, report: SprintReport) -> None:
        """Handle successful pipeline completion."""
        self._progress_panel.on_finished()
        self._report_viewer.on_report_ready(report)

        # Switch to the Report tab.
        self._tabs.setCurrentIndex(_TAB_REPORT)

        self._input_panel.set_enabled(True)
        self._status_bar.showMessage("Analysis complete.")

    def _on_error(self, message: str) -> None:
        """Handle pipeline failure."""
        self._progress_panel.on_error(message)
        self._input_panel.set_enabled(True)
        self._status_bar.showMessage(f"Error: {message}")

    def _on_cancel(self) -> None:
        """Cancel a running analysis (Escape key or Cancel button)."""
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(5000)
            self._cleanup_thread()
            self._input_panel.set_enabled(True)
            self._status_bar.showMessage("Analysis cancelled.")

    # ------------------------------------------------------------------
    # Thread cleanup (AuraRouter deleteLater pattern)
    # ------------------------------------------------------------------

    def _cleanup_thread(self) -> None:
        """Release the worker and thread via deleteLater()."""
        if self._worker:
            self._worker.deleteLater()
            self._worker = None
        if self._thread:
            self._thread.deleteLater()
            self._thread = None

    # ------------------------------------------------------------------
    # Window close
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        """Ensure the background thread is stopped before closing."""
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(5000)
        self._cleanup_thread()
        event.accept()
