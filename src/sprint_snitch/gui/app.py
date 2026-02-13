"""QApplication bootstrap.

Provides the ``launch_gui()`` entry point that creates the Qt application,
shows the main window, and runs the event loop.
"""

from __future__ import annotations


def launch_gui() -> None:
    """Create the QApplication, show the main window, and enter the event loop.

    This is the single entry point for the Sprint Snitch GUI, called from
    the ``gui`` CLI subcommand (see ``sprint_snitch.__main__``).
    """
    from sprint_snitch.gui import check_pyside6

    check_pyside6()

    import sys

    from PySide6.QtWidgets import QApplication

    from sprint_snitch.gui.main_window import SprintSnitchWindow

    app = QApplication(sys.argv)
    app.setApplicationName("Sprint Snitch")

    window = SprintSnitchWindow()
    window.show()

    sys.exit(app.exec())
