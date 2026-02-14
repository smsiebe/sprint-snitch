"""Tests for PDF export (HTML rendering + PDF file generation)."""

from datetime import datetime
from pathlib import Path

import pytest

from sprint_snitch.models.data import (
    AuthorMetrics,
    ChangeTypeStats,
    ChurnedFile,
    CommitCategory,
    ContributorSummary,
    DailyActivity,
    FileTypeBreakdown,
    RepoAnalysis,
    RepoSummary,
    SprintReport,
)
from sprint_snitch.reporting.pdf_export import (
    _escape,
    _render_html_bar_chart,
    _render_html_table,
    render_html,
    save_pdf,
)


# ---------------------------------------------------------------------------
# Fixtures (mirrors test_markdown_export.py)
# ---------------------------------------------------------------------------


def _make_report(**kwargs):
    defaults = dict(
        date_from=datetime(2025, 1, 1),
        date_to=datetime(2025, 1, 14),
        generated_at=datetime(2025, 1, 14, 12, 0),
    )
    defaults.update(kwargs)
    return SprintReport(**defaults)


def _make_full_report():
    am = AuthorMetrics(
        name="Alice", email="a@e.com", lines_added=200, lines_removed=50,
    )
    analysis = RepoAnalysis(
        repo_url="https://github.com/org/myrepo",
        repo_name="myrepo",
        date_from=datetime(2025, 1, 1),
        date_to=datetime(2025, 1, 14),
        authors={"a@e.com": am},
        total_commits=5,
        total_lines_added=200,
        total_lines_removed=50,
        files_changed=["main.py", "utils.py"],
    )
    rs = RepoSummary(
        repo_url="https://github.com/org/myrepo",
        repo_name="myrepo",
        analysis=analysis,
        overall_summary="Repo did great things.",
        key_areas=["backend", "tests"],
    )
    cs = ContributorSummary(
        name="Alice", email="a@e.com", metrics=am,
        qualitative_summary="Alice focused on backend improvements.",
    )
    return _make_report(
        repos=[rs],
        contributors=[cs],
        overall_narrative="A productive sprint focused on backend.",
        token_usage={"input_tokens": 100, "output_tokens": 50, "calls": 3},
    )


def _make_enriched_report():
    """Build a report with enrichment data populated."""
    am = AuthorMetrics(
        name="Alice", email="a@e.com", lines_added=200, lines_removed=50,
    )
    analysis = RepoAnalysis(
        repo_url="https://github.com/org/myrepo",
        repo_name="myrepo",
        date_from=datetime(2025, 1, 1),
        date_to=datetime(2025, 1, 14),
        authors={"a@e.com": am},
        total_commits=5, total_lines_added=200, total_lines_removed=50,
        files_changed=["main.py", "utils.py", "README.md"],
        file_type_breakdown=[
            FileTypeBreakdown("Python", ".py", 2, 180, 40, 4),
            FileTypeBreakdown("Documentation", ".md", 1, 20, 10, 1),
        ],
        commit_categories=[
            CommitCategory("feat", 3),
            CommitCategory("fix", 2),
        ],
        daily_activity=[
            DailyActivity(datetime(2025, 1, 6), 3, 100, 20, ["a@e.com"]),
            DailyActivity(datetime(2025, 1, 7), 2, 100, 30, ["a@e.com"]),
        ],
        change_type_stats=ChangeTypeStats(
            files_added=1, files_modified=3, files_deleted=0, files_renamed=0,
        ),
        churned_files=[ChurnedFile("main.py", 4, 150, 30)],
        peak_day=DailyActivity(datetime(2025, 1, 6), 3, 100, 20, ["a@e.com"]),
        weekday_commits=5,
        weekend_commits=0,
    )
    rs = RepoSummary(
        repo_url="https://github.com/org/myrepo",
        repo_name="myrepo",
        analysis=analysis,
    )
    cs = ContributorSummary(name="Alice", email="a@e.com", metrics=am)
    return _make_report(repos=[rs], contributors=[cs])


# ---------------------------------------------------------------------------
# Helper tests
# ---------------------------------------------------------------------------


def test_escape_html_entities():
    assert _escape("<script>") == "&lt;script&gt;"
    assert _escape("a & b") == "a &amp; b"
    assert _escape('"quoted"') == "&quot;quoted&quot;"
    assert _escape("it's") == "it&#x27;s"


