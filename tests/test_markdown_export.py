"""Tests for Markdown export."""

from datetime import datetime
from pathlib import Path

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
from sprint_snitch.reporting.markdown_export import (
    _render_ascii_bar_chart,
    render_markdown,
    save_markdown,
)


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
        name="Alice", email="a@e.com", commit_count=5,
        files_touched=["main.py", "utils.py"], lines_added=200, lines_removed=50,
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


def test_render_header():
    report = _make_full_report()
    md = render_markdown(report)
    assert "# Sprint Report: 2025-01-01" in md
    assert "2025-01-14" in md
    assert "myrepo" in md


def test_render_executive_summary():
    report = _make_full_report()
    md = render_markdown(report)
    assert "## Executive Summary" in md
    assert "A productive sprint focused on backend." in md


def test_render_contributor_table():
    report = _make_full_report()
    md = render_markdown(report)
    assert "| Metric | Value |" in md
    assert "| Commits | 5 |" in md
    assert "+200" in md


def test_render_ascii_chart_basic():
    data = {"Alice": 10, "Bob": 5}
    chart = _render_ascii_bar_chart(data, "Test Chart")
    assert "**Test Chart**" in chart
    assert "Alice" in chart
    assert "Bob" in chart
    assert "10" in chart
    assert "5" in chart
    # Alice should have longer bar
    lines = chart.split("\n")
    alice_line = [l for l in lines if "Alice" in l][0]
    bob_line = [l for l in lines if "Bob" in l][0]
    alice_bars = alice_line.count("\u2588")
    bob_bars = bob_line.count("\u2588")
    assert alice_bars > bob_bars


def test_render_ascii_chart_single_item():
    data = {"Alice": 10}
    chart = _render_ascii_bar_chart(data, "Solo")
    assert "Alice" in chart
    assert "\u2588" in chart  # Should have a full-width bar


def test_render_ascii_chart_zero_values():
    data = {"Alice": 0, "Bob": 0}
    chart = _render_ascii_bar_chart(data, "Zeros")
    # Should not crash
    assert "Alice" in chart
    assert "Bob" in chart


def test_render_empty_report():
    report = _make_report()
    md = render_markdown(report)
    assert "# Sprint Report" in md
    assert "No executive summary" in md


def test_render_missing_narrative():
    report = _make_report(overall_narrative="")
    md = render_markdown(report)
    assert "## Executive Summary" in md
    assert "No executive summary available" in md


def test_render_special_characters():
    am = AuthorMetrics(name="O'Brien|Jr*", email="o@e.com", commit_count=1)
    cs = ContributorSummary(name="O'Brien|Jr*", email="o@e.com", metrics=am)
    report = _make_report(contributors=[cs])
    md = render_markdown(report)
    # Pipe and asterisk should be escaped
    assert "\\|" in md
    assert "\\*" in md


def test_save_markdown_writes_file(tmp_path):
    report = _make_full_report()
    out = tmp_path / "report.md"
    result = save_markdown(report, out)
    assert result == out
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "# Sprint Report" in content


# ---------------------------------------------------------------------------
# New analytics section tests
# ---------------------------------------------------------------------------


def _make_enriched_report():
    """Build a report with enrichment data populated."""
    am = AuthorMetrics(
        name="Alice", email="a@e.com", commit_count=5,
        files_touched=["main.py", "utils.py"], lines_added=200, lines_removed=50,
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
        change_type_stats=ChangeTypeStats(files_added=1, files_modified=3, files_deleted=0, files_renamed=0),
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
        change_type_stats=ChangeTypeStats(files_added=1, files_modified=3, files_deleted=0, files_renamed=0),
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


def test_render_file_type_breakdown_section():
    report = _make_enriched_report()
    md = render_markdown(report)
    assert "## File Type Breakdown" in md
    assert "Python" in md
    assert "Documentation" in md
    assert "Lines Changed by File Type" in md


def test_render_commit_categories_section():
    report = _make_enriched_report()
    md = render_markdown(report)
    assert "## Commit Categories" in md
    assert "feat" in md
    assert "fix" in md
    assert "Commit Distribution" in md


def test_render_timeline_section():
    report = _make_enriched_report()
    md = render_markdown(report)
    assert "## Sprint Timeline" in md
    assert "Daily Commit Activity" in md
    assert "Peak Day" in md
    assert "Weekday commits" in md


def test_render_change_type_stats_section():
    report = _make_enriched_report()
    md = render_markdown(report)
    assert "## Change Analysis" in md
    assert "Change Types" in md
    assert "Most Changed Files" in md
    assert "main.py" in md


def test_render_new_sections_ordering():
    """New sections should appear after Activity Overview, before footer."""
    report = _make_enriched_report()
    md = render_markdown(report)
    activity_pos = md.index("## Activity Overview")
    file_type_pos = md.index("## File Type Breakdown")
    footer_pos = md.index("---\n*Generated by")
    assert activity_pos < file_type_pos < footer_pos


def test_render_new_sections_empty_graceful():
    """When analytics fields are empty defaults, new sections are omitted."""
    report = _make_full_report()
    md = render_markdown(report)
    assert "## File Type Breakdown" not in md
    assert "## Commit Categories" not in md
    assert "## Sprint Timeline" not in md
    assert "## Change Analysis" not in md
