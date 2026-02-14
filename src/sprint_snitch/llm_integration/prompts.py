"""Prompt templates for LLM summarization.

All functions return plain-text prompts suitable for the ``reasoning`` role
of AuraRouter's ComputeFabric.  Helper utilities handle context-window
budgeting by truncating oversized text and building deduplicated file-content
dicts from commit data.
"""

from __future__ import annotations

from sprint_snitch.models.data import (
    AuthorMetrics,
    ChangeTypeStats,
    ChurnedFile,
    CommitCategory,
    CommitInfo,
    DailyActivity,
    FileTypeBreakdown,
    RepoAnalysis,
)


# ---------------------------------------------------------------------------
# Context helpers
# ---------------------------------------------------------------------------

def truncate_context(text: str, max_chars: int = 12000) -> str:
    """Truncate *text* to *max_chars*, appending a note when trimmed.

    Parameters
    ----------
    text : str
        The input text.
    max_chars : int
        Maximum allowed character count (default 12 000).

    Returns
    -------
    str
        The (possibly shortened) text.
    """
    if len(text) <= max_chars:
        return text
    omitted = len(text) - max_chars
    return text[:max_chars] + f"\n(truncated, {omitted} chars omitted)"


def build_file_context(
    commits: list[CommitInfo],
    max_chars: int = 12000,
) -> dict[str, str]:
    """Collect deduplicated file contents from *commits*.

    For each unique file path the content from the **latest** commit (by
    list order) wins.  When the combined character budget exceeds
    *max_chars*, the largest files are dropped first until the total fits.

    Parameters
    ----------
    commits : list[CommitInfo]
        Commits whose ``FileChange.content`` fields are harvested.
    max_chars : int
        Maximum total characters across all file contents.

    Returns
    -------
    dict[str, str]
        Mapping of ``{filepath: content}``.
    """
    # Latest-commit-wins: iterate in order so later commits overwrite earlier.
    raw: dict[str, str] = {}
    for commit in commits:
        for fc in commit.files:
            if fc.content:
                raw[fc.path] = fc.content

    # Budget check -- drop largest files first until under budget.
    total = sum(len(v) for v in raw.values())
    if total <= max_chars:
        return raw

    # Sort descending by content length so we drop the biggest first.
    ranked = sorted(raw.items(), key=lambda kv: len(kv[1]), reverse=True)
    while ranked and total > max_chars:
        path, content = ranked.pop(0)
        total -= len(content)
        raw.pop(path)

    return raw


# ---------------------------------------------------------------------------
# Analytics context formatters
# ---------------------------------------------------------------------------


def _format_file_type_context(breakdown: list[FileTypeBreakdown]) -> str:
    """Format file type breakdown into compact text for LLM context."""
    if not breakdown:
        return ""
    lines = []
    for b in breakdown[:8]:
        lines.append(
            f"- {b.file_type}: {b.lines_added} lines added, "
            f"{b.lines_removed} removed ({b.commit_count} commits)"
        )
    return "\n".join(lines)


def _format_commit_category_context(categories: list[CommitCategory]) -> str:
    """Format commit categories into a compact text line for LLM context."""
    if not categories:
        return ""
    parts = []
    _LABELS = {
        "feat": "features", "fix": "bugfixes", "refactor": "refactors",
        "docs": "documentation", "test": "test changes", "chore": "chores",
        "ci": "CI changes", "style": "style changes", "perf": "perf improvements",
        "cleanup": "cleanups", "other": "other",
    }
    for c in categories:
        label = _LABELS.get(c.category, c.category)
        parts.append(f"{c.count} {label}")
    return ", ".join(parts)


def _format_time_context(
    daily_activity: list[DailyActivity],
    peak_day: DailyActivity | None,
    weekday_commits: int,
    weekend_commits: int,
) -> str:
    """Format time-based metrics into text for LLM context."""
    parts = []
    active_days = sum(1 for d in daily_activity if d.commit_count > 0)
    total_days = len(daily_activity)
    if total_days > 0:
        parts.append(f"Active {active_days} of {total_days} days.")
    if peak_day and peak_day.commit_count > 0:
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        day_name = day_names[peak_day.date.weekday()]
        parts.append(
            f"Peak day: {peak_day.date.strftime('%Y-%m-%d')} ({day_name}, "
            f"{peak_day.commit_count} commits)."
        )
    total = weekday_commits + weekend_commits
    if total > 0:
        parts.append(
            f"Weekday: {weekday_commits} commits ({round(100 * weekday_commits / total)}%), "
            f"Weekend: {weekend_commits} commits ({round(100 * weekend_commits / total)}%)."
        )
    return " ".join(parts)