def test_render_html_table_basic():
    html = _render_html_table(["Name", "Value"], [["Alice", "10"], ["Bob", "20"]])
    assert "<table" in html
    assert "<th" in html
    assert "Name" in html
    assert "Value" in html
    assert "Alice" in html
    assert "10" in html
    assert "Bob" in html
    assert "20" in html


def test_render_html_table_escapes_content():
    html = _render_html_table(["Col"], [["<b>bold</b>"]])
    assert "&lt;b&gt;" in html
    assert "<b>bold</b>" not in html


def test_render_html_table_zebra_striping():
    html = _render_html_table(["X"], [["a"], ["b"], ["c"]])
    # Row 0 = normal, row 1 = alt, row 2 = normal
    assert "f5f5f5" in html  # alt row background


def test_render_html_bar_chart_basic():
    data = {"Alice": 10, "Bob": 5}
    html = _render_html_bar_chart(data, "Test Chart")
    assert "Test Chart" in html
    assert "Alice" in html
    assert "Bob" in html
    assert "10" in html
    assert "5" in html
    assert "<table" in html


def test_render_html_bar_chart_single_item():
    data = {"Alice": 10}
    html = _render_html_bar_chart(data, "Solo")
    assert "Alice" in html
    assert "300px" in html  # full bar width


def test_render_html_bar_chart_zero_values():
    data = {"Alice": 0, "Bob": 0}
    html = _render_html_bar_chart(data, "Zeros")
    assert "Alice" in html
    assert "Bob" in html
    assert "width:0px" in html


def test_render_html_bar_chart_empty():
    assert _render_html_bar_chart({}, "Empty") == ""


# ---------------------------------------------------------------------------
# Section rendering tests (via render_html)
# ---------------------------------------------------------------------------


def test_render_html_header():
    report = _make_full_report()
    html = render_html(report)
    assert "<h1>Sprint Report: 2025-01-01" in html
    assert "2025-01-14" in html
    assert "myrepo" in html


def test_render_html_executive_summary():
    report = _make_full_report()
    html = render_html(report)
    assert "<h2>Executive Summary</h2>" in html
    assert "A productive sprint focused on backend." in html


def test_render_html_empty_narrative():
    report = _make_report(overall_narrative="")
    html = render_html(report)
    assert "No executive summary available" in html


def test_render_html_repo_section():
    report = _make_full_report()
    html = render_html(report)
    assert "<h2>Repositories</h2>" in html
    assert "myrepo" in html
    assert "Total commits" in html
    assert "5" in html
    assert "+200" in html


def test_render_html_repo_key_areas():
    report = _make_full_report()
    html = render_html(report)
    assert "Key areas of change" in html
    assert "backend" in html
    assert "tests" in html


def test_render_html_contributor_section():
    report = _make_full_report()
    html = render_html(report)
    assert "<h2>Contributors</h2>" in html
    assert "Alice" in html
    assert "Alice focused on backend improvements." in html


def test_render_html_contributor_per_repo_table():
    """Contributor section should include a per-repository breakdown table."""
    report = _make_full_report()
    html = render_html(report)
    assert "Repository" in html
    assert "myrepo" in html


def test_render_html_contributor_multi_repo():
    """With 2 repos, contributor table shows per-repo breakdown."""
    am1 = AuthorMetrics(name="Alice", email="a@e.com", lines_added=150, lines_removed=30)
    am2 = AuthorMetrics(name="Alice", email="a@e.com", lines_added=50, lines_removed=20)
    a1 = RepoAnalysis(
        repo_url="u1", repo_name="repo-a",
        date_from=datetime(2025, 1, 1), date_to=datetime(2025, 1, 14),
        authors={"a@e.com": am1},
    )
    a2 = RepoAnalysis(
        repo_url="u2", repo_name="repo-b",
        date_from=datetime(2025, 1, 1), date_to=datetime(2025, 1, 14),
        authors={"a@e.com": am2},
    )
    merged = AuthorMetrics(
        name="Alice", email="a@e.com", lines_added=200, lines_removed=50,
    )
    cs = ContributorSummary(name="Alice", email="a@e.com", metrics=merged)
    report = _make_report(
        repos=[
            RepoSummary(repo_url="u1", repo_name="repo-a", analysis=a1),
            RepoSummary(repo_url="u2", repo_name="repo-b", analysis=a2),
        ],
        contributors=[cs],
    )
    html = render_html(report)
    assert "repo-a" in html
    assert "repo-b" in html
    assert "+150" in html
    assert "-30" in html
    assert "+50" in html
    assert "-20" in html


