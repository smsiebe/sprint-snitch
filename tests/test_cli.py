"""Tests for CLI entry point."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sprint_snitch.__main__ import main


def test_main_help():
    """--help exits cleanly with code 0."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0


def test_main_gui_subcommand():
    """'gui' subcommand should call launch_gui()."""
    mock_launch = MagicMock()
    with patch.dict("sys.modules", {}):
        with patch("sprint_snitch.gui.app.launch_gui", mock_launch, create=True):
            main(["gui"])
    mock_launch.assert_called_once()


def test_main_headless_no_repos():
    """No repos and no subcommand should error."""
    with pytest.raises(SystemExit) as exc_info:
        main([])
    assert exc_info.value.code == 2


def test_main_headless_quantitative(tmp_path):
    """Headless with --no-llm should pass use_llm=False."""
    output_file = tmp_path / "report.md"

    with patch("sprint_snitch.__main__._run_headless") as mock_run:
        main([
            "--repos", "https://github.com/org/repo.git",
            "--from-date", "2025-01-01",
            "--to-date", "2025-01-14",
            "--no-llm",
            "-o", str(output_file),
        ])
        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["use_llm"] is False
        assert call_kwargs["output_path"] == output_file


def test_main_headless_with_llm(tmp_path):
    """Without --no-llm, use_llm should be True."""
    output_file = tmp_path / "report.md"

    with patch("sprint_snitch.__main__._run_headless") as mock_run:
        main([
            "--repos", "https://github.com/org/repo.git",
            "--from-date", "2025-01-01",
            "--to-date", "2025-01-14",
            "-o", str(output_file),
        ])
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["use_llm"] is True


def test_main_date_defaults(tmp_path):
    """Without date args, defaults to last 14 days."""
    output_file = tmp_path / "report.md"

    with patch("sprint_snitch.__main__._run_headless") as mock_run:
        main([
            "--repos", "https://github.com/org/repo.git",
            "--no-llm",
            "-o", str(output_file),
        ])
        call_kwargs = mock_run.call_args[1]
        date_from = call_kwargs["date_from"]
        date_to = call_kwargs["date_to"]
        delta = date_to - date_from
        assert 13 <= delta.days <= 14


def test_main_git_error_exits_1(tmp_path):
    """Git failures should result in exit code 1."""
    output_file = tmp_path / "report.md"

    from sprint_snitch.git_analysis.clone import GitError

    with patch(
        "sprint_snitch.__main__._run_headless",
        side_effect=GitError("clone failed", 128, "fatal"),
    ):
        with pytest.raises(SystemExit) as exc_info:
            main([
                "--repos", "https://github.com/org/bad.git",
                "--no-llm",
                "-o", str(output_file),
            ])
        assert exc_info.value.code == 1