def _format_change_type_context(
    stats: ChangeTypeStats,
    churned_files: list[ChurnedFile],
) -> str:
    """Format change type stats and top churned files for LLM context."""
    parts = []
    total = stats.files_added + stats.files_modified + stats.files_deleted + stats.files_renamed
    if total > 0:
        items = []
        if stats.files_added:
            items.append(f"{stats.files_added} added")
        if stats.files_modified:
            items.append(f"{stats.files_modified} modified")
        if stats.files_deleted:
            items.append(f"{stats.files_deleted} deleted")
        if stats.files_renamed:
            items.append(f"{stats.files_renamed} renamed")
        parts.append(f"File operations: {', '.join(items)}.")
    if churned_files:
        top = churned_files[:5]
        churn_str = ", ".join(
            f"{cf.path} ({cf.change_count}x)" for cf in top
        )
        parts.append(f"Most changed files: {churn_str}.")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def build_contributor_prompt(
    author_name: str,
    metrics: AuthorMetrics,
    file_contents: dict[str, str],
) -> str:
    """Build a prompt asking the LLM to narrate a contributor's work.

    The resulting prompt instructs the model to produce a 2--4 paragraph
    qualitative summary that identifies themes, describes the nature of
    the work (features, bug fixes, refactoring, documentation, etc.), and
    assesses the scope and impact of the contributor's changes.

    Parameters
    ----------
    author_name : str
        Display name of the contributor.
    metrics : AuthorMetrics
        Aggregated quantitative metrics for this contributor.
    file_contents : dict[str, str]
        Mapping of file paths to their (possibly truncated) contents.

    Returns
    -------
    str
        A fully-formed prompt string.
    """
    # -- Commit log summary ---------------------------------------------------
    commit_lines: list[str] = []
    for c in metrics.commits:
        files_str = ", ".join(fc.path for fc in c.files) if c.files else "(no files)"
        commit_lines.append(
            f"  - [{c.sha[:8]}] {c.message.splitlines()[0]}  "
            f"(+{c.lines_added}/-{c.lines_removed}, files: {files_str})"
        )
    commit_log = "\n".join(commit_lines) or "  (no commits)"

    # -- File contents block --------------------------------------------------
    file_blocks: list[str] = []
    for path, content in file_contents.items():
        truncated = truncate_context(content, max_chars=3000)
        file_blocks.append(f"--- {path} ---\n{truncated}")
    file_section = "\n\n".join(file_blocks) or "(no file contents available)"

    return (
        f"You are an engineering manager reviewing sprint contributions.\n"
        f"\n"
        f"Write a 2-4 paragraph qualitative narrative describing what "
        f"**{author_name}** worked on during this sprint. Identify recurring "
        f"themes, describe the nature of the work (new features, bug fixes, "
        f"refactoring, tests, documentation, etc.), and assess the overall "
        f"scope and impact of their contributions.\n"
        f"\n"
        f"## Quantitative Metrics\n"
        f"- Lines added: {metrics.lines_added}\n"
        f"- Lines removed: {metrics.lines_removed}\n"
        f"\n"
        f"## Commit Log\n"
        f"{commit_log}\n"
        f"\n"
        f"## Modified File Contents\n"
        f"{file_section}\n"
        f"\n"
        f"Respond with ONLY the narrative paragraphs -- no headings, bullet "
        f"points, or metadata."
    )


