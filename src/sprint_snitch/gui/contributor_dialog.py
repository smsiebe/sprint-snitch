"""Contributor reconciliation dialog.

Shows discovered git identities and lets the user merge duplicates or rename
contributors before the analysis phase runs.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from sprint_snitch.models.data import DiscoveredIdentity

logger = logging.getLogger(__name__)


class ContributorReconciliationDialog(QDialog):
    """Modal dialog for merging/renaming contributor identities.

    Parameters
    ----------
    identities:
        List of discovered (name, email) pairs from commit extraction.
    parent:
        Parent widget.
    """

    def __init__(
        self,
        identities: list[DiscoveredIdentity],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._identities = list(identities)
        # Internal mapping: original_email -> (target_name, target_email)
        # Only populated for emails that have been remapped.
        self._mapping: dict[str, tuple[str, str]] = {}
        # Rows: each entry is a "group" — a list of DiscoveredIdentity that
        # have been merged together.  The first element is the canonical one.
        self._groups: list[list[DiscoveredIdentity]] = [
            [ident] for ident in self._identities
        ]

        self.setWindowTitle("Contributor Reconciliation")
        self.setMinimumSize(620, 400)

        self._build_ui()
        self._populate_table()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Header text
        header = QLabel(
            "The following identities were found in the extracted commits.\n"
            "Merge duplicates or rename contributors as needed."
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["Name", "Email", "Commits"])
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        h = self._table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(self._table)

        # Action buttons
        btn_row = QHBoxLayout()

        self._merge_btn = QPushButton("Merge Selected")
        self._merge_btn.setToolTip("Merge 2 or more selected identities into one.")
        self._merge_btn.clicked.connect(self._on_merge)
        btn_row.addWidget(self._merge_btn)

        self._rename_btn = QPushButton("Rename...")
        self._rename_btn.setToolTip("Change the display name of the selected contributor.")
        self._rename_btn.clicked.connect(self._on_rename)
        btn_row.addWidget(self._rename_btn)

        self._undo_btn = QPushButton("Undo All")
        self._undo_btn.setToolTip("Reset all merges and renames.")
        self._undo_btn.clicked.connect(self._on_undo)
        btn_row.addWidget(self._undo_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Accept button
        self._accept_btn = QPushButton("Accept && Continue")
        self._accept_btn.setFixedHeight(36)
        self._accept_btn.setStyleSheet(
            "QPushButton { font-size: 13px; font-weight: bold; }"
        )
        self._accept_btn.clicked.connect(self.accept)
        layout.addWidget(self._accept_btn)

    # ------------------------------------------------------------------
    # Table population
    # ------------------------------------------------------------------

    def _populate_table(self) -> None:
        """Rebuild the table from the current group state."""
        self._table.setRowCount(len(self._groups))

        for row, group in enumerate(self._groups):
            canonical = group[0]
            total_commits = sum(ident.commit_count for ident in group)

            # Name — show canonical name; if merged, add (+ N merged) suffix
            name_text = canonical.name
            if len(group) > 1:
                name_text += f"  (+{len(group) - 1} merged)"

            name_item = QTableWidgetItem(name_text)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(row, 0, name_item)

            # Email — show canonical email; if merged, show tooltip with all
            email_item = QTableWidgetItem(canonical.email)
            email_item.setFlags(email_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if len(group) > 1:
                all_emails = ", ".join(ident.email for ident in group)
                email_item.setToolTip(f"Merged emails: {all_emails}")
            self._table.setItem(row, 1, email_item)

            # Commits
            commits_item = QTableWidgetItem(str(total_commits))
            commits_item.setFlags(commits_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            commits_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self._table.setItem(row, 2, commits_item)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_merge(self) -> None:
        """Merge selected rows into one group."""
        selected_rows = sorted(set(idx.row() for idx in self._table.selectedIndexes()))
        if len(selected_rows) < 2:
            QMessageBox.information(
                self,
                "Merge",
                "Select 2 or more rows to merge.",
            )
            return

        # Pick the canonical identity (one with the most commits)
        groups_to_merge = [self._groups[r] for r in selected_rows]
        merged: list[DiscoveredIdentity] = []
        for g in groups_to_merge:
            merged.extend(g)

        # Sort by commit count descending — first becomes canonical
        merged.sort(key=lambda d: -d.commit_count)

        # Remove old groups (reverse order to preserve indices)
        for r in reversed(selected_rows):
            del self._groups[r]

        # Insert the merged group at the first selected position
        insert_at = min(selected_rows)
        if insert_at > len(self._groups):
            insert_at = len(self._groups)
        self._groups.insert(insert_at, merged)

        self._populate_table()

    def _on_rename(self) -> None:
        """Rename the display name of the first selected row."""
        selected_rows = sorted(set(idx.row() for idx in self._table.selectedIndexes()))
        if len(selected_rows) != 1:
            QMessageBox.information(
                self,
                "Rename",
                "Select exactly 1 row to rename.",
            )
            return

        row = selected_rows[0]
        group = self._groups[row]
        current_name = group[0].name

        new_name, ok = QInputDialog.getText(
            self,
            "Rename Contributor",
            "Display name:",
            text=current_name,
        )
        if ok and new_name.strip():
            group[0] = DiscoveredIdentity(
                name=new_name.strip(),
                email=group[0].email,
                commit_count=group[0].commit_count,
            )
            self._populate_table()

    def _on_undo(self) -> None:
        """Reset all merges and renames."""
        self._groups = [[ident] for ident in self._identities]
        self._populate_table()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_mapping(self) -> dict[str, tuple[str, str]]:
        """Build the identity mapping from the current group state.

        Returns
        -------
        dict[str, tuple[str, str]]
            Maps original email → (canonical_name, canonical_email).
            Only includes entries where the identity actually changed
            (merged or renamed).
        """
        mapping: dict[str, tuple[str, str]] = {}
        for group in self._groups:
            canonical = group[0]
            for ident in group:
                # Include if email differs (merge) or name differs (rename)
                if ident.email != canonical.email or ident.name != canonical.name:
                    mapping[ident.email] = (canonical.name, canonical.email)
        return mapping
