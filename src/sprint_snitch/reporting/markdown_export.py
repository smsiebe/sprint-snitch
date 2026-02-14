"""Renders SprintReport to Markdown with ASCII charts."""

from __future__ import annotations

from pathlib import Path

from sprint_snitch.models.data import (
    ContributorSummary,
    RepoSummary,
    SprintReport,
)


def render_markdown(report: SprintReport) -> str:
    """Produce the full Markdown sprint report document."""
    sections = [
        _render_header(report),
        _render_executive_summary(report),
        _render_repo_sections(report),
        _render_contributor_sections(report),
        _render_activity_overview(report),
        _render_file_type_breakdown(report),
        _render_commit_categories(report),
        _render_timeline(report),
        _render_change_type_stats(report),
        _render_footer(report),
    ]
    return "\n\n".join(s for s in sections if s)


def save_markdown(report: SprintReport, output_path: Path) -> Path:
    """Write rendered Markdown to file and return the path."""
    content = render_markdown(report)
    output_path = Path(output_path)
    output_path.write_text(content, encoding="utf-8")
    return output_path


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------


def _render_header(report: SprintReport) -> str:
    date_from = report.date_from.strftime("%Y-%m-%d")
    date_to = report.date_to.strftime("%Y-%m-%d")
    lines = [
        f"# Sprint Report: {date_from} — {date_to}",
        "",
        f"**Generated:** {report.generated_at.strftime('%Y-%m-%d %H:%M')}",
    ]
    if report.repos:
        lines.append("")
        lines.append("**Repositories analyzed:**")
        for rs in report.repos:
            lines.append(f"- [{rs.repo_name}]({rs.repo_url})")
    return "\n".join(lines)


def _render_executive_summary(report: SprintReport) -> str:
    lines = ["## Executive Summary"]
    if report.overall_narrative:
        lines.append("")
        lines.append(report.overall_narrative)
    else:
        lines.append("")
        lines.append("*No executive summary available.*")
    return "\n".join(lines)


def _render_repo_sections(report: SprintReport) -> str:
    if not report.repos:
        return ""
    parts = ["## Repositories"]
    for rs in report.repos:
        parts.append(_render_single_repo(rs))
    return "\n\n".join(parts)


