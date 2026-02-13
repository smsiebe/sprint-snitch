"""Live progress and log console panel.

Displays a progress bar, a scrolling monospace log, and a cancel button
for the background analysis pipeline.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class ProgressPanel(QWidget):
    """Real-time progress display for the analysis worker.

    Slots connect to the various signals emitted by
    :class:`~sprint_snitch.gui.workers.AnalysisWorker`.

    Emits
    -----
    cancel_requested
        Fired when the user clicks "Cancel".
    """

    cancel_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self._wire_signals()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # ---- Header ----------------------------------------------------------
        self._header_label = QLabel("Analysis Progress")
        self._header_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(self._header_label)

        # ---- Progress bar ----------------------------------------------------
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)  # indeterminate until first progress
        self._progress_bar.setTextVisible(True)
        layout.addWidget(self._progress_bar)

        # ---- Log console -----------------------------------------------------
        self._log_view = QTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setFont(QFont("Consolas", 9))
        self._log_view.setPlaceholderText("Log output will appear here...")
        layout.addWidget(self._log_view, 1)  # stretch factor 1

        # ---- Cancel button ---------------------------------------------------
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setFixedWidth(120)
        btn_row.addWidget(self._cancel_btn)
        layout.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _wire_signals(self) -> None:
        self._cancel_btn.clicked.connect(self._on_cancel_clicked)

    # ------------------------------------------------------------------
    # Slots (intended for cross-thread signal connections)
    # ------------------------------------------------------------------

    def on_progress(self, current: int, total: int, message: str) -> None:
        """Update the progress bar and append a log line."""
        self._progress_bar.setRange(0, total)
        self._progress_bar.setValue(current)
        self._append_log(f"[{current}/{total}] {message}")

    def on_repo_cloned(self, repo_url: str) -> None:
        """Log that a repository has been cloned."""
        self._append_log(f"  Cloned: {repo_url}")

    def on_repo_analyzed(self, repo_url: str) -> None:
        """Log that a repository has been analyzed."""
        self._append_log(f"  Analyzed: {repo_url}")

    def on_llm_progress(self, description: str) -> None:
        """Log an LLM summarization step."""
        self._append_log(f"  LLM: {description}")

    def on_model_tried(
        self, role: str, model_id: str, success: bool, elapsed: float
    ) -> None:
        """Log an individual model attempt from the FabricBridge."""
        status = "OK" if success else "FAIL"
        self._append_log(
            f"    Model [{role}] {model_id}: {status} ({elapsed:.1f}s)"
        )

    def on_error(self, message: str) -> None:
        """Log an error in red-tinted text."""
        self._append_log(f"ERROR: {message}")

    def on_finished(self) -> None:
        """Mark the progress bar as complete."""
        maximum = self._progress_bar.maximum()
        if maximum > 0:
            self._progress_bar.setValue(maximum)
        self._append_log("Analysis complete.")
        self._cancel_btn.setEnabled(False)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Clear all state for a fresh run."""
        self._progress_bar.setRange(0, 0)
        self._progress_bar.setValue(0)
        self._log_view.clear()
        self._cancel_btn.setEnabled(True)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _on_cancel_clicked(self) -> None:
        self._append_log("Cancellation requested...")
        self._cancel_btn.setEnabled(False)
        self.cancel_requested.emit()

    def _append_log(self, text: str) -> None:
        """Append *text* as a new line and auto-scroll to the bottom."""
        self._log_view.append(text)
        # Force scroll to bottom.
        cursor = self._log_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._log_view.setTextCursor(cursor)
