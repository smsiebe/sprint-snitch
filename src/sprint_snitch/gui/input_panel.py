"""Repository URL and date range input panel.

Provides the primary user-facing input form: repository URLs, date range
selection, LLM toggle, and the "Analyze Sprint" action button.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from PySide6.QtCore import QDate, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDateEdit,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class InputPanel(QWidget):
    """Input form for sprint analysis parameters.

    Emits
    -----
    analyze_requested(urls, date_from, date_to, use_llm)
        Fired when the user clicks "Analyze Sprint" and validation passes.
        ``urls`` is a ``list[str]``, ``date_from``/``date_to`` are Python
        ``datetime`` objects, ``use_llm`` is ``bool``.
    """

    analyze_requested = Signal(list, object, object, bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self._wire_signals()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # ---- Repository URLs -------------------------------------------------
        layout.addWidget(QLabel("Repository URLs (one per line):"))

        self._url_input = QTextEdit()
        self._url_input.setPlaceholderText(
            "https://github.com/org/repo-a.git\n"
            "https://github.com/org/repo-b.git\n"
            "git@github.com:org/repo-c.git"
        )
        self._url_input.setMinimumHeight(90)
        self._url_input.setMaximumHeight(140)
        layout.addWidget(self._url_input)

        # ---- Date range ------------------------------------------------------
        date_row = QHBoxLayout()

        date_row.addWidget(QLabel("From:"))
        self._date_from = QDateEdit()
        self._date_from.setCalendarPopup(True)
        self._date_from.setDisplayFormat("yyyy-MM-dd")
        default_from = QDate.currentDate().addDays(-14)
        self._date_from.setDate(default_from)
        date_row.addWidget(self._date_from)

        date_row.addSpacing(16)

        date_row.addWidget(QLabel("To:"))
        self._date_to = QDateEdit()
        self._date_to.setCalendarPopup(True)
        self._date_to.setDisplayFormat("yyyy-MM-dd")
        self._date_to.setDate(QDate.currentDate())
        date_row.addWidget(self._date_to)

        date_row.addStretch()
        layout.addLayout(date_row)

        # ---- LLM toggle ------------------------------------------------------
        self._llm_checkbox = QCheckBox("Include AI-powered qualitative analysis")

        # Default state depends on AuraRouter availability.
        llm_available = self._check_llm_available()
        self._llm_checkbox.setChecked(llm_available)
        if not llm_available:
            self._llm_checkbox.setToolTip(
                "AuraRouter is not configured. Install aurarouter and set up "
                "auraconfig.yaml to enable AI summaries."
            )
        layout.addWidget(self._llm_checkbox)

        # ---- Analyze button ---------------------------------------------------
        self._analyze_btn = QPushButton("Analyze Sprint")
        self._analyze_btn.setFixedHeight(38)
        self._analyze_btn.setStyleSheet(
            "QPushButton { font-size: 14px; font-weight: bold; }"
        )
        layout.addWidget(self._analyze_btn)

        # ---- AuraRouter status label ------------------------------------------
        self._status_label = QLabel()
        self._status_label.setStyleSheet("color: gray; font-size: 11px;")
        if llm_available:
            self._status_label.setText("AuraRouter: connected")
        else:
            self._status_label.setText(
                "AuraRouter: not available (quantitative-only reports)"
            )
        layout.addWidget(self._status_label)

        layout.addStretch()

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _wire_signals(self) -> None:
        self._analyze_btn.clicked.connect(self._on_analyze_clicked)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_analyze_clicked(self) -> None:
        """Validate inputs and emit ``analyze_requested`` if everything is OK."""
        # Parse URLs — one per line, strip blanks.
        raw_text = self._url_input.toPlainText()
        urls = [
            line.strip()
            for line in raw_text.splitlines()
            if line.strip()
        ]

        if not urls:
            QMessageBox.warning(
                self,
                "Validation Error",
                "Please enter at least one repository URL.",
            )
            return

        # Convert QDate to Python datetime.
        qdate_from = self._date_from.date()
        qdate_to = self._date_to.date()

        date_from = datetime(qdate_from.year(), qdate_from.month(), qdate_from.day())
        date_to = datetime(qdate_to.year(), qdate_to.month(), qdate_to.day())

        if date_from >= date_to:
            QMessageBox.warning(
                self,
                "Validation Error",
                "The 'From' date must be earlier than the 'To' date.",
            )
            return

        use_llm = self._llm_checkbox.isChecked()

        self.analyze_requested.emit(urls, date_from, date_to, use_llm)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _check_llm_available() -> bool:
        """Return True if FabricBridge can initialise without error."""
        try:
            from sprint_snitch.llm_integration.fabric_bridge import FabricBridge
            bridge = FabricBridge()
            return bridge.is_available()
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable all interactive controls."""
        self._url_input.setEnabled(enabled)
        self._date_from.setEnabled(enabled)
        self._date_to.setEnabled(enabled)
        self._llm_checkbox.setEnabled(enabled)
        self._analyze_btn.setEnabled(enabled)
