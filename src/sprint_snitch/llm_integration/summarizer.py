"""Orchestrates LLM calls for qualitative analysis.

``SprintSummarizer`` drives the full summarization pipeline: for each
repository it builds file context, summarizes every contributor, summarizes
the repo itself, deduplicates contributors across repos (by email), and
finally synthesizes an overall sprint narrative.
"""

from __future__ import annotations

import logging
import re
from typing import Callable

from sprint_snitch.llm_integration.fabric_bridge import FabricBridge
from sprint_snitch.llm_integration.prompts import (
    build_contributor_prompt,
    build_file_context,
    build_repo_prompt,
    build_sprint_narrative_prompt,
)
from sprint_snitch.models.data import (
    AuthorMetrics,
    ContributorSummary,
    RepoAnalysis,
    RepoSummary,
)

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int, str], None]

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def _strip_think_blocks(text: str) -> str:
    """Remove ``<think>…</think>`` reasoning blocks from LLM output."""
    return _THINK_RE.sub("", text).strip()


class SprintSummarizer:
    """High-level orchestrator for LLM-based sprint summarization.

    Parameters
    ----------
    bridge : FabricBridge
        An initialised :class:`FabricBridge` (or compatible stub) used
        for all LLM calls.
    """

    def __init__(self, bridge: FabricBridge) -> None:
        self._bridge = bridge

    # ------------------------------------------------------------------
    # Individual summarization helpers
    # ------------------------------------------------------------------

    def summarize_contributor(
        self,
        author: AuthorMetrics,
        file_contents: dict[str, str],
        on_model_tried=None,
    ) -> str:
        """Generate a qualitative narrative for a single contributor.

        Parameters
        ----------
        author : AuthorMetrics
            The contributor's aggregated metrics.
        file_contents : dict[str, str]
            File-path-to-content mapping for context.
        on_model_tried : callable | None
            Optional callback forwarded to the bridge.

        Returns
        -------
        str
            The LLM-generated narrative, or a fallback string.
        """
        prompt = build_contributor_prompt(author.name, author, file_contents)
        result = self._bridge.execute(prompt, on_model_tried)
        if result:
            return _strip_think_blocks(result)
        return "(Qualitative summary unavailable)"

    def summarize_repo(
        self,
        analysis: RepoAnalysis,
        file_contents: dict[str, str],
        on_model_tried=None,
    ) -> str:
        """Generate an overall summary for a single repository.

        Parameters
        ----------
        analysis : RepoAnalysis
            Full quantitative analysis for the repo.
        file_contents : dict[str, str]
            File-path-to-content mapping for context.
        on_model_tried : callable | None
            Optional callback forwarded to the bridge.

        Returns
        -------
        str
            The LLM-generated repo summary, or a fallback string.
        """
        prompt = build_repo_prompt(analysis.repo_name, analysis, file_contents)
        result = self._bridge.execute(prompt, on_model_tried)
        if result:
            return _strip_think_blocks(result)
        return "(Qualitative summary unavailable)"

    def generate_sprint_narrative(
        self,
        repo_summaries: list[str],
        contributor_summaries: list[str],
        on_model_tried=None,
    ) -> str:
        """Synthesize per-repo and per-contributor summaries into one narrative.

        Parameters
        ----------
        repo_summaries : list[str]
            Already-generated text summaries for each repository.
        contributor_summaries : list[str]
            Already-generated text summaries for each contributor.
        on_model_tried : callable | None
            Optional callback forwarded to the bridge.

        Returns
        -------
        str
            The executive narrative, or a fallback string.
        """
        prompt = build_sprint_narrative_prompt(repo_summaries, contributor_summaries)
        result = self._bridge.execute(prompt, on_model_tried)
        if result:
            return _strip_think_blocks(result)
        return "(Sprint narrative unavailable)"

    # ------------------------------------------------------------------
    # Full pipeline
    # ------------------------------------------------------------------

    def summarize_all(
        self,
        analyses: list[RepoAnalysis],
        on_progress: ProgressCallback | None = None,
    ) -> tuple[list[ContributorSummary], list[RepoSummary], str]:
        """Run the complete summarization pipeline across all repos.

        Workflow
        --------
        1. For each repo, build file context from all commits.
        2. For each author in the repo, generate a contributor summary.
        3. Generate a repo-level summary.
        4. Deduplicate contributors across repos by email (latest wins,
           summaries are concatenated).
        5. Generate the overall sprint narrative.

        Parameters
        ----------
        analyses : list[RepoAnalysis]
            One analysis per repository to summarise.
        on_progress : callable | None
            ``(current_step, total_steps, description)`` callback for UI
            progress reporting.

        Returns
        -------
        tuple[list[ContributorSummary], list[RepoSummary], str]
            ``(contributors, repo_summaries, narrative)``
        """
        # Calculate total step count for progress reporting:
        #   per-repo: (N authors + 1 repo summary) per repo
        #   + 1 final narrative
        total_steps = sum(
            len(analysis.authors) + 1 for analysis in analyses
        ) + 1
        current_step = 0

        def _progress(description: str) -> None:
            nonlocal current_step
            current_step += 1
            if on_progress is not None:
                on_progress(current_step, total_steps, description)

        # -- Per-author summaries (keyed by email for dedup) ------------------
        contributor_map: dict[str, ContributorSummary] = {}
        repo_summary_objects: list[RepoSummary] = []
        repo_summary_texts: list[str] = []

        for analysis in analyses:
            # Build file context once for the whole repo.
            file_contents = build_file_context(analysis.commits)

            # Summarize each contributor in this repo.
            for email, author in analysis.authors.items():
                _progress(f"Summarizing {author.name} in {analysis.repo_name}")
                logger.info(
                    "Summarizing contributor %s <%s> for %s",
                    author.name, email, analysis.repo_name,
                )

                # Build contributor-specific file context (only their files).
                author_paths = {fc.path for c in author.commits for fc in c.files}
                author_files = {
                    path: content
                    for path, content in file_contents.items()
                    if path in author_paths
                }
                summary_text = self.summarize_contributor(author, author_files)

                if email in contributor_map:
                    # Merge: keep latest metrics, concatenate summaries.
                    existing = contributor_map[email]
                    merged_summary = (
                        existing.qualitative_summary + "\n\n" + summary_text
                    )
                    contributor_map[email] = ContributorSummary(
                        name=author.name,
                        email=email,
                        metrics=author,
                        qualitative_summary=merged_summary,
                    )
                else:
                    contributor_map[email] = ContributorSummary(
                        name=author.name,
                        email=email,
                        metrics=author,
                        qualitative_summary=summary_text,
                    )

            # Summarize the repo itself.
            _progress(f"Summarizing repo {analysis.repo_name}")
            logger.info("Summarizing repo %s", analysis.repo_name)
            repo_text = self.summarize_repo(analysis, file_contents)

            # Parse key areas from bullet points in the LLM response.
            key_areas: list[str] = []
            for line in repo_text.splitlines():
                stripped = line.strip()
                if stripped.startswith("- "):
                    key_areas.append(stripped[2:].strip())

            repo_summary_objects.append(
                RepoSummary(
                    repo_url=analysis.repo_url,
                    repo_name=analysis.repo_name,
                    analysis=analysis,
                    overall_summary=repo_text,
                    key_areas=key_areas,
                )
            )
            repo_summary_texts.append(repo_text)

        # -- Sprint narrative -------------------------------------------------
        _progress("Generating sprint narrative")
        logger.info("Generating overall sprint narrative")

        contributor_list = list(contributor_map.values())
        contributor_texts = [c.qualitative_summary for c in contributor_list]

        narrative = self.generate_sprint_narrative(
            repo_summary_texts, contributor_texts,
        )

        return contributor_list, repo_summary_objects, narrative
