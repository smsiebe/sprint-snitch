"""Renders SprintReport to PDF via HTML + QTextDocument/QPdfWriter."""

from __future__ import annotations

import html
from pathlib import Path

from sprint_snitch.models.data import (
    ContributorSummary,
    RepoSummary,
    SprintReport,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render_html(report: SprintReport) -> str:
    """Produce a full HTML document for PDF rendering.

    This is a pure function — it can be tested without Qt.
    """
    sections = [
        _render_html_header(report),
        _render_html_executive_summary(report),
        _render_html_repo_sections(report),
        _render_html_contributor_sections(report),
        _render_html_activity_overview(report),
        _render_html_file_type_breakdown(report),
        _render_html_commit_categories(report),
        _render_html_timeline(report),
        _render_html_change_type_stats(report),
        _render_html_footer(report),
    ]
    content = "\n".join(s for s in sections if s)

    return (
        "<!DOCTYPE html>\n<html>\n<head>\n"
        '<meta charset="utf-8">\n'
        f"<style>\n{_get_stylesheet()}\n</style>\n"
        f"</head>\n<body>\n{content}\n</body>\n</html>"
    )


def save_pdf(report: SprintReport, output_path: Path) -> Path:
    """Write the rendered report to a PDF file using Qt.

    Requires a running ``QGuiApplication`` (or ``QApplication``).
    """
    from PySide6.QtCore import QMarginsF, QSizeF
    from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter, QTextDocument

    html_content = render_html(report)
    output_path = Path(output_path)

    writer = QPdfWriter(str(output_path))
    page_size = QPageSize(QPageSize.PageSizeId.Letter)
    margins = QMarginsF(15, 15, 15, 15)  # 15 mm margins
    writer.setPageLayout(
        QPageLayout(page_size, QPageLayout.Orientation.Portrait, margins)
    )
    writer.setResolution(300)

    doc = QTextDocument()
    doc.setHtml(html_content)

    # Match the document page size to the PDF writer's paint area so text
    # wraps correctly across pages.
    paint_rect = writer.pageLayout().paintRect(QPageLayout.Unit.Point)
    doc.setPageSize(QSizeF(paint_rect.width(), paint_rect.height()))

    doc.print_(writer)
    return output_path


# ---------------------------------------------------------------------------
# Stylesheet
# ---------------------------------------------------------------------------


def _get_stylesheet() -> str:
    return """
body {
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 10pt;
    color: #222;
}
h1 {
    font-size: 18pt;
    color: #2c3e50;
    border-bottom: 2px solid #3498db;
    padding-bottom: 6px;
}
h2 {
    font-size: 14pt;
    color: #34495e;
    margin-top: 18px;
    border-bottom: 1px solid #bdc3c7;
    padding-bottom: 4px;
}
h3 {
    font-size: 12pt;
    color: #555;
    margin-top: 14px;
}
p  { margin: 8px 0; line-height: 1.5; }
ul { margin: 8px 0; padding-left: 20px; }
li { margin: 4px 0; line-height: 1.4; }
a  { color: #3498db; }
""".strip()


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------


def _render_html_header(report: SprintReport) -> str:
    date_from = report.date_from.strftime("%Y-%m-%d")
    date_to = report.date_to.strftime("%Y-%m-%d")
    parts = [
        f"<h1>Sprint Report: {date_from} &mdash; {date_to}</h1>",
        f"<p><b>Generated:</b> {report.generated_at.strftime('%Y-%m-%d %H:%M')}</p>",
    ]
    if report.repos:
        parts.append("<p><b>Repositories analyzed:</b></p><ul>")
        for rs in report.repos:
            name = _escape(rs.repo_name)
            url = _escape(rs.repo_url)
            parts.append(f"<li><a href='{url}'>{name}</a></li>")
        parts.append("</ul>")
    return "\n".join(parts)


def _render_html_executive_summary(report: SprintReport) -> str:
    parts = ["<h2>Executive Summary</h2>"]
    if report.overall_narrative:
        parts.append(
            '<div style="background-color:#f8f9fa; border-left:3px solid #3498db;'
            ' padding:10px 14px; margin:8px 0;">'
        )
        parts.append(_narrative_to_html(report.overall_narrative))
        parts.append("</div>")
    else:
        parts.append("<p><i>No executive summary available.</i></p>")
    return "\n".join(parts)


def _render_html_repo_sections(report: SprintReport) -> str:
    if not report.repos:
        return ""
    parts = ["<h2>Repositories</h2>"]
    for rs in report.repos:
        parts.append(_render_single_repo(rs))
    return "\n".join(parts)


def _render_single_repo(rs: RepoSummary) -> str:
    a = rs.analysis
    parts = [
        f"<h3>{_escape(rs.repo_name)}</h3>",
        _render_html_table(
            ["Metric", "Value"],
            [
                ["Total commits", str(a.total_commits)],
                ["Lines added", f"+{a.total_lines_added}"],
                ["Lines removed", f"-{a.total_lines_removed}"],
                ["Files changed", str(len(a.files_changed))],
                ["Contributors", str(len(a.authors))],
            ],
        ),
    ]
    if rs.overall_summary:
        parts.append(_narrative_to_html(rs.overall_summary))
    if rs.key_areas:
        parts.append("<p><b>Key areas of change:</b></p><ul>")
        for area in rs.key_areas:
            parts.append(f"<li>{_escape(area)}</li>")
        parts.append("</ul>")
    return "\n".join(parts)


def _render_html_contributor_sections(report: SprintReport) -> str:
    if not report.contributors:
        return ""
    parts = ["<h2>Contributors</h2>"]
    for cs in report.contributors:
        parts.append(_render_single_contributor(cs))
    return "\n".join(parts)


def _render_single_contributor(cs: ContributorSummary) -> str:
    m = cs.metrics
    parts = [
        f"<h3>{_escape(cs.name)}</h3>",
        _render_html_table(
            ["Metric", "Value"],
            [
                ["Commits", str(m.commit_count)],
                ["Lines added", f"+{m.lines_added}"],
                ["Lines removed", f"-{m.lines_removed}"],
                ["Files touched", str(len(m.files_touched))],
            ],
        ),
    ]
    if cs.qualitative_summary:
        parts.append(_narrative_to_html(cs.qualitative_summary))
    return "\n".join(parts)


def _render_html_activity_overview(report: SprintReport) -> str:
    if not report.contributors:
        return ""
    parts = ["<h2>Activity Overview</h2>"]

    commit_data = {
        cs.name: cs.metrics.commit_count for cs in report.contributors
    }
    if any(v > 0 for v in commit_data.values()):
        parts.append(_render_html_bar_chart(commit_data, "Commits per Contributor"))

    lines_data = {
        cs.name: cs.metrics.lines_added + cs.metrics.lines_removed
        for cs in report.contributors
    }
    if any(v > 0 for v in lines_data.values()):
        parts.append(
            _render_html_bar_chart(lines_data, "Lines Changed per Contributor")
        )

    return "\n".join(parts)


def _render_html_file_type_breakdown(report: SprintReport) -> str:
    has_data = any(rs.analysis.file_type_breakdown for rs in report.repos)
    if not has_data:
        return ""

    parts = ["<h2>File Type Breakdown</h2>"]

    for rs in report.repos:
        breakdown = rs.analysis.file_type_breakdown
        if not breakdown:
            continue
        if len(report.repos) > 1:
            parts.append(f"<h3>{_escape(rs.repo_name)}</h3>")

        rows = [
            [b.file_type, str(b.file_count), f"+{b.lines_added}",
             f"-{b.lines_removed}", str(b.commit_count)]
            for b in breakdown
        ]
        parts.append(_render_html_table(
            ["File Type", "Files", "Lines Added", "Lines Removed", "Commits"],
            rows,
        ))

        chart_data = {
            b.file_type: b.lines_added + b.lines_removed for b in breakdown
        }
        if any(v > 0 for v in chart_data.values()):
            parts.append(_render_html_bar_chart(chart_data, "Lines Changed by File Type"))

    # Per-contributor inline summary
    contrib_parts = []
    for cs in report.contributors:
        if cs.metrics.file_type_breakdown:
            types = ", ".join(
                f"{b.file_type} (+{b.lines_added}/-{b.lines_removed})"
                for b in cs.metrics.file_type_breakdown[:5]
            )
            contrib_parts.append(f"<p><b>{_escape(cs.name)}:</b> {_escape(types)}</p>")
    if contrib_parts:
        parts.append("<h3>Per Contributor</h3>")
        parts.extend(contrib_parts)

    return "\n".join(parts)


def _render_html_commit_categories(report: SprintReport) -> str:
    has_data = any(rs.analysis.commit_categories for rs in report.repos)
    if not has_data:
        return ""

    parts = ["<h2>Commit Categories</h2>"]

    for rs in report.repos:
        categories = rs.analysis.commit_categories
        if not categories:
            continue
        if len(report.repos) > 1:
            parts.append(f"<h3>{_escape(rs.repo_name)}</h3>")

        rows = [[c.category, str(c.count)] for c in categories]
        parts.append(_render_html_table(["Category", "Count"], rows))

        chart_data = {c.category: c.count for c in categories}
        if any(v > 0 for v in chart_data.values()):
            parts.append(_render_html_bar_chart(chart_data, "Commit Distribution"))

    # Per-contributor inline summary
    contrib_lines = []
    for cs in report.contributors:
        if cs.metrics.commit_categories:
            cats = ", ".join(
                f"{c.category}: {c.count}" for c in cs.metrics.commit_categories
            )
            contrib_lines.append(
                f"<p><b>{_escape(cs.name)}</b> {_escape(cats)}</p>"
            )
    if contrib_lines:
        parts.append("<h3>Per Contributor</h3>")
        parts.extend(contrib_lines)

    return "\n".join(parts)


def _render_html_timeline(report: SprintReport) -> str:
    daily_merged: dict = {}
    total_weekday = 0
    total_weekend = 0
    peak = None

    for rs in report.repos:
        a = rs.analysis
        for da in a.daily_activity:
            key = da.date
            if key not in daily_merged:
                daily_merged[key] = {
                    "commit_count": 0, "lines_added": 0,
                    "lines_removed": 0, "authors": set(),
                }
            daily_merged[key]["commit_count"] += da.commit_count
            daily_merged[key]["lines_added"] += da.lines_added
            daily_merged[key]["lines_removed"] += da.lines_removed
            daily_merged[key]["authors"].update(da.authors)
        total_weekday += a.weekday_commits
        total_weekend += a.weekend_commits
        if a.peak_day and (peak is None or a.peak_day.commit_count > peak.commit_count):
            peak = a.peak_day

    if not daily_merged:
        return ""

    _DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    parts = ["<h2>Sprint Timeline</h2>"]

    sorted_days = sorted(daily_merged.keys())
    chart_data = {}
    for day in sorted_days:
        d = daily_merged[day]
        day_name = _DAY_NAMES[day.weekday()]
        label = f"{day.strftime('%Y-%m-%d')} ({day_name})"
        chart_data[label] = d["commit_count"]

    if any(v > 0 for v in chart_data.values()):
        parts.append(_render_html_bar_chart(chart_data, "Daily Commit Activity"))

    meta_lines = []
    if peak:
        day_name = _DAY_NAMES[peak.date.weekday()]
        meta_lines.append(
            f"<b>Peak Day:</b> {peak.date.strftime('%Y-%m-%d')} ({day_name}) "
            f"&mdash; {peak.commit_count} commits"
        )
    total = total_weekday + total_weekend
    if total > 0:
        wd_pct = round(100 * total_weekday / total)
        we_pct = 100 - wd_pct
        meta_lines.append(
            f"<b>Weekday commits:</b> {total_weekday} ({wd_pct}%) | "
            f"<b>Weekend commits:</b> {total_weekend} ({we_pct}%)"
        )
    if meta_lines:
        parts.append("<p>" + "<br>".join(meta_lines) + "</p>")

    return "\n".join(parts)


def _render_html_change_type_stats(report: SprintReport) -> str:
    has_data = any(
        (rs.analysis.change_type_stats.files_added
         + rs.analysis.change_type_stats.files_modified
         + rs.analysis.change_type_stats.files_deleted
         + rs.analysis.change_type_stats.files_renamed) > 0
        for rs in report.repos
    )
    if not has_data:
        return ""

    parts = ["<h2>Change Analysis</h2>"]

    # Per-repo change types
    repo_rows = []
    for rs in report.repos:
        s = rs.analysis.change_type_stats
        repo_rows.append([
            rs.repo_name, str(s.files_added), str(s.files_modified),
            str(s.files_deleted), str(s.files_renamed),
        ])
    parts.append("<h3>Change Types</h3>")
    parts.append(_render_html_table(
        ["Repo", "Added", "Modified", "Deleted", "Renamed"],
        repo_rows,
    ))

    # Per-contributor change types
    contributor_rows = []
    for cs in report.contributors:
        s = cs.metrics.change_type_stats
        total = s.files_added + s.files_modified + s.files_deleted + s.files_renamed
        if total > 0:
            contributor_rows.append([
                cs.name, str(s.files_added), str(s.files_modified),
                str(s.files_deleted), str(s.files_renamed),
            ])
    if contributor_rows:
        parts.append("<h3>Per Contributor</h3>")
        parts.append(_render_html_table(
            ["Contributor", "Added", "Modified", "Deleted", "Renamed"],
            contributor_rows,
        ))

    # Churned files
    all_churned = []
    for rs in report.repos:
        all_churned.extend(rs.analysis.churned_files)
    if all_churned:
        all_churned.sort(key=lambda c: c.change_count, reverse=True)
        churn_rows = [
            [cf.path, str(cf.change_count),
             f"+{cf.total_lines_added}", f"-{cf.total_lines_removed}"]
            for cf in all_churned[:10]
        ]
        parts.append("<h3>Most Changed Files</h3>")
        parts.append(_render_html_table(
            ["File", "Times Changed", "Lines Added", "Lines Removed"],
            churn_rows,
        ))

    return "\n".join(parts)


def _render_html_footer(report: SprintReport) -> str:
    parts = ['<hr>', '<p style="font-size:9pt;color:#888;font-style:italic;">']
    parts.append("Generated by Sprint Snitch v0.1.0")
    if report.token_usage:
        inp = report.token_usage.get("input_tokens", 0)
        out = report.token_usage.get("output_tokens", 0)
        calls = report.token_usage.get("calls", 0)
        if inp or out:
            parts.append(
                f"<br>LLM usage: {calls} calls, {inp} input tokens, "
                f"{out} output tokens"
            )
    parts.append("</p>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _escape(text: str) -> str:
    """Escape HTML special characters."""
    return html.escape(text, quote=True)


def _narrative_to_html(text: str) -> str:
    """Convert multi-paragraph narrative text to styled HTML paragraphs.

    Splits on blank lines and wraps each paragraph in a ``<p>`` with
    narrative styling.  Single newlines within a paragraph become
    ``<br>`` to preserve intentional line breaks (e.g. bullet lists
    inside narratives).
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    parts = []
    for para in paragraphs:
        escaped = _escape(para).replace("\n", "<br>")
        parts.append(
            f'<p style="margin:8px 0; line-height:1.5; text-align:justify;">'
            f"{escaped}</p>"
        )
    return "\n".join(parts)


_TABLE_STYLE = (
    'style="border-collapse:collapse; width:100%; margin:10px 0;"'
)
_TH_STYLE = (
    'style="background-color:#3498db; color:white; font-weight:bold; '
    'padding:6px 8px; text-align:left; border:1px solid #2980b9;"'
)
_TD_STYLE = 'style="padding:5px 8px; border:1px solid #bdc3c7;"'
_TD_ALT_STYLE = (
    'style="padding:5px 8px; border:1px solid #bdc3c7; background-color:#f5f5f5;"'
)


def _render_html_table(headers: list[str], rows: list[list[str]]) -> str:
    """Render an HTML table with styled headers and zebra-striped rows."""
    parts = [f"<table {_TABLE_STYLE}>", "<tr>"]
    for h in headers:
        parts.append(f"<th {_TH_STYLE}>{_escape(h)}</th>")
    parts.append("</tr>")

    for i, row in enumerate(rows):
        td = _TD_ALT_STYLE if i % 2 == 1 else _TD_STYLE
        parts.append("<tr>")
        for cell in row:
            parts.append(f"<td {td}>{_escape(cell)}</td>")
        parts.append("</tr>")

    parts.append("</table>")
    return "".join(parts)


_BAR_COLOR = "#3498db"
_BAR_MAX_PX = 300


def _render_html_bar_chart(
    data: dict[str, int],
    title: str,
    max_width: int = _BAR_MAX_PX,
) -> str:
    """Render a horizontal bar chart as a table with coloured cells."""
    if not data:
        return ""

    max_val = max(data.values()) if data else 0

    parts = [
        f"<p><b>{_escape(title)}</b></p>",
        '<table style="border-collapse:collapse; margin:6px 0;">',
    ]

    for label, value in data.items():
        bar_width = int(value / max_val * max_width) if max_val > 0 else 0
        parts.append(
            "<tr>"
            f'<td style="padding:2px 6px; border:none; white-space:nowrap;'
            f' font-size:9pt;">{_escape(label)}</td>'
            f'<td style="padding:2px 0; border:none; width:{max_width}px;">'
            f'<div style="background-color:{_BAR_COLOR};'
            f" width:{bar_width}px; height:14px;\"></div></td>"
            f'<td style="padding:2px 6px; border:none; font-size:9pt;">'
            f"{value}</td>"
            "</tr>"
        )

    parts.append("</table>")
    return "".join(parts)
