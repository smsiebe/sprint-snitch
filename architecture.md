# Sprint Snitch — Architecture

## System overview

Sprint Snitch is a pipeline-based application that flows data through four stages: extraction, enrichment, summarization, and rendering. Each stage is a separate package with no circular dependencies.

```
User Input (repo URLs + date range)
        │
        ▼
┌─────────────────┐
│  git_analysis/   │   Stage 1: Extraction
│  clone.py        │   Clone/fetch repos via subprocess
│  diff_extractor  │   Parse git log --numstat into CommitInfo
│  metrics.py      │   Aggregate into AuthorMetrics + RepoAnalysis
│  enrichment.py   │   Classify file types, commits, timelines, churn
└────────┬────────┘
         │ RepoAnalysis (quantitative)
         ▼
┌─────────────────┐
│ llm_integration/ │   Stage 2: Summarization (optional)
│ fabric_bridge    │   AuraRouter ComputeFabric wrapper
│ prompts.py       │   Prompt construction + context budgeting
│ summarizer.py    │   Orchestrate per-author, per-repo, overall LLM calls
└────────┬────────┘
         │ ContributorSummary, RepoSummary, narrative
         ▼
┌─────────────────┐
│   reporting/     │   Stage 3: Assembly + Rendering
│ report_builder   │   Builder pattern → SprintReport
│ markdown_export  │   GFM tables, ASCII charts → .md file
└────────┬────────┘
         │
         ▼
    sprint_report.md
```

## Data model hierarchy

All types are stdlib `@dataclass` in `models/data.py`. The hierarchy flows from fine-grained to aggregate:

```
FileChange              ─┐
FileTypeBreakdown        │
CommitCategory           │  Building blocks
DailyActivity            │
ChangeTypeStats          │
ChurnedFile             ─┘
        │
        ▼
CommitInfo              ─── A single parsed git commit (contains FileChange[])
        │
        ▼
AuthorMetrics           ─── Per-author aggregation (contains CommitInfo[], enrichment fields)
        │
        ▼
RepoAnalysis            ─── Per-repo quantitative analysis (contains AuthorMetrics{}, enrichment fields)
        │
        ▼
ContributorSummary      ─── AuthorMetrics + qualitative LLM summary
RepoSummary             ─── RepoAnalysis + qualitative LLM summary + key areas
        │
        ▼
SprintReport            ─── Top-level output (RepoSummary[], ContributorSummary[], narrative)
```

## Package responsibilities

### `git_analysis/` — Extraction + enrichment

**clone.py** — Repository management
- `clone_or_fetch(repo_url, work_dir)` → `Path`
- Sanitizes URLs into directory names (e.g. `github.com_org_repo`)
- Clones fresh or runs `git fetch --all` on existing clones
- Raises `GitError` with returncode and stderr on failure

**diff_extractor.py** — Commit parsing
- `extract_commits(repo_path, date_from, date_to)` → `list[CommitInfo]`
- Runs `git log --numstat` with custom `COMMIT_SEP` delimiter
- Parses each block into `CommitInfo` with `FileChange` list
- Enriches with file content at each commit SHA (50KB truncation)
- `get_diff_text(repo_path, sha)` — raw unified diff for LLM context

**metrics.py** — Quantitative aggregation
- `compute_author_metrics(commits)` → `dict[str, AuthorMetrics]`
- `compute_repo_analysis(url, commits, date_from, date_to)` → `RepoAnalysis`
- Calls `enrich_repo_analysis()` to populate all analytics fields

**enrichment.py** — Pure computation (zero I/O)
- **File classification:** 40+ extensions mapped to language names, plus filename-based detection (Dockerfile, Makefile, etc.)
- **Commit classification:** Conventional commit regex (`feat:`, `fix(scope):`, etc.) with keyword heuristic fallback
- **Time analytics:** Daily activity across full date range (including zero-commit days), peak day, weekday/weekend split
- **Change analysis:** Files added/modified/deleted/renamed, top-10 churned files
- **Per-author enrichment:** All above computed per contributor
- **Merge helpers:** Functions to union metrics across repos (for cross-repo contributor merging)
- `enrich_repo_analysis(analysis)` — orchestrator, mutates RepoAnalysis in-place

### `llm_integration/` — AI summarization

**fabric_bridge.py** — AuraRouter wrapper
- `FabricBridge(config_path)` — tries `from aurarouter.config import ConfigLoader`, disables on failure
- `execute(prompt, on_model_tried)` — sends to `"reasoning"` role, tracks tokens
- `is_available()` — True when ComputeFabric initialized successfully
- Token accounting: `get_token_usage()`, `reset_token_usage()`
- `AuraGridBridge` — placeholder subclass, raises `NotImplementedError`

**prompts.py** — Prompt engineering
- `build_contributor_prompt(name, metrics, files)` — 2-4 paragraph contributor narrative
- `build_repo_prompt(name, analysis, files)` — overview paragraph + 3-5 key area bullets
- `build_sprint_narrative_prompt(repo_summaries, contributor_summaries)` — executive synthesis
- `build_file_context(commits)` — deduplicated file contents, latest version wins
- `truncate_context(text, budget=12000)` — hard character limit for prompt context

**summarizer.py** — Pipeline orchestration
- `SprintSummarizer(bridge)` — drives the full LLM pipeline
- `summarize_all(analyses, on_progress)` returns `(contributors, repo_summaries, narrative)`
- Pipeline:
  1. For each repo: build file context → summarize each author → summarize repo
  2. Deduplicate contributors across repos by email (concatenate summaries)
  3. Generate overall sprint narrative from repo + contributor summaries