def _render_single_repo(rs: RepoSummary) -> str:
    a = rs.analysis
    lines = [
        f"### {_escape_md(rs.repo_name)}",
        "",
        _render_metrics_table(
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
        lines.append("")
        lines.append(rs.overall_summary)
    if rs.key_areas:
        lines.append("")
        lines.append("**Key areas of change:**")
        for area in rs.key_areas:
            lines.append(f"- {_escape_md(area)}")
    return "\n".join(lines)


def _render_contributor_sections(report: SprintReport) -> str:
    if not report.contributors:
        return ""
    parts = ["## Contributors"]
    for cs in report.contributors:
        parts.append(_render_single_contributor(cs))
    return "\n\n".join(parts)


def _render_single_contributor(cs: ContributorSummary) -> str:
    m = cs.metrics
    lines = [
        f"### {_escape_md(cs.name)}",
        "",
        _render_metrics_table(
            ["Metric", "Value"],
            [
                ["Lines added", f"+{m.lines_added}"],
                ["Lines removed", f"-{m.lines_removed}"],
            ],
        ),
    ]
    if cs.qualitative_summary:
        lines.append("")
        lines.append(cs.qualitative_summary)
    return "\n".join(lines)


def _render_activity_overview(report: SprintReport) -> str:
    if not report.contributors:
        return ""
    lines = ["## Activity Overview"]

    # Lines changed per contributor
    lines_data = {
        cs.name: cs.metrics.lines_added + cs.metrics.lines_removed
        for cs in report.contributors
    }
    if any(v > 0 for v in lines_data.values()):
        lines.append("")
        lines.append(
            _render_ascii_bar_chart(lines_data, "Lines Changed per Contributor")
        )

    return "\n".join(lines)


def _render_file_type_breakdown(report: SprintReport) -> str:
    """Render file type breakdown tables and charts for each repo."""
    has_data = any(
        rs.analysis.file_type_breakdown for rs in report.repos
    )
    if not has_data:
        return ""

    parts = ["## File Type Breakdown"]

    for rs in report.repos:
        breakdown = rs.analysis.file_type_breakdown
        if not breakdown:
            continue

        if len(report.repos) > 1:
            parts.append(f"### {_escape_md(rs.repo_name)}")

        rows = []
        for b in breakdown:
            rows.append([
                b.file_type,
                str(b.file_count),
                f"+{b.lines_added}",
                f"-{b.lines_removed}",
                str(b.commit_count),
            ])
        parts.append(_render_metrics_table(
            ["File Type", "Files", "Lines Added", "Lines Removed", "Commits"],
            rows,
        ))

        chart_data = {
            b.file_type: b.lines_added + b.lines_removed for b in breakdown
        }
        if any(v > 0 for v in chart_data.values()):
            parts.append(_render_ascii_bar_chart(chart_data, "Lines Changed by File Type"))

    return "\n\n".join(parts)


def _render_commit_categories(report: SprintReport) -> str:
    """Render commit category distribution for repos and contributors."""
    has_data = any(
        rs.analysis.commit_categories for rs in report.repos
    )
    if not has_data:
        return ""

    parts = ["## Commit Categories"]

    for rs in report.repos:
        categories = rs.analysis.commit_categories
        if not categories:
            continue

        if len(report.repos) > 1:
            parts.append(f"### {_escape_md(rs.repo_name)}")

        rows = [[c.category, str(c.count)] for c in categories]
        parts.append(_render_metrics_table(["Category", "Count"], rows))

        chart_data = {c.category: c.count for c in categories}
        if any(v > 0 for v in chart_data.values()):
            parts.append(_render_ascii_bar_chart(chart_data, "Commit Distribution"))

    return "\n\n".join(parts)


def _render_timeline(report: SprintReport) -> str:
    """Render daily activity timeline and time-based metrics."""
    # Merge daily activity across all repos
    from collections import defaultdict

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

    parts = ["## Sprint Timeline"]

    # Daily activity chart
    _DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    sorted_days = sorted(daily_merged.keys())

    chart_data = {}
    for day in sorted_days:
        d = daily_merged[day]
        day_name = _DAY_NAMES[day.weekday()]
        label = f"{day.strftime('%Y-%m-%d')} ({day_name})"
        chart_data[label] = d["commit_count"]

    if any(v > 0 for v in chart_data.values()):
        parts.append(_render_ascii_bar_chart(chart_data, "Daily Commit Activity"))

    # Peak day + weekday/weekend
    meta_lines = []
    if peak:
        day_name = _DAY_NAMES[peak.date.weekday()]
        meta_lines.append(
            f"**Peak Day:** {peak.date.strftime('%Y-%m-%d')} ({day_name}) "
            f"-- {peak.commit_count} commits"
        )
    total = total_weekday + total_weekend
    if total > 0:
        wd_pct = round(100 * total_weekday / total)
        we_pct = 100 - wd_pct
        meta_lines.append(
            f"**Weekday commits:** {total_weekday} ({wd_pct}%) | "
            f"**Weekend commits:** {total_weekend} ({we_pct}%)"
        )
    if meta_lines:
        parts.append("\n".join(meta_lines))

    return "\n\n".join(parts)


def _render_change_type_stats(report: SprintReport) -> str:
    """Render change type breakdown and churned files."""
    has_data = any(
        (rs.analysis.change_type_stats.files_added +
         rs.analysis.change_type_stats.files_modified +
         rs.analysis.change_type_stats.files_deleted +
         rs.analysis.change_type_stats.files_renamed) > 0
        for rs in report.repos
    )
    if not has_data:
        return ""

    parts = ["## Change Analysis"]

    # Per-repo change types
    repo_rows = []
    for rs in report.repos:
        s = rs.analysis.change_type_stats
        repo_rows.append([
            rs.repo_name,
            str(s.files_added),
            str(s.files_modified),
            str(s.files_deleted),
            str(s.files_renamed),
        ])
    parts.append("### Change Types")
    parts.append(_render_metrics_table(
        ["Repo", "Added", "Modified", "Deleted", "Renamed"],
        repo_rows,
    ))

    # Churned files
    all_churned = []
    for rs in report.repos:
        all_churned.extend(rs.analysis.churned_files)
    if all_churned:
        all_churned.sort(key=lambda c: c.change_count, reverse=True)
        churn_rows = []
        for cf in all_churned[:10]:
            churn_rows.append([
                cf.path,
                str(cf.change_count),
                f"+{cf.total_lines_added}",
                f"-{cf.total_lines_removed}",
            ])
        parts.append("### Most Changed Files")
        parts.append(_render_metrics_table(
            ["File", "Times Changed", "Lines Added", "Lines Removed"],
            churn_rows,
        ))

    return "\n\n".join(parts)


def _render_footer(report: SprintReport) -> str:
    lines = ["---", f"*Generated by Sprint Snitch v0.1.0*"]
    if report.token_usage:
        inp = report.token_usage.get("input_tokens", 0)
        out = report.token_usage.get("output_tokens", 0)
        calls = report.token_usage.get("calls", 0)
        if inp or out:
            lines.append(
                f"*LLM usage: {calls} calls, {inp} input tokens, {out} output tokens*"
            )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _render_metrics_table(headers: list[str], rows: list[list[str]]) -> str:
    """Render a GFM Markdown table."""
    header_line = "| " + " | ".join(headers) + " |"
    sep_line = "| " + " | ".join("---" for _ in headers) + " |"
    data_lines = []
    for row in rows:
        escaped = [_escape_md(cell) for cell in row]
        data_lines.append("| " + " | ".join(escaped) + " |")
    return "\n".join([header_line, sep_line] + data_lines)


def _render_ascii_bar_chart(
    data: dict[str, int], title: str, max_width: int = 40
) -> str:
    """Render a horizontal ASCII bar chart.

    Format per line: ``<label (padded)> | <bar> <value>``
    """
    if not data:
        return ""

    lines = [f"**{title}**", "```"]
    max_val = max(data.values()) if data else 0
    max_label_len = max((len(label) for label in data), default=0)

    for label, value in data.items():
        padded_label = label.ljust(max_label_len)
        if max_val > 0:
            bar_len = round(value / max_val * max_width)
        else:
            bar_len = 0
        bar = "\u2588" * bar_len
        lines.append(f"  {padded_label} | {bar} {value}")

    lines.append("```")
    return "\n".join(lines)


def _escape_md(text: str) -> str:
    """Escape characters that have special meaning in Markdown tables."""
    return text.replace("|", "\\|").replace("*", "\\*")
