"""Git analysis engine — clone, extract, measure, and enrich."""

from sprint_snitch.git_analysis.clone import GitError, clone_or_fetch
from sprint_snitch.git_analysis.diff_extractor import extract_commits, get_diff_text
from sprint_snitch.git_analysis.enrichment import enrich_repo_analysis
from sprint_snitch.git_analysis.metrics import (
    compute_author_metrics,
    compute_repo_analysis,
    get_changed_files,
)

__all__ = [
    "GitError",
    "clone_or_fetch",
    "compute_author_metrics",
    "compute_repo_analysis",
    "enrich_repo_analysis",
    "extract_commits",
    "get_changed_files",
    "get_diff_text",
]