- Progress callback: `(current_step, total_steps, description)`

### `reporting/` — Assembly + rendering

**report_builder.py** — Builder pattern
- `ReportBuilder(date_from, date_to)` with `add_repo_summary()`, `add_contributor_summary()`, `set_overall_narrative()`, `set_token_usage()`
- `build()` → `SprintReport`
- `merge_contributors_across_repos(analyses)` — unions `AuthorMetrics` by email

**markdown_export.py** — Markdown rendering
- `render_markdown(report)` → `str` — joins all section renderers
- `save_markdown(report, path)` → `Path`
- Section renderers (each returns empty string if no data → section skipped):
  - `_render_header` — title, timestamp, repo links
  - `_render_executive_summary` — overall narrative
  - `_render_repo_sections` — per-repo metrics table + summary + key areas
  - `_render_contributor_sections` — per-contributor metrics table + narrative
  - `_render_activity_overview` — ASCII bar charts (commits + lines per contributor)
  - `_render_file_type_breakdown` — per-repo tables + charts, per-contributor inline
  - `_render_commit_categories` — distribution tables + charts
  - `_render_timeline` — daily activity chart, peak day, weekday/weekend split
  - `_render_change_type_stats` — add/modify/delete/rename tables + top-10 churned files
  - `_render_footer` — version + LLM token usage
- Helpers: `_render_metrics_table()` (GFM tables), `_render_ascii_bar_chart()` (horizontal bars), `_escape_md()` (pipe/asterisk escaping)

### `gui/` — PySide6 desktop interface

**app.py** — `launch_gui()` creates `QApplication` and shows `SprintSnitchWindow`

**main_window.py** — `SprintSnitchWindow(QMainWindow)`
- Three-tab layout: Input, Progress, Report
- Manages `QThread` + `AnalysisWorker` lifecycle
- Keyboard shortcuts: `Ctrl+Return` (analyze), `Escape` (cancel)
- Thread cleanup via `deleteLater()` pattern

**input_panel.py** — `InputPanel`
- Repository URL text area, date range pickers, LLM toggle checkbox
- Probes `FabricBridge` availability to enable/disable LLM option
- Emits `analyze_requested(urls, date_from, date_to, use_llm)` signal

**progress_panel.py** — `ProgressPanel`
- Progress bar + monospace log console + Cancel button
- Slots for: `on_progress`, `on_repo_cloned`, `on_repo_analyzed`, `on_llm_progress`, `on_model_tried`, `on_error`, `on_finished`

**report_viewer.py** — `ReportViewer`
- Read-only markdown display
- Export to file via save dialog
- Copy to system clipboard

**workers.py** — `AnalysisWorker(QObject)`
- Moved to `QThread` (not subclassed)
- Executes the full pipeline: clone → extract → metrics → LLM → build report
- Emits typed signals for each pipeline phase
- Dynamically recalculates total step count once authors are known

## AuraRouter integration

Sprint-snitch uses AuraRouter as a **Python library**, not a network service:

```python
from aurarouter.config import ConfigLoader
from aurarouter.fabric import ComputeFabric

config = ConfigLoader(config_path)       # Loads auraconfig.yaml
fabric = ComputeFabric(config)           # Initializes model connections
result = fabric.execute("reasoning", prompt, on_model_tried=callback)
```

This means:
- AuraRouter must be `pip install`-ed in the same environment
- Running AuraRouter as a GUI or MCP server in a separate process does not help
- No gRPC, no HTTP, no MCP — direct in-process Python calls
- The `on_model_tried` callback receives `(role, model_id, success, elapsed, input_tokens, output_tokens)` for token tracking
- AuraRouter handles multi-model routing and fallback internally

The `AuraGridBridge` subclass exists as a placeholder for future integration with AuraGrid's `UnifiedRouterService` via gRPC, but is not yet implemented.

## Cross-repo contributor merging

When multiple repos are analyzed, contributors are deduplicated by email address:

1. **During summarization:** `SprintSummarizer` maintains a `contributor_map` keyed by email. If the same email appears in multiple repos, metrics come from the latest repo and qualitative summaries are concatenated.
2. **During report building:** `merge_contributors_across_repos()` unions `AuthorMetrics` fields — commit lists concatenated, files_touched unioned, line counts summed, enrichment fields merged via dedicated helpers (`merge_file_type_breakdowns`, `merge_commit_categories`, `merge_daily_activity`, `merge_change_type_stats`).

## Commit classification

Two-tier classification in `enrichment.py`:

1. **Conventional commit regex** — Matches prefixes like `feat:`, `fix(scope):`, `docs!:`, etc. Aliases normalize variants (`tests` → `test`, `build` → `chore`, `revert` → `fix`).
2. **Keyword heuristic fallback** — Scans the full message for keywords: `"add"` → feat, `"bug"` → fix, `"refactor"` → refactor, etc. First match wins.
3. **Default** — `"other"` if neither matches.

Categories: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `ci`, `style`, `perf`, `cleanup`, `other`.

## Error handling

- **Git failures:** `clone.py` raises `GitError` with subprocess returncode and stderr
- **LLM failures:** `FabricBridge.execute()` returns `None`; summarizer substitutes `"(Qualitative summary unavailable)"`
- **Missing AuraRouter:** `FabricBridge.__init__()` catches all exceptions and sets `_fabric = None`
- **CLI:** Top-level try/except prints error to stderr and exits with code 1
- **GUI:** `AnalysisWorker` emits `error` signal; progress panel displays the message
