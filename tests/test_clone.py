"""Tests for git clone/fetch operations."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sprint_snitch.git_analysis.clone import (
    GitError,
    _normalize_repo_url,
    _repo_dir_name,
    clone_or_fetch,
)


# -- _normalize_repo_url tests ------------------------------------------------


def test_normalize_full_https_url():
    """Full HTTPS URLs should pass through unchanged."""
    url = "https://github.com/org/repo.git"
    assert _normalize_repo_url(url) == url


def test_normalize_full_ssh_url():
    """Full SSH URLs should pass through unchanged."""
    url = "git@github.com:org/repo.git"
    assert _normalize_repo_url(url) == url


def test_normalize_shorthand_owner_repo():
    """Plain owner/repo shorthand should expand to HTTPS GitHub URL."""
    assert _normalize_repo_url("smsiebe/sprint-snitch") == (
        "https://github.com/smsiebe/sprint-snitch.git"
    )


def test_normalize_shorthand_with_description():
    """owner/repo with appended description should strip the description."""
    raw = 'smsiebe/sprint-snitch: Application to automatically create an "end of sprint" report'
    assert _normalize_repo_url(raw) == (
        "https://github.com/smsiebe/sprint-snitch.git"
    )


def test_normalize_strips_whitespace():
    assert _normalize_repo_url("  org/repo  ") == (
        "https://github.com/org/repo.git"
    )


# -- _repo_dir_name tests -----------------------------------------------------


def test_repo_dir_name_https():
    assert _repo_dir_name("https://github.com/org/repo.git") == "github.com_org_repo"


def test_repo_dir_name_ssh():
    assert _repo_dir_name("git@github.com:org/repo.git") == "github.com_org_repo"


def test_repo_dir_name_no_extension():
    assert _repo_dir_name("https://github.com/org/repo") == "github.com_org_repo"


def test_clone_or_fetch_clone_new(tmp_path):
    """When repo dir does not exist, git clone should be invoked."""
    with patch("sprint_snitch.git_analysis.clone.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = clone_or_fetch("https://github.com/org/repo.git", str(tmp_path))
    # Verify git clone was called
    args = mock_run.call_args[0][0]
    assert args[0] == "git"
    assert args[1] == "clone"
    assert "github.com/org/repo.git" in args[2]


def test_clone_or_fetch_fetch_existing(tmp_path):
    """When repo dir exists with .git/, git fetch should be invoked."""
    repo_dir = tmp_path / "github.com_org_repo"
    repo_dir.mkdir()
    (repo_dir / ".git").mkdir()

    with patch("sprint_snitch.git_analysis.clone.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = clone_or_fetch("https://github.com/org/repo.git", str(tmp_path))
    args = mock_run.call_args[0][0]
    assert args[0] == "git"
    assert args[1] == "fetch"
    assert args[2] == "--all"


def test_clone_or_fetch_git_error(tmp_path):
    """Non-zero exit code should raise GitError."""
    with patch("sprint_snitch.git_analysis.clone.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=128, stdout="", stderr="fatal: repository not found"
        )
        with pytest.raises(GitError) as exc_info:
            clone_or_fetch("https://github.com/org/bad.git", str(tmp_path))
    assert exc_info.value.returncode == 128
    assert "fatal" in exc_info.value.stderr
