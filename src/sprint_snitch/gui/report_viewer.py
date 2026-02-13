"""Report display and export controls.

Renders a completed SprintReport as Markdown text in a read-only viewer
and provides "Export to Markdown" and "Copy to Clipboard" actions.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from sprint_snitch.models.data import SprintReport
from sprint_snitch.reporting.markdown_export import render_markdown, save_markdown
from sprint_snitch.reporting.pdf_export import save_pdf


class ReportViewer(QWidget):
    """Displays the rendered sprint report with export controls.

    Call :meth:`on_report_ready` with a :class:`SprintReport` to populate
    the viewer.  The user can then export to a ``.md`` file or copy the
    full text to the clipboard.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._report: SprintReport | None = None
        self._rendered_text: str = ""
        self._build_ui()
        self._wire_signals()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # ---- Header ----------------------------------------------------------
        self._header_label = QLabel("Sprint Report")
        self._header_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(self._header_label)

        # ---- Report text view ------------------------------------------------
        self._text_view = QTextEdit()
        self._text_view.setReadOnly(True)
        self._text_view.setFont(QFont("Consolas", 10))
        self._text_view.setPlaceholderText(
            "Complete an analysis to see the report here."
        )
        layout.addWidget(self._text_view, 1)  # stretch factor 1

        # ---- Export buttons --------------------------------------------------
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._export_btn = QPushButton("Export to Markdown...")
        self._export_btn.setEnabled(False)
        btn_row.addWidget(self._export_btn)

        self._export_pdf_btn = QPushButton("Export to PDF...")
        self._export_pdf_btn.setEnabled(False)
        btn_row.addWidget(self._export_pdf_btn)

        self._copy_btn = QPushButton("Copy to Clipboard")
        self._copy_btn.setEnabled(False)
        btn_row.addWidget(self._copy_btn)

        layout.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _wire_signals(self) -> None:
        self._export_btn.clicked.connect(self._on_export)
        self._export_pdf_btn.clicked.connect(self._on_export_pdf)
        self._copy_btn.clicked.connect(self._on_copy)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def on_report_ready(self, report: SprintReport) -> None:
        """Populate the viewer with a completed report."""
        self._report = report
        self._rendered_text = render_markdown(report)
        self._text_view.setPlainText(self._rendered_text)
        self._export_btn.setEnabled(True)
        self._export_pdf_btn.setEnabled(True)
        self._copy_btn.setEnabled(True)

    def reset(self) -> None:
        """Clear the viewer for a fresh run."""
        self._report = None
        self._rendered_text = ""
        self._text_view.clear()
        self._export_btn.setEnabled(False)
        self._export_pdf_btn.setEnabled(False)
        self._copy_btn.setEnabled(False)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _on_export(self) -> None:
        """Open a file dialog and save the rendered Markdown."""
        if not self._report:
            return

        default_name = "sprint_report.md"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Sprint Report",
            default_name,
            "Markdown Files (*.md);;All Files (*)",
        )
        if not path:
            return  # user cancelled

        try:
            save_markdown(self._report, Path(path))
            QMessageBox.information(
                self,
                "Export Successful",
                f"Report saved to:\n{path}",
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Export Failed",
                f"Could not save report:\n{exc}",
            )

    def _on_export_pdf(self) -> None:
        """Open a file dialog and save the rendered PDF."""
        if not self._report:
            return

        default_name = "sprint_report.pdf"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Sprint Report as PDF",
            default_name,
            "PDF Files (*.pdf);;All Files (*)",
        )
        if not path:
            return  # user cancelled

        try:
            save_pdf(self._report, Path(path))
            QMessageBox.information(
                self,
                "Export Successful",
                f"Report saved to:\n{path}",
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Export Failed",
                f"Could not save PDF report:\n{exc}",
            )

    def _on_copy(self) -> None:
        """Copy the full rendered Markdown to the system clipboard."""
        if not self._rendered_text:
            return

        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self._rendered_text)