def test_render_html_activity_overview():
    report = _make_full_report()
    html = render_html(report)
    assert "<h2>Activity Overview</h2>" in html
    assert "Lines Changed per Contributor" in html


def test_render_html_footer():
    report = _make_full_report()
    html = render_html(report)
    assert "Sprint Snitch v0.1.0" in html
    assert "LLM usage" in html
    assert "100 input tokens" in html


def test_render_html_full_document_structure():
    report = _make_full_report()
    html = render_html(report)
    assert "<!DOCTYPE html>" in html
    assert "<html>" in html
    assert "<head>" in html
    assert "<style>" in html
    assert "<body>" in html
    assert "</body>" in html
    assert "</html>" in html


def test_render_html_empty_report():
    report = _make_report()
    html = render_html(report)
    assert "<h1>Sprint Report" in html
    assert "No executive summary" in html
    # Should not contain repo/contributor sections
    assert "<h2>Repositories</h2>" not in html
    assert "<h2>Contributors</h2>" not in html


def test_render_html_special_characters():
    am = AuthorMetrics(name="O'Brien<>&\"", email="o@e.com")
    cs = ContributorSummary(name="O'Brien<>&\"", email="o@e.com", metrics=am)
    report = _make_report(contributors=[cs])
    html = render_html(report)
    assert "<script>" not in html
    assert "&lt;" in html
    assert "&amp;" in html
    assert "&quot;" in html


# ---------------------------------------------------------------------------
# Enriched section tests
# ---------------------------------------------------------------------------


def test_render_html_file_type_breakdown():
    report = _make_enriched_report()
    html = render_html(report)
    assert "<h2>File Type Breakdown</h2>" in html
    assert "Python" in html
    assert "Documentation" in html
    assert "Lines Changed by File Type" in html


def test_render_html_commit_categories():
    report = _make_enriched_report()
    html = render_html(report)
    assert "<h2>Commit Categories</h2>" in html
    assert "feat" in html
    assert "fix" in html
    assert "Commit Distribution" in html


def test_render_html_timeline():
    report = _make_enriched_report()
    html = render_html(report)
    assert "<h2>Sprint Timeline</h2>" in html
    assert "Daily Commit Activity" in html
    assert "Peak Day" in html
    assert "Weekday commits" in html


def test_render_html_change_type_stats():
    report = _make_enriched_report()
    html = render_html(report)
    assert "<h2>Change Analysis</h2>" in html
    assert "Change Types" in html
    assert "Most Changed Files" in html
    assert "main.py" in html


def test_render_html_enriched_sections_absent_when_empty():
    report = _make_full_report()
    html = render_html(report)
    assert "File Type Breakdown" not in html
    assert "Commit Categories" not in html
    assert "Sprint Timeline" not in html
    assert "Change Analysis" not in html


def test_render_html_section_ordering():
    report = _make_enriched_report()
    html = render_html(report)
    activity_pos = html.index("Activity Overview")
    file_type_pos = html.index("File Type Breakdown")
    footer_pos = html.index("Sprint Snitch v0.1.0")
    assert activity_pos < file_type_pos < footer_pos


# ---------------------------------------------------------------------------
# PDF generation test
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def _qapp():
    """Ensure a QGuiApplication exists for Qt-dependent tests."""
    from PySide6.QtGui import QGuiApplication

    app = QGuiApplication.instance()
    if app is None:
        app = QGuiApplication([])
    return app


def test_save_pdf_creates_file(tmp_path, _qapp):
    """Test that save_pdf creates a valid PDF file."""
    report = _make_full_report()
    output_path = tmp_path / "test_report.pdf"
    result = save_pdf(report, output_path)

    assert result.exists()
    assert result.suffix == ".pdf"
    assert result.stat().st_size > 0

    # Check PDF magic bytes
    with open(result, "rb") as f:
        header = f.read(5)
    assert header == b"%PDF-"


def test_save_pdf_enriched_report(tmp_path, _qapp):
    """PDF with all enriched sections should not error and produce valid output."""
    report = _make_enriched_report()
    output_path = tmp_path / "enriched_report.pdf"
    result = save_pdf(report, output_path)

    assert result.exists()
    assert result.stat().st_size > 0
