"""Sprint Snitch GUI package — PySide6 desktop interface."""

from __future__ import annotations


def check_pyside6() -> None:
    """Verify that PySide6 is installed; raise a helpful message if not."""
    try:
        import PySide6  # noqa: F401
    except ImportError:
        raise ImportError(
            "PySide6 is required for the GUI. Install it with: pip install PySide6>=6.6"
        )
