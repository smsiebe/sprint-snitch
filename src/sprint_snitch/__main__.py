"""CLI entry point for sprint-snitch."""

from __future__ import annotations

import argparse
import logging
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from sprint_snitch import __version__


def _parse_date(value: str) -> datetime:
    """Parse an ISO date string into a datetime."""
    return datetime.fromisoformat(value)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sprint-snitch",
        description="Sprint Snitch — Automated sprint report generator from git repositories",
    )
    parser.add_argument(
        "--version", action="version", version=f"sprint-snitch {__version__}"
    )

    subparsers = parser.add_subparsers(dest="command")

    # GUI subcommand
    subparsers.add_parser("gui", help="Launch the PySide6 GUI")

    # Headless args (default when no subcommand)
    parser.add_argument(
        "--repos", nargs="+", metavar="URL",
        help="One or more remote git repository URLs",
    )
    parser.add_argument(
        "--from-date", type=_parse_date,
        default=None,
        help="Start date (ISO format, default: 14 days ago)",
    )
    parser.add_argument(
        "--to-date", type=_parse_date,
        default=None,
        help="End date (ISO format, default: today)",
    )
    parser.add_argument(
        "-o", "--output", type=Path,
        default=Path("sprint_report.md"),
        help="Output Markdown file path (default: sprint_report.md)",
    )
    parser.add_argument(
        "--work-dir",
        default=None,
        help="Directory for cloned repos (default: temp directory)",
    )
    parser.add_argument(
        "--no-llm", action="store_true",
        help="Skip LLM summarization (quantitative-only report)",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to AuraRouter auraconfig.yaml",
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    """Entry point for the sprint-snitch CLI."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr,
    )

    # GUI subcommand
    if args.command == "gui":
        from sprint_snitch.gui.app import launch_gui
        launch_gui()
        return

    # Headless mode — repos are required
    if not args.repos:
        parser.error("--repos is required in headless mode (or use 'gui' subcommand)")

    # Date defaults
    date_to = args.to_date or datetime.now()
    date_from = args.from_date or (date_to - timedelta(days=14))

    # Work directory
    work_dir = args.work_dir or tempfile.mkdtemp(prefix="sprint_snitch_")

    print(f"Sprint Snitch v{__version__}", file=sys.stderr)
    print(f"Date range: {date_from.date()} to {date_to.date()}", file=sys.stderr)
    print(f"Repos: {len(args.repos)}", file=sys.stderr)

    try:
        _run_headless(
            repo_urls=args.repos,
            date_from=date_from,
            date_to=date_to,
            output_path=args.output,
            work_dir=work_dir,
            use_llm=not args.no_llm,
            config_path=args.config,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


def _run_headless(
    repo_urls: list[str],
    date_from: datetime,
    date_to: datetime,
    output_path: Path,
    work_dir: str,
    use_llm: bool,
    config_path: str | None,
) -> None:
    """Execute the full pipeline in headless (CLI) mode."""
    from sprint_snitch.git_analysis.clone import clone_or_fetch
    from sprint_snitch.git_analysis.diff_extractor import extract_commits
    from sprint_snitch.git_analysis.metrics import compute_repo_analysis
    from sprint_snitch.llm_integration.fabric_bridge import FabricBridge
    from sprint_snitch.llm_integration.summarizer import SprintSummarizer
    from sprint_snitch.models.data import ContributorSummary, RepoSummary
    from sprint_snitch.reporting.markdown_export import save_markdown
    from sprint_snitch.reporting.report_builder import (
        ReportBuilder,
        merge_contributors_across_repos,
    )

    analyses = []

    # Step 1 & 2: Clone and analyze each repo
    for url in repo_urls:
        print(f"Cloning {url}...", file=sys.stderr)
        repo_path = clone_or_fetch(url, work_dir)

        print(f"Analyzing {url}...", file=sys.stderr)
        commits = extract_commits(repo_path, date_from, date_to)
        analysis = compute_repo_analysis(url, commits, date_from, date_to)
        analyses.append(analysis)
        print(
            f"  {analysis.total_commits} commits, "
            f"+{analysis.total_lines_added}/-{analysis.total_lines_removed}, "
            f"{len(analysis.authors)} contributors",
            file=sys.stderr,
        )

    # Step 3: LLM summarization (optional)
    contributor_summaries = []
    repo_summaries = []
    narrative = ""
    token_usage = {}

    if use_llm:
        bridge = FabricBridge(config_path)
        if bridge.is_available():
            print("Running LLM summarization...", file=sys.stderr)
            summarizer = SprintSummarizer(bridge)

            def on_progress(current, total, desc):
                print(f"  [{current}/{total}] {desc}", file=sys.stderr)

            contributor_summaries, repo_summaries, narrative = summarizer.summarize_all(
                analyses, on_progress=on_progress
            )
            token_usage = bridge.get_token_usage()
        else:
            print(
                "AuraRouter not available. Generating quantitative-only report.",
                file=sys.stderr,
            )

    # Step 4: Build report
    builder = ReportBuilder(date_from, date_to)

    if repo_summaries:
        for rs in repo_summaries:
            builder.add_repo_summary(rs)
    else:
        # Quantitative-only: wrap analyses in RepoSummary without qualitative
        for analysis in analyses:
            builder.add_repo_summary(
                RepoSummary(
                    repo_url=analysis.repo_url,
                    repo_name=analysis.repo_name,
                    analysis=analysis,
                )
            )

    if contributor_summaries:
        for cs in contributor_summaries:
            builder.add_contributor_summary(cs)
    else:
        # Quantitative-only: wrap merged authors in ContributorSummary
        merged = merge_contributors_across_repos(analyses)
        for email, metrics in merged.items():
            builder.add_contributor_summary(
                ContributorSummary(name=metrics.name, email=email, metrics=metrics)
            )

    builder.set_overall_narrative(narrative)
    builder.set_token_usage(token_usage)
    report = builder.build()

    # Step 5: Export
    save_markdown(report, output_path)
    print(str(output_path.resolve()))


if __name__ == "__main__":
    main()
