"""Tests for diff extraction and parsing."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sprint_snitch.git_analysis.diff_extractor import (
    _enrich_with_file_content,
    _parse_git_log,
    _parse_numstat_line,
    extract_commits,
)
from sprint_snitch.models.data import CommitInfo, FileChange


_SINGLE_COMMIT_LOG = """\
COMMIT_SEP
sha:abc123def456
author_name:Alice Smith
author_email:alice@example.com
date:2025-01-10T14:30:00+00:00
message:Fix the widget

10\t3\tsrc/widget.py
5\t0\tsrc/utils.py
"""

_MULTI_COMMIT_LOG = """\
COMMIT_SEP
sha:aaa111
author_name:Alice
author_email:alice@example.com
date:2025-01-10T10:00:00+00:00
message:First commit

5\t2\tfile_a.py

COMMIT_SEP
sha:bbb222
author_name:Bob
author_email:bob@example.com
date:2025-01-11T10:00:00+00:00
message:Second commit

3\t1\tfile_b.py

COMMIT_SEP
sha:ccc333
author_name:Alice
author_email:alice@example.com
date:2025-01-12T10:00:00+00:00
message:Third commit

1\t0\tfile_c.py
"""


def test_parse_git_log_single_commit():
    commits = _parse_git_log(_SINGLE_COMMIT_LOG)
    assert len(commits) == 1
    c = commits[0]
    assert c.sha == "abc123def456"
    assert c.author_name == "Alice Smith"
    assert c.author_email == "alice@example.com"
    assert c.message == "Fix the widget"
    assert len(c.files) == 2
    assert c.files[0].path == "src/widget.py"
    assert c.files[0].lines_added == 10
    assert c.files[0].lines_removed == 3
    assert c.lines_added == 15  # 10 + 5
    assert c.lines_removed == 3  # 3 + 0


def test_parse_git_log_multiple_commits():
    commits = _parse_git_log(_MULTI_COMMIT_LOG)
    assert len(commits) == 3
    assert commits[0].sha == "aaa111"
    assert commits[1].sha == "bbb222"
    assert commits[2].sha == "ccc333"
    assert commits[0].author_name == "Alice"
    assert commits[1].author_name == "Bob"


def test_parse_git_log_empty_output():
    commits = _parse_git_log("")
    assert commits == []


def test_parse_numstat_standard():
    fc = _parse_numstat_line("10\t5\tsrc/foo.py")
    assert fc is not None
    assert fc.lines_added == 10
    assert fc.lines_removed == 5
    assert fc.path == "src/foo.py"
    assert fc.change_type == "modified"


def test_parse_numstat_binary():
    fc = _parse_numstat_line("-\t-\timage.png")
    assert fc is not None
    assert fc.lines_added == 0
    assert fc.lines_removed == 0
    assert fc.path == "image.png"


def test_parse_numstat_rename():
    fc = _parse_numstat_line("0\t0\tsrc/{old.py => new.py}")
    assert fc is not None
    assert fc.change_type == "renamed"
    assert "new.py" in fc.path
    assert "old.py" not in fc.path


def test_extract_commits_date_args():
    """Verify the git command is constructed with correct date arguments."""
    with patch("sprint_snitch.git_analysis.diff_extractor.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        with patch("sprint_snitch.git_analysis.diff_extractor._enrich_with_file_content"):
            extract_commits(
                Path("/fake/repo"),
                datetime(2025, 1, 1),
                datetime(2025, 1, 14),
            )
    args = mock_run.call_args[0][0]
    # Should have --after=2025-01-01 and --before=2025-01-15 (date_to + 1 day)
    after_arg = [a for a in args if a.startswith("--after=")][0]
    before_arg = [a for a in args if a.startswith("--before=")][0]
    assert "2025-01-01" in after_arg
    assert "2025-01-15" in before_arg


def test_enrich_with_file_content():
    """Verify git show is called and content is set."""
    fc = FileChange(path="src/main.py", lines_added=5, lines_removed=0, change_type="modified")
    commit = CommitInfo(
        sha="abc123", author_name="A", author_email="a@e.com",
        message="test", timestamp=datetime.now(), files=[fc],
    )
    with patch("sprint_snitch.git_analysis.diff_extractor.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="file content here", stderr="")
        _enrich_with_file_content(Path("/fake"), [commit])
    assert fc.content == "file content here"


def test_enrich_large_file_truncation():
    """Files larger than 50KB should be truncated."""
    fc = FileChange(path="big.py", lines_added=1, lines_removed=0, change_type="modified")
    commit = CommitInfo(
        sha="abc", author_name="A", author_email="a@e.com",
        message="big", timestamp=datetime.now(), files=[fc],
    )
    large_content = "x" * 60_000
    with patch("sprint_snitch.git_analysis.diff_extractor.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=large_content, stderr="")
        _enrich_with_file_content(Path("/fake"), [commit])
    assert len(fc.content) < 60_000
    assert "truncated" in fc.content


def test_enrich_binary_file():
    """Non-zero return code from git show should result in '(binary file)'."""
    fc = FileChange(path="image.png", lines_added=0, lines_removed=0, change_type="modified")
    commit = CommitInfo(
        sha="abc", author_name="A", author_email="a@e.com",
        message="img", timestamp=datetime.now(), files=[fc],
    )
    with patch("sprint_snitch.git_analysis.diff_extractor.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="not a text file")
        _enrich_with_file_content(Path("/fake"), [commit])
    assert fc.content == "(binary file)"