def build_repo_prompt(
    repo_name: str,
    analysis: RepoAnalysis,
    file_contents: dict[str, str],
) -> str:
    """Build a prompt asking the LLM to summarize overall repo changes.

    The prompt instructs the model to provide an overview paragraph
    followed by 3--5 bullet points identifying key areas of change.

    Parameters
    ----------
    repo_name : str
        Human-readable repository name.
    analysis : RepoAnalysis
        Full quantitative analysis for the repo.
    file_contents : dict[str, str]
        Mapping of file paths to their (possibly truncated) contents.

    Returns
    -------
    str
        A fully-formed prompt string.
    """
    # -- Author breakdown -----------------------------------------------------
    author_lines: list[str] = []
    for email, am in analysis.authors.items():
        author_lines.append(
            f"  - {am.name} <{email}>: "
            f"+{am.lines_added}/-{am.lines_removed}"
        )
    author_section = "\n".join(author_lines) or "  (no authors)"

    # -- Files changed --------------------------------------------------------
    files_list = "\n".join(f"  - {f}" for f in analysis.files_changed[:50])
    if len(analysis.files_changed) > 50:
        files_list += f"\n  ... and {len(analysis.files_changed) - 50} more"

    # -- File contents block --------------------------------------------------
    file_blocks: list[str] = []
    for path, content in file_contents.items():
        truncated = truncate_context(content, max_chars=3000)
        file_blocks.append(f"--- {path} ---\n{truncated}")
    file_section = "\n\n".join(file_blocks) or "(no file contents available)"

    # -- Analytics context (from enrichment) -----------------------------------
    analytics_sections = ""

    if analysis.file_type_breakdown:
        ft_ctx = _format_file_type_context(analysis.file_type_breakdown)
        analytics_sections += f"\n## Work by File Type\n{ft_ctx}\n"

    if analysis.commit_categories:
        cat_ctx = _format_commit_category_context(analysis.commit_categories)
        analytics_sections += f"\n## Commit Categories\n{cat_ctx}\n"

    if analysis.daily_activity:
        time_ctx = _format_time_context(
            analysis.daily_activity, analysis.peak_day,
            analysis.weekday_commits, analysis.weekend_commits,
        )
        analytics_sections += f"\n## Sprint Timeline\n{time_ctx}\n"

    ct_total = (analysis.change_type_stats.files_added +
                analysis.change_type_stats.files_modified +
                analysis.change_type_stats.files_deleted +
                analysis.change_type_stats.files_renamed)
    if ct_total > 0 or analysis.churned_files:
        ct_ctx = _format_change_type_context(
            analysis.change_type_stats, analysis.churned_files,
        )
        analytics_sections += f"\n## Change Analysis\n{ct_ctx}\n"

    return (
        f"You are a technical lead summarizing repository activity for a sprint report.\n"
        f"\n"
        f"Summarize the changes made to **{repo_name}** during this sprint. "
        f"Provide ONE overview paragraph, then list 3-5 key areas of change "
        f"as bullet points.\n"
        f"\n"
        f"## Repository Metrics\n"
        f"- Total commits: {analysis.total_commits}\n"
        f"- Lines added: {analysis.total_lines_added}\n"
        f"- Lines removed: {analysis.total_lines_removed}\n"
        f"- Files changed: {len(analysis.files_changed)}\n"
        f"{analytics_sections}"
        f"\n"
        f"## Contributors\n"
        f"{author_section}\n"
        f"\n"
        f"## Files Changed\n"
        f"{files_list}\n"
        f"\n"
        f"## Modified File Contents\n"
        f"{file_section}\n"
        f"\n"
        f"Format your response as:\n"
        f"1. A single overview paragraph.\n"
        f"2. A blank line.\n"
        f"3. 3-5 bullet points (using \"-\") identifying key areas of change.\n"
        f"\n"
        f"Do not include any other headings or metadata."
    )


def build_sprint_narrative_prompt(
    repo_summaries: list[str],
    contributor_summaries: list[str],
) -> str:
    """Build a prompt to synthesize an executive sprint narrative.

    Takes **already-generated** per-repo and per-contributor text
    summaries and asks the LLM to combine them into a cohesive 2--3
    paragraph executive summary.

    Parameters
    ----------
    repo_summaries : list[str]
        LLM-generated text summaries for each repository.
    contributor_summaries : list[str]
        LLM-generated text summaries for each contributor.

    Returns
    -------
    str
        A fully-formed prompt string.
    """
    repos_block = "\n\n---\n\n".join(repo_summaries) or "(no repository summaries)"
    contribs_block = "\n\n---\n\n".join(contributor_summaries) or "(no contributor summaries)"

    return (
        f"You are writing an executive summary for a sprint report.\n"
        f"\n"
        f"Below are individual summaries for each repository and each "
        f"contributor involved in this sprint. Synthesize them into a "
        f"cohesive 2-3 paragraph executive narrative that highlights the "
        f"most important accomplishments, cross-cutting themes, and overall "
        f"sprint trajectory.\n"
        f"\n"
        f"## Repository Summaries\n"
        f"{repos_block}\n"
        f"\n"
        f"## Contributor Summaries\n"
        f"{contribs_block}\n"
        f"\n"
        f"Respond with ONLY the narrative paragraphs -- no headings, bullet "
        f"points, or metadata."
    )
