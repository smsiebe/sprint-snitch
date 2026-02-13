"""QObject background workers for async operations.

Follows AuraRouter's InferenceWorker pattern: a QObject with typed Signals
that is moved to a QThread.  The ``run()`` slot drives the full analysis
pipeline (clone, extract, metrics, optional LLM, report assembly) and
emits progress/result/error signals back to the main thread.
"""

from __future__ import annotations

import logging
import tempfile
from datetime import datetime

from PySide6.QtCore import QObject, Signal

from sprint_snitch.git_analysis.clone import clone_or_fetch
from sprint_snitch.git_analysis.diff_extractor import extract_commits
from sprint_snitch.git_analysis.metrics import compute_repo_analysis
from sprint_snitch.llm_integration.fabric_bridge import FabricBridge
from sprint_snitch.llm_integration.summarizer import SprintSummarizer
from sprint_snitch.models.data import (
    ContributorSummary,
    RepoAnalysis,
    RepoSummary,
    SprintReport,
)
from sprint_snitch.reporting.report_builder import (
    ReportBuilder,
    merge_contributors_across_repos,
)

logger = logging.getLogger(__name__)


class AnalysisWorker(QObject):
    """Runs the full sprint-snitch pipeline off the main thread.

    Signals
    -------
    progress(current_step, total_steps, message)
        Incremental step progress for the progress bar.
    repo_cloned(repo_url)
        Emitted after a repository has been cloned or fetched.
    repo_analyzed(repo_url)
        Emitted after commit extraction and metrics computation for a repo.
    llm_progress(description)
        Description of the current LLM summarization step.
    model_tried(role, model_id, success, elapsed)
        Forwarded from FabricBridge after each model attempt.
    finished(report)
        Emitted with the completed SprintReport on success.
    error(message)
        Emitted with a human-readable error string on failure.
    """

    progress = Signal(int, int, str)           # (current_step, total_steps, message)
    repo_cloned = Signal(str)                  # repo_url
    repo_analyzed = Signal(str)                # repo_url
    llm_progress = Signal(str)                 # description of current LLM call
    model_tried = Signal(str, str, bool, float)  # (role, model_id, success, elapsed)
    finished = Signal(object)                  # SprintReport
    error = Signal(str)                        # error message

    def __init__(
        self,
        repo_urls: list[str],
        date_from: datetime,
        date_to: datetime,
        config_path: str | None,
        use_llm: bool,
        work_dir: str | None,
    ) -> None:
        super().__init__()
        self._repo_urls = repo_urls
        self._date_from = date_from
        self._date_to = date_to
        self._config_path = config_path
        self._use_llm = use_llm
        self._work_dir = work_dir

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _emit_model_tried(
        self, role: str, model_id: str, success: bool, elapsed: float
    ) -> None:
        """Callback forwarded to FabricBridge.execute()."""
        self.model_tried.emit(role, model_id, success, elapsed)

    # ------------------------------------------------------------------
    # Main pipeline
    # ------------------------------------------------------------------

    def run(self) -> None:  # noqa: C901 — unavoidable pipeline complexity
        """Execute the full clone -> analyze -> summarize -> build pipeline.

        This method is intended to be connected to ``QThread.started`` so it
        runs entirely on the worker thread.
        """
        try:
            repos = self._repo_urls
            work_dir = self._work_dir or tempfile.mkdtemp(prefix="sprint_snitch_")

            # Step budget:
            #   clone steps = len(repos)
            #   analyze steps = len(repos)
            #   LLM steps are dynamic (calculated after analysis) but we add a
            #   placeholder of 1 here so the bar isn't stuck at 100% during LLM.
            n_repos = len(repos)
            llm_placeholder = 1 if self._use_llm else 0
            total_steps = n_repos * 2 + llm_placeholder
            current_step = 0

            # -- Phase 1: Clone / fetch ----------------------------------------
            repo_paths: dict[str, str] = {}  # url -> local path

            for url in repos:
                current_step += 1
                self.progress.emit(current_step, total_steps, f"Cloning {url}")
                logger.info("Cloning %s", url)

                repo_path = clone_or_fetch(url, work_dir)
                repo_paths[url] = str(repo_path)
                self.repo_cloned.emit(url)

            # -- Phase 2: Extract commits + compute metrics --------------------
            analyses: list[RepoAnalysis] = []

            for url in repos:
                current_step += 1
                self.progress.emit(current_step, total_steps, f"Analyzing {url}")
                logger.info("Analyzing %s", url)

                from pathlib import Path
                repo_path = Path(repo_paths[url])
                commits = extract_commits(repo_path, self._date_from, self._date_to)
                analysis = compute_repo_analysis(
                    url, commits, self._date_from, self._date_to
                )
                analyses.append(analysis)
                self.repo_analyzed.emit(url)

            # -- Phase 3: Optional LLM summarization ---------------------------
            contributor_summaries: list[ContributorSummary] = []
            repo_summaries: list[RepoSummary] = []
            narrative = ""
            token_usage: dict = {}

            if self._use_llm:
                bridge = FabricBridge(self._config_path)
                if bridge.is_available():
                    summarizer = SprintSummarizer(bridge)

                    # Now we know the real LLM step count — recalculate total.
                    llm_steps = sum(
                        len(a.authors) + 1 for a in analyses
                    ) + 1  # +1 for narrative
                    total_steps = n_repos * 2 + llm_steps

                    def _on_llm_progress(
                        llm_current: int, llm_total: int, description: str
                    ) -> None:
                        nonlocal current_step
                        current_step = n_repos * 2 + llm_current
                        self.progress.emit(current_step, total_steps, description)
                        self.llm_progress.emit(description)

                    contributor_summaries, repo_summaries, narrative = (
                        summarizer.summarize_all(
                            analyses, on_progress=_on_llm_progress
                        )
                    )
                    token_usage = bridge.get_token_usage()
                else:
                    logger.warning(
                        "AuraRouter not available. Skipping LLM summarization."
                    )

            # -- Phase 4: Assemble the report ----------------------------------
            builder = ReportBuilder(self._date_from, self._date_to)

            if repo_summaries:
                for rs in repo_summaries:
                    builder.add_repo_summary(rs)
            else:
                # Quantitative-only: wrap each analysis in a bare RepoSummary.
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
                # Quantitative-only: merge authors across repos.
                merged = merge_contributors_across_repos(analyses)
                for email, metrics in merged.items():
                    builder.add_contributor_summary(
                        ContributorSummary(
                            name=metrics.name, email=email, metrics=metrics
                        )
                    )

            builder.set_overall_narrative(narrative)
            builder.set_token_usage(token_usage)
            report = builder.build()

            self.finished.emit(report)

        except Exception as exc:
            logger.exception("Analysis pipeline failed")
            self.error.emit(str(exc))
