# Sprint-Snitch: Agentic Task Groups — MVP Init

> **Purpose:** This document defines the complete implementation plan for sprint-snitch as a set of agentic task groups. Each group is self-contained with profile, context, constraints, tasks, tests, and success criteria. Feed this to a Claude Opus main agent for autonomous execution and progress tracking.
>
> **Project root:** `c:\projects\sprint-snitch\`
> **Package root:** `src/sprint_snitch/`

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Execution Graph](#execution-graph)
3. [Group 0: Project Scaffold](#group-0-project-scaffold)
4. [Group 1: Data Models & Core Types](#group-1-data-models--core-types)
5. [Group 2: Git Analysis Engine](#group-2-git-analysis-engine)
6. [Group 3: LLM Integration via AuraRouter](#group-3-llm-integration-via-aurarouter)
7. [Group 4: Reporting Engine](#group-4-reporting-engine)
8. [Group 5: PySide6 GUI](#group-5-pyside6-gui)
9. [Group 6: CLI Entry Point & End-to-End Integration](#group-6-cli-entry-point--end-to-end-integration)
10. [Cross-Cutting Concerns](#cross-cutting-concerns)

---

## Architecture Overview

```
src/sprint_snitch/
    __init__.py                  # __version__ = "0.1.0"
    __main__.py                  # CLI entry (argparse: headless + gui subcommand)
    models/
        __init__.py
        data.py                  # All dataclasses: CommitInfo, AuthorMetrics, SprintReport, etc.
    git_analysis/
        __init__.py
        clone.py                 # Repo cloning/fetching via subprocess + git CLI
        diff_extractor.py        # Date-range commit extraction, diff parsing, file content retrieval
        metrics.py               # Quantitative per-author / per-repo aggregation
    llm_integration/
        __init__.py
        fabric_bridge.py         # AuraRouter ComputeFabric wrapper + AuraGrid TODO stub
        prompts.py               # Prompt templates for contributor/repo/sprint summarization
        summarizer.py            # Orchestrates all LLM calls with progress callbacks
    reporting/
        __init__.py
        report_builder.py        # Assembles SprintReport from quantitative + qualitative data
        markdown_export.py       # Renders SprintReport to Markdown with ASCII charts
    gui/
        __init__.py              # check_pyside6() guard
        app.py                   # QApplication bootstrap
        main_window.py           # QMainWindow with 3 tabs
        input_panel.py           # Repo URLs + date range input
        progress_panel.py        # Live progress / log console
        report_viewer.py         # Report display + export controls
        workers.py               # QObject background workers (QThread pattern)
tests/
    __init__.py
    conftest.py                  # Shared fixtures
    test_models.py
    test_clone.py
    test_diff_extractor.py
    test_metrics.py
    test_fabric_bridge.py
    test_prompts.py
    test_summarizer.py
    test_report_builder.py
    test_markdown_export.py
    test_cli.py
    test_workers.py
pyproject.toml
README.md
.gitignore
```

### Data Flow

```
User Input (URLs + dates)
        │
        ▼
┌─────────────────┐     ┌─────────────────────────┐
│  git_analysis/   │────▶│  models/data.py          │
│  clone → extract │     │  CommitInfo, FileChange,  │
│  → metrics       │     │  AuthorMetrics, etc.      │
└─────────────────┘     └───────────┬─────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼                               ▼
          ┌─────────────────┐             ┌─────────────────┐
          │ llm_integration/ │             │  reporting/       │
          │ fabric_bridge    │             │  report_builder   │
          │ → prompts        │────────────▶│  → markdown_export│
          │ → summarizer     │  qualitative│  (+ ASCII charts) │
          └─────────────────┘  summaries  └─────────────────┘
                    │                               │
                    │         ┌──────────┐          │
                    └────────▶│SprintReport│◀────────┘
                              └─────┬──────┘
                                    ▼
                          Markdown file output
```

### Key Integration: AuraRouter

Sprint-snitch integrates with AuraRouter via **direct Python import** (not MCP server):

```python
from aurarouter.config import ConfigLoader        # c:\projects\auracore\aurarouter\src\aurarouter\config.py
from aurarouter.fabric import ComputeFabric        # c:\projects\auracore\aurarouter\src\aurarouter\fabric.py

config = ConfigLoader(config_path)                 # Resolves ~/.auracore/aurarouter/auraconfig.yaml
fabric = ComputeFabric(config)
result = fabric.execute("reasoning", prompt)        # Returns Optional[str]; tries each model in role chain
```

**Critical API details:**
- `ComputeFabric.execute(role, prompt, json_mode=False, on_model_tried=callback)` — see `fabric.py:113-119`
- `on_model_tried` callback: adapts to 4-param `(role, model_id, success, elapsed)` or 6-param `(role, model_id, success, elapsed, input_tokens, output_tokens)` — see `fabric.py:90-111`
- Returns `None` if all models in chain fail
- Use `"reasoning"` role for all summarization (not `"coding"` or `"router"`)

**AuraGrid TODO stub:** Reference `aurarouter.auragrid.services.UnifiedRouterService` but raise `NotImplementedError`.

**PySide6 worker pattern (from AuraRouter):**
- `InferenceWorker(QObject)` with Signals — see `main_window.py:54-128`
- `QThread` + `moveToThread` + `started.connect(worker.run)` — see `main_window.py:465-487`
- Cleanup: `deleteLater()` on both thread and worker — see `main_window.py:534-540`
- Error/finish signals both connect to `thread.quit` — see `main_window.py:483-484`

---

## Execution Graph

```
Phase 0 ──── Group 0: Project Scaffold (SERIAL — must complete first)
                 │
Phase 1 ──── Group 1: Data Models  ─────────────────── (PARALLEL)
             Group 2: Git Analysis Engine ───────────── (PARALLEL)
                 │
Phase 2 ──── Group 3: LLM Integration ──────────────── (PARALLEL, depends on G1)
             Group 4: Reporting Engine ──────────────── (PARALLEL, depends on G1)
                 │
Phase 3 ──── Group 5: PySide6 GUI (SERIAL, depends on G1-G4)
                 │
Phase 4 ──── Group 6: CLI + End-to-End Integration (SERIAL, depends on G1-G5)
```

### Dependency Matrix

| Group | Depends On | Can Parallel With |
|-------|-----------|-------------------|
| G0: Scaffold | — | — |
| G1: Models | G0 | G2 |
| G2: Git Analysis | G0 | G1 |
| G3: LLM Integration | G0, G1 | G4 |
| G4: Reporting | G0, G1 | G3 |
| G5: GUI | G0, G1, G2, G3, G4 | — |
| G6: CLI + Integration | G0-G5 | — |

---

## Group 0: Project Scaffold

### Agentic Profile
**Integration/DevOps Engineer** — creates directory structures, configures tooling, initializes packaging.

### Context
All subsequent groups depend on the directory structure and `pyproject.toml` being in place. This group creates every directory and empty file so parallel groups don't conflict on path creation. The existing repo at `c:\projects\sprint-snitch\` has only a `README.md`.

### Constraints
- No business logic — only skeleton files with empty or minimal content.
- `__init__.py` files: empty or single-line docstring.
- `.py` files (non-init): single docstring placeholder (e.g., `"""Module docstring."""`).
- Git repo already exists; do NOT reinitialize. Just add `.gitignore`.
- Use `src/` layout (matches AuraRouter's `src/aurarouter/` pattern).

### Task List

1. **Create the full directory tree** under `c:\projects\sprint-snitch\`:
   ```
   src/sprint_snitch/__init__.py
   src/sprint_snitch/__main__.py
   src/sprint_snitch/models/__init__.py
   src/sprint_snitch/models/data.py
   src/sprint_snitch/git_analysis/__init__.py
   src/sprint_snitch/git_analysis/clone.py
   src/sprint_snitch/git_analysis/diff_extractor.py
   src/sprint_snitch/git_analysis/metrics.py
   src/sprint_snitch/llm_integration/__init__.py
   src/sprint_snitch/llm_integration/fabric_bridge.py
   src/sprint_snitch/llm_integration/prompts.py
   src/sprint_snitch/llm_integration/summarizer.py
   src/sprint_snitch/reporting/__init__.py
   src/sprint_snitch/reporting/report_builder.py
   src/sprint_snitch/reporting/markdown_export.py
   src/sprint_snitch/gui/__init__.py
   src/sprint_snitch/gui/app.py
   src/sprint_snitch/gui/main_window.py
   src/sprint_snitch/gui/input_panel.py
   src/sprint_snitch/gui/progress_panel.py
   src/sprint_snitch/gui/report_viewer.py
   src/sprint_snitch/gui/workers.py
   tests/__init__.py
   tests/conftest.py
   ```
   Plus one empty test file per module (listed in architecture overview).

2. **Create `pyproject.toml`** with:
   ```toml
   [build-system]
   requires = ["setuptools>=68.0", "wheel"]
   build-backend = "setuptools.backends._legacy:_Backend"

   [project]
   name = "sprint-snitch"
   version = "0.1.0"
   description = "Automated sprint report generator from git repositories"
   requires-python = ">=3.11"
   dependencies = [
       "PySide6>=6.6",
   ]

   [project.optional-dependencies]
   llm = [
       "aurarouter",  # install via: pip install -e c:\projects\auracore\aurarouter
   ]
   dev = [
       "pytest>=7.0",
       "pytest-mock",
       "pytest-cov",
       "ruff",
   ]

   [project.scripts]
   sprint-snitch = "sprint_snitch.__main__:main"

   [tool.setuptools.packages.find]
   where = ["src"]

   [tool.pytest.ini_options]
   testpaths = ["tests"]

   [tool.ruff]
   line-length = 100
   ```

3. **Create `.gitignore`**:
   ```
   __pycache__/
   *.py[cod]
   *.egg-info/
   dist/
   build/
   .eggs/
   .pytest_cache/
   .ruff_cache/
   *.egg
   .venv/
   venv/
   *.log
   sprint_report*.md
   cloned_repos/
   ```

4. **Verify** `pip install -e ".[dev]"` succeeds from the project root.

### Unit Tests
None (scaffold only).

### Criteria for Success
- All directories and placeholder files exist.
- `pip install -e ".[dev]"` completes without error.
- `python -c "import sprint_snitch"` succeeds.
- `git status` shows the full scaffold as untracked files.

---

## Group 1: Data Models & Core Types

### Agentic Profile
**Python Backend Engineer** — experienced with dataclasses, type annotations, and domain modeling for data pipelines.

### Context
Every other module imports from `models/data.py`. These dataclasses define the contract between git analysis, LLM integration, and reporting. Follow the `@dataclass` pattern from AuraRouter's `c:\projects\auracore\aurarouter\src\aurarouter\savings\models.py` — simple `@dataclass` with explicit typed fields, `__str__` helpers where useful, no inheritance hierarchies.

The data must flow: `git_analysis → models → llm_integration → models → reporting → Markdown`.

### Constraints
- Use `@dataclass` from stdlib `dataclasses` — not Pydantic (keeping dependencies minimal for MVP).
- All date/time fields: `datetime` objects internally, ISO 8601 strings in serialized form.
- All models must be JSON-serializable via a `to_dict()` method on `SprintReport`.
- `models/` imports NOTHING from other sprint_snitch modules (zero coupling).
- Use `from __future__ import annotations` for forward references.
- Use `field(default_factory=list)` for mutable defaults.

### Task List

1. **Implement `src/sprint_snitch/models/data.py`** with these dataclasses:

   - **`FileChange`**: Represents a single file's change in a commit.
     - Fields: `path: str`, `lines_added: int`, `lines_removed: int`, `change_type: str` (one of: `"added"`, `"modified"`, `"deleted"`, `"renamed"`), `content: str = ""` (full file content at this commit, for LLM context)

   - **`CommitInfo`**: A single parsed git commit.
     - Fields: `sha: str`, `author_name: str`, `author_email: str`, `message: str`, `timestamp: datetime`, `files: list[FileChange]` (default_factory), `lines_added: int = 0`, `lines_removed: int = 0`

   - **`AuthorMetrics`**: Aggregated metrics for one contributor across a repo.
     - Fields: `name: str`, `email: str`, `commit_count: int = 0`, `files_touched: list[str]` (default_factory), `lines_added: int = 0`, `lines_removed: int = 0`, `commits: list[CommitInfo]` (default_factory)

   - **`RepoAnalysis`**: Complete quantitative analysis of one repo within the date range.
     - Fields: `repo_url: str`, `repo_name: str`, `date_from: datetime`, `date_to: datetime`, `commits: list[CommitInfo]` (default_factory), `authors: dict[str, AuthorMetrics]` (default_factory), `total_commits: int = 0`, `total_lines_added: int = 0`, `total_lines_removed: int = 0`, `files_changed: list[str]` (default_factory)

   - **`ContributorSummary`**: Combines quantitative metrics with LLM-generated qualitative summary for one person.
     - Fields: `name: str`, `email: str`, `metrics: AuthorMetrics`, `qualitative_summary: str = ""` (LLM-generated)

   - **`RepoSummary`**: Combined quantitative + qualitative for one repo.
     - Fields: `repo_url: str`, `repo_name: str`, `analysis: RepoAnalysis`, `overall_summary: str = ""` (LLM-generated), `key_areas: list[str]` (default_factory)

   - **`SprintReport`**: The top-level output of the entire pipeline.
     - Fields: `date_from: datetime`, `date_to: datetime`, `repos: list[RepoSummary]` (default_factory), `contributors: list[ContributorSummary]` (default_factory), `overall_narrative: str = ""`, `generated_at: datetime` (default_factory=datetime.now), `token_usage: dict` (default_factory=dict)
     - Method: `to_dict() -> dict` — recursively serializes all nested dataclasses to dicts. Datetimes become ISO 8601 strings.

2. **Implement `src/sprint_snitch/models/__init__.py`** — re-export all dataclasses:
   ```python
   from sprint_snitch.models.data import (
       FileChange, CommitInfo, AuthorMetrics, RepoAnalysis,
       ContributorSummary, RepoSummary, SprintReport,
   )
   ```

### Unit Tests

**File: `tests/test_models.py`**

| Test | Description |
|------|-------------|
| `test_file_change_creation` | Construct FileChange with all fields, verify values. |
| `test_commit_info_defaults` | Construct CommitInfo with required fields only, verify `files=[]`, `lines_added=0`. |
| `test_author_metrics_empty` | Default AuthorMetrics has `commit_count=0`, empty lists, zero lines. |
| `test_repo_analysis_stores_authors` | Add two AuthorMetrics to RepoAnalysis.authors dict, verify retrieval by email key. |
| `test_contributor_summary_empty_qualitative` | ContributorSummary with `qualitative_summary=""` is valid. |
| `test_sprint_report_to_dict_serializable` | Build a full SprintReport with nested data, call `to_dict()`, pass to `json.dumps()` — must not raise. |
| `test_sprint_report_to_dict_datetime_format` | Verify datetimes in `to_dict()` output are ISO 8601 strings. |
| `test_sprint_report_generated_at_auto` | Construct SprintReport without explicit `generated_at`, verify it's auto-populated. |

### Criteria for Success
- All 7 dataclasses defined with correct type annotations and defaults.
- `to_dict()` produces a JSON-serializable dict (verified by `json.dumps()`).
- All 8 unit tests pass.
- Zero imports from other `sprint_snitch` modules.

---

## Group 2: Git Analysis Engine

### Agentic Profile
**Python Backend Engineer** — experienced with `subprocess`, git CLI internals, log/diff parsing, and structured data extraction.

### Context
This module is the quantitative backbone. It clones remote repos, extracts commits within a date range using `git log`, parses the output into `CommitInfo`/`FileChange` objects, retrieves full file content for LLM context, and computes per-author/per-repo aggregated metrics.

**Critical design decision:** The user wants **full file content** (not just diffs) sent to the LLM for context. This means after extracting commits, we must also run `git show <sha>:<filepath>` to retrieve the complete file content at each commit. This is the most expensive I/O operation and must be done judiciously — retrieve content only for files that changed, at the commit where they changed.

### Constraints
- Use `subprocess.run(capture_output=True, text=True, timeout=120)` for ALL git commands.
- Clone into a configurable working directory. Default: `tempfile.mkdtemp(prefix="sprint_snitch_")`.
- No dependency on GitPython or any git library — only `subprocess` + system `git`.
- Custom exception: `class GitError(Exception)` with `message`, `returncode`, `stderr` fields.
- All functions are **synchronous** — the GUI layer handles threading.
- Handle binary files gracefully in numstat (they show as `-\t-\t<filename>`).
- Handle encoding issues — use `errors="replace"` when decoding git output.
- For `git show <sha>:<path>` (file content retrieval): cap at 50KB per file. Files larger than this get truncated content with a note. Binary files get `"(binary file)"` placeholder.
- Date filtering: use `--after="YYYY-MM-DD" --before="YYYY-MM-DD"` (inclusive start, exclusive end — adjust by adding 1 day to `date_to`).

### Task List

1. **Create `src/sprint_snitch/git_analysis/__init__.py`** — export `GitError` and key functions.

2. **Implement `src/sprint_snitch/git_analysis/clone.py`**:
   - `class GitError(Exception)`: custom exception with `message: str`, `returncode: int`, `stderr: str`.
   - `clone_or_fetch(repo_url: str, work_dir: str | None = None) -> Path`:
     - Derives a safe directory name from URL via `_repo_dir_name()`.
     - If directory exists and has `.git/`: runs `git fetch --all` to update.
     - If directory doesn't exist: runs `git clone <url> <dir>`.
     - Returns the `Path` to the local repo directory.
     - On non-zero exit code: raises `GitError`.
   - `_repo_dir_name(repo_url: str) -> str`:
     - Strips protocol, replaces `/` and special chars with `_`.
     - E.g., `https://github.com/org/repo.git` → `github.com_org_repo`.

3. **Implement `src/sprint_snitch/git_analysis/diff_extractor.py`**:
   - `extract_commits(repo_path: Path, date_from: datetime, date_to: datetime) -> list[CommitInfo]`:
     - Runs `git log` with custom format and `--numstat`.
     - Format string: `--format="COMMIT_SEP%nsha:%H%nauthor_name:%an%nauthor_email:%ae%ndate:%aI%nmessage:%s"`.
     - Date range: `--after=<date_from ISO>` `--before=<date_to + 1 day ISO>`.
     - Flags: `--all` (include all branches).
     - Calls `_parse_git_log()` then `_enrich_with_file_content()`.
   - `_parse_git_log(raw_output: str) -> list[CommitInfo]`:
     - Splits on `COMMIT_SEP`, parses each block into `CommitInfo`.
     - Parses numstat lines into `FileChange` objects (without content yet).
   - `_parse_numstat_line(line: str) -> FileChange | None`:
     - Standard: `<added>\t<removed>\t<filepath>` → FileChange(change_type="modified").
     - Binary: `-\t-\t<filepath>` → FileChange(lines_added=0, lines_removed=0, change_type="modified").
     - Rename: `{old => new}` syntax → FileChange(change_type="renamed").
     - Empty/invalid → returns None.
   - `_enrich_with_file_content(repo_path: Path, commits: list[CommitInfo]) -> None`:
     - For each commit, for each file in `commit.files`:
       - Runs `git show <sha>:<filepath>`.
       - Sets `file_change.content` to the result (truncated at 50KB).
       - For deleted files: content = `"(file deleted)"`.
       - For binary files (decode error): content = `"(binary file)"`.
     - Modifies commits in-place.
   - `get_diff_text(repo_path: Path, date_from: datetime, date_to: datetime) -> str`:
     - Runs `git log -p --after=<from> --before=<to>` and returns raw unified diff output.
     - Used as supplementary context — the full patch for the entire date range.

4. **Implement `src/sprint_snitch/git_analysis/metrics.py`**:
   - `compute_author_metrics(commits: list[CommitInfo]) -> dict[str, AuthorMetrics]`:
     - Groups commits by `author_email`.
     - For each author: sums lines_added/removed, collects unique files_touched, stores commit refs.
     - Returns dict keyed by email.
   - `compute_repo_analysis(repo_url: str, commits: list[CommitInfo], date_from: datetime, date_to: datetime) -> RepoAnalysis`:
     - Calls `compute_author_metrics()`.
     - Sums totals across all commits.
     - Collects unique `files_changed`.
     - Derives `repo_name` from URL (last path segment, strip `.git`).
   - `get_changed_files(commits: list[CommitInfo]) -> list[str]`:
     - Returns sorted list of unique file paths across all commits.

### Unit Tests

**File: `tests/test_clone.py`**

| Test | Description |
|------|-------------|
| `test_repo_dir_name_https` | `https://github.com/org/repo.git` → `github.com_org_repo` |
| `test_repo_dir_name_ssh` | `git@github.com:org/repo.git` → `github.com_org_repo` |
| `test_repo_dir_name_no_extension` | `https://github.com/org/repo` → `github.com_org_repo` |
| `test_clone_or_fetch_clone_new` | Mock subprocess: no existing dir → verify `git clone` invoked with correct args. |
| `test_clone_or_fetch_fetch_existing` | Mock subprocess + existing dir with `.git/` → verify `git fetch --all` invoked. |
| `test_clone_or_fetch_git_error` | Mock subprocess returning non-zero → verify `GitError` raised with stderr. |

**File: `tests/test_diff_extractor.py`**

| Test | Description |
|------|-------------|
| `test_parse_git_log_single_commit` | Provide raw git log output for 1 commit with 2 files, verify CommitInfo fields and FileChange list. |
| `test_parse_git_log_multiple_commits` | 3 commits, verify count=3, each has correct author/sha/message. |
| `test_parse_git_log_empty_output` | Empty string → returns `[]`. |
| `test_parse_numstat_standard` | `"10\t5\tsrc/foo.py"` → FileChange(lines_added=10, lines_removed=5, path="src/foo.py"). |
| `test_parse_numstat_binary` | `"-\t-\timage.png"` → FileChange(lines_added=0, lines_removed=0). |
| `test_parse_numstat_rename` | `"0\t0\t{old => new}/file.py"` → FileChange(change_type="renamed"). |
| `test_extract_commits_date_args` | Mock subprocess, verify `--after` and `--before` arguments include correct dates. |
| `test_enrich_with_file_content` | Mock `git show`, verify FileChange.content populated. |
| `test_enrich_large_file_truncation` | Mock `git show` returning >50KB, verify content is truncated. |
| `test_enrich_binary_file` | Mock `git show` raising decode error, verify content = `"(binary file)"`. |

**File: `tests/test_metrics.py`**

| Test | Description |
|------|-------------|
| `test_compute_author_metrics_single_author` | 3 commits from same author → 1 entry, correct sums. |
| `test_compute_author_metrics_multiple_authors` | 2 authors, verify separate entries with correct attribution. |
| `test_compute_repo_analysis_totals` | Verify `total_commits`, `total_lines_added`, `total_lines_removed` match commit sums. |
| `test_compute_repo_analysis_repo_name` | `https://github.com/org/myrepo.git` → `repo_name="myrepo"`. |
| `test_get_changed_files_deduplication` | Same file in 3 commits → appears once in result. |
| `test_get_changed_files_sorted` | Files returned in alphabetical order. |

### Criteria for Success
- `clone_or_fetch` clones new repos and fetches existing ones.
- `extract_commits` correctly parses multi-commit git log output with numstat.
- Full file content is retrieved via `git show` and attached to `FileChange.content`.
- Binary and large files handled gracefully (no crashes).
- `compute_author_metrics` and `compute_repo_analysis` produce correct aggregations.
- All 22 unit tests pass.
- No dependency on GitPython or external git libraries.

---

## Group 3: LLM Integration via AuraRouter

### Agentic Profile
**Python Backend Engineer + LLM Integration Specialist** — familiar with AuraRouter's ComputeFabric API, prompt engineering for code summarization, and optional-dependency patterns.

### Context
This module wraps AuraRouter's `ComputeFabric` for generating qualitative summaries of git changes. The core API call is:

```python
# c:\projects\auracore\aurarouter\src\aurarouter\fabric.py:113-119
fabric.execute(
    role="reasoning",       # Use reasoning role for analysis/summarization
    prompt=prompt_text,
    json_mode=False,        # We want natural language, not JSON
    on_model_tried=callback # Optional: (role, model_id, success, elapsed, input_tokens, output_tokens)
)
# Returns Optional[str] — None if all models fail
```

The fabric automatically iterates through the model chain defined in `~/.auracore/aurarouter/auraconfig.yaml` under `roles.reasoning`, trying each model until one succeeds. The `on_model_tried` callback fires for each attempt (both successes and failures) and auto-adapts to 4-param or 6-param signatures (see `fabric.py:90-111`).

**AuraRouter is an optional dependency.** Sprint-snitch must work in "quantitative-only" mode when AuraRouter is not installed.

### Constraints
- Import `aurarouter` inside a try/except — graceful `ImportError` handling.
- Use `"reasoning"` role for ALL summarization calls (this is configured in the user's `auraconfig.yaml` to point at their preferred models).
- Token tracking: accumulate input/output tokens from `on_model_tried` callbacks.
- **Prompt size management:** Full file content can be large. Each prompt must stay within a configurable character limit (default: 12,000 chars for diff/file context). Truncate oldest/largest files first if over budget.
- When `fabric.execute()` returns `None`: substitute a graceful fallback string like `"(Qualitative summary unavailable — all models failed)"`.
- AuraGrid stub: `AuraGridBridge` subclass that raises `NotImplementedError` with reference to `aurarouter.auragrid.services.UnifiedRouterService`.
- Each prompt must describe its intent clearly; the exact wording is up to the implementing agent, but the purpose of each prompt is specified below.

### Task List

1. **Implement `src/sprint_snitch/llm_integration/__init__.py`** — re-export `FabricBridge`, `SprintSummarizer`.

2. **Implement `src/sprint_snitch/llm_integration/fabric_bridge.py`**:
   - `class FabricBridge`:
     - `__init__(self, config_path: str | None = None)`:
       - Try importing `aurarouter.config.ConfigLoader` and `aurarouter.fabric.ComputeFabric`.
       - On success: create `ConfigLoader(config_path)` and `ComputeFabric(config)`.
       - On `ImportError` or `FileNotFoundError`: set `self._fabric = None`.
     - `is_available(self) -> bool`: returns `True` if fabric was created successfully.
     - `execute(self, prompt: str, on_model_tried=None) -> str | None`:
       - Delegates to `self._fabric.execute("reasoning", prompt, on_model_tried=on_model_tried)`.
       - If not available: returns `None`.
       - Wraps the `on_model_tried` callback to accumulate token usage in `self._token_usage`.
     - `_token_usage: dict` — `{"input_tokens": 0, "output_tokens": 0, "calls": 0}`.
     - `get_token_usage(self) -> dict`: returns copy of `_token_usage`.
     - `reset_token_usage(self)`: zeros the counters.
   - `class AuraGridBridge(FabricBridge)`:
     - Docstring references `aurarouter.auragrid.services.UnifiedRouterService`.
     - `__init__`: raises `NotImplementedError("AuraGrid integration pending — TODO: use UnifiedRouterService from aurarouter.auragrid.services")`.

3. **Implement `src/sprint_snitch/llm_integration/prompts.py`**:
   - `build_contributor_prompt(author_name: str, metrics: AuthorMetrics, file_contents: dict[str, str]) -> str`:
     - **Intent:** Ask the LLM to write a qualitative narrative describing what this contributor worked on during the sprint. The prompt should include the contributor's name, their quantitative metrics (commits, files, lines), and the full content of files they modified. The LLM should identify themes, describe the nature of the work (bug fixes, features, refactoring, etc.), and assess the impact/scope of their contributions. Output should be 2-4 paragraphs of professional prose suitable for a sprint report.
   - `build_repo_prompt(repo_name: str, analysis: RepoAnalysis, file_contents: dict[str, str]) -> str`:
     - **Intent:** Ask the LLM to summarize the overall changes to this repository during the sprint. Include the repo name, key metrics, and file contents. The LLM should identify the major areas of change, describe what was accomplished at a high level, and list 3-5 key areas/themes of development. Output should be a structured summary with an overview paragraph followed by key areas as bullet points.
   - `build_sprint_narrative_prompt(repo_summaries: list[str], contributor_summaries: list[str]) -> str`:
     - **Intent:** Ask the LLM to synthesize the per-repo and per-contributor summaries into a cohesive overall sprint narrative. This is the executive summary. The LLM should identify cross-repo themes, highlight the most impactful changes, and provide a 2-3 paragraph narrative of what the team accomplished during the sprint period. This prompt receives the already-generated text summaries (not raw diffs/content).
   - `truncate_context(text: str, max_chars: int = 12000) -> str`:
     - Truncates text to `max_chars`, appending `"\n... (truncated, {original_len - max_chars} chars omitted)"` if truncated.
   - `build_file_context(commits: list[CommitInfo], max_chars: int = 12000) -> dict[str, str]`:
     - Collects `{filepath: content}` from all FileChange objects across commits.
     - Deduplicates (latest commit wins for same file).
     - If total chars exceed `max_chars`: drop largest files first until under budget.
     - Returns the dict for embedding in prompts.

4. **Implement `src/sprint_snitch/llm_integration/summarizer.py`**:
   - `class SprintSummarizer`:
     - `__init__(self, bridge: FabricBridge)`.
     - `summarize_contributor(self, author: AuthorMetrics, file_contents: dict[str, str], on_model_tried=None) -> str`:
       - Builds prompt via `build_contributor_prompt()`.
       - Calls `bridge.execute(prompt, on_model_tried)`.
       - Returns result or fallback: `"(Qualitative summary unavailable)"`.
     - `summarize_repo(self, analysis: RepoAnalysis, file_contents: dict[str, str], on_model_tried=None) -> str`:
       - Builds prompt via `build_repo_prompt()`.
       - Calls bridge, returns result or fallback.
     - `generate_sprint_narrative(self, repo_summaries: list[str], contributor_summaries: list[str], on_model_tried=None) -> str`:
       - Builds prompt via `build_sprint_narrative_prompt()`.
       - Calls bridge, returns result or fallback.
     - `summarize_all(self, analyses: list[RepoAnalysis], on_progress=None) -> tuple[list[ContributorSummary], list[RepoSummary], str]`:
       - Orchestrates the full qualitative pipeline:
         1. For each repo: build file context, summarize each author, summarize repo.
         2. Generate overall sprint narrative.
         3. Call `on_progress(current_step: int, total_steps: int, description: str)` at each step.
       - Returns `(contributors, repo_summaries, overall_narrative)`.
       - Deduplicates contributors across repos (by email — merge if same person contributed to multiple repos).

### Unit Tests

**File: `tests/test_fabric_bridge.py`**

| Test | Description |
|------|-------------|
| `test_bridge_not_available_no_aurarouter` | Patch `import aurarouter` to raise `ImportError`, verify `is_available()` returns `False`. |
| `test_bridge_not_available_no_config` | Patch `ConfigLoader` to raise `FileNotFoundError`, verify `is_available()` returns `False`. |
| `test_bridge_execute_delegates` | Mock `ComputeFabric.execute`, call `bridge.execute(prompt)`, verify fabric called with `role="reasoning"`. |
| `test_bridge_execute_returns_none_when_unavailable` | Bridge with `_fabric=None`, verify `execute()` returns `None`. |
| `test_bridge_token_tracking` | Fire mock `on_model_tried` callback with known tokens, verify `get_token_usage()` accumulates. |
| `test_bridge_reset_tokens` | Accumulate tokens, call `reset_token_usage()`, verify zeroed. |
| `test_auragrid_bridge_raises` | Instantiating `AuraGridBridge()` raises `NotImplementedError`. |

**File: `tests/test_prompts.py`**

| Test | Description |
|------|-------------|
| `test_contributor_prompt_contains_name` | Verify author name appears in generated prompt string. |
| `test_contributor_prompt_contains_metrics` | Verify commit count and line counts appear in prompt. |
| `test_repo_prompt_contains_repo_name` | Verify repo name appears in prompt. |
| `test_sprint_narrative_prompt_includes_summaries` | Verify repo/contributor summary text embedded in prompt. |
| `test_truncate_context_short` | Input under limit → returned unchanged. |
| `test_truncate_context_long` | Input over limit → truncated with `"(truncated..."` note. |
| `test_build_file_context_dedup` | Same file in 2 commits → latest version wins. |
| `test_build_file_context_budget` | Total content exceeds max_chars → largest files dropped. |

**File: `tests/test_summarizer.py`**

| Test | Description |
|------|-------------|
| `test_summarize_contributor_success` | Mock bridge returning text, verify non-empty result. |
| `test_summarize_contributor_fallback` | Mock bridge returning `None`, verify fallback text returned. |
| `test_summarize_repo_success` | Mock bridge, verify result. |
| `test_generate_sprint_narrative` | Mock bridge, verify narrative generated. |
| `test_summarize_all_progress` | Mock bridge, track `on_progress` calls, verify called for each step. |
| `test_summarize_all_dedup_contributors` | Same author email in 2 repos → single merged ContributorSummary. |
| `test_summarize_all_handles_empty_analyses` | Empty `analyses` list → returns empty lists and fallback narrative. |

### Criteria for Success
- `FabricBridge` correctly wraps `ComputeFabric.execute("reasoning", ...)`.
- Graceful fallback when AuraRouter is not installed — `is_available()` returns `False`, `execute()` returns `None`.
- `AuraGridBridge` raises `NotImplementedError` with clear TODO message.
- Token usage tracking accumulates correctly across multiple calls.
- Prompt builders produce well-structured prompts containing all required context.
- File context budget management prevents oversized prompts.
- All 22 unit tests pass.

---

## Group 4: Reporting Engine

### Agentic Profile
**Python Backend Engineer** — experienced with data aggregation, Markdown generation, and ASCII visualization.

### Context
This module is the convergence point: it assembles `SprintReport` from quantitative analysis (Group 2) and qualitative summaries (Group 3), then renders it to Markdown with ASCII bar charts for contribution metrics.

### Constraints
- Pure Python — no external dependencies beyond stdlib and `sprint_snitch.models`.
- Markdown must be valid GitHub-flavored Markdown (GFM).
- ASCII charts: simple horizontal bar charts using block characters (`█`, `▓`, `░`). Max width 40 characters. Used for: commits per author, lines changed per author, lines per repo.
- Handle edge cases: zero commits, single repo, missing LLM summaries (empty string).
- `report_builder.py` is stateless beyond the builder pattern (add data, then `build()`).

### Task List

1. **Implement `src/sprint_snitch/reporting/__init__.py`** — re-export `ReportBuilder`, `render_markdown`, `save_markdown`.

2. **Implement `src/sprint_snitch/reporting/report_builder.py`**:
   - `class ReportBuilder`:
     - `__init__(self, date_from: datetime, date_to: datetime)`: stores date range.
     - `add_repo_summary(self, summary: RepoSummary)`: appends to internal list.
     - `add_contributor_summary(self, summary: ContributorSummary)`: appends to internal list.
     - `set_overall_narrative(self, narrative: str)`: stores the sprint-level narrative.
     - `set_token_usage(self, usage: dict)`: stores token usage stats.
     - `build(self) -> SprintReport`: assembles and returns the final report with `generated_at=datetime.now()`.
   - `merge_contributors_across_repos(analyses: list[RepoAnalysis]) -> dict[str, AuthorMetrics]`:
     - Takes multiple `RepoAnalysis` objects, merges `AuthorMetrics` by email.
     - For the same email across repos: sums `commit_count`, `lines_added`, `lines_removed`; unions `files_touched`; concatenates `commits` lists.
     - Returns dict keyed by email.

3. **Implement `src/sprint_snitch/reporting/markdown_export.py`**:
   - `render_markdown(report: SprintReport) -> str`: produces the full Markdown document. Sections:
     1. **Header**: `# Sprint Report: <date_from> — <date_to>`, generated timestamp, list of repos analyzed.
     2. **Executive Summary** (`## Executive Summary`): the `overall_narrative` text.
     3. **Repository Summaries** (`## Repositories`): for each RepoSummary:
        - `### <repo_name>` with metrics table (total commits, lines +/-, files changed).
        - Qualitative summary paragraph.
        - Key areas as bullet list.
     4. **Contributor Summaries** (`## Contributors`): for each ContributorSummary:
        - `### <name>` with metrics table (commits, lines +/-, files touched count).
        - Qualitative summary paragraph.
     5. **Contribution Charts** (`## Activity Overview`):
        - ASCII bar chart: commits per contributor.
        - ASCII bar chart: lines changed (added + removed) per contributor.
     6. **Footer**: generation timestamp, token usage if available.
   - `_render_ascii_bar_chart(data: dict[str, int], title: str, max_width: int = 40) -> str`:
     - Takes `{label: value}` dict.
     - Normalizes to max_width using `█` characters.
     - Format per line: `<label (padded)> | <bar> <value>`.
     - Returns multi-line string.
   - `_render_metrics_table(headers: list[str], rows: list[list[str]]) -> str`:
     - Renders a GFM Markdown table with alignment.
   - `save_markdown(report: SprintReport, output_path: Path) -> Path`:
     - Calls `render_markdown()`, writes to `output_path`, returns the path.

### Unit Tests

**File: `tests/test_report_builder.py`**

| Test | Description |
|------|-------------|
| `test_build_empty_report` | No data added → SprintReport with empty lists, empty narrative. |
| `test_build_single_repo` | One RepoSummary + one ContributorSummary → correctly structured report. |
| `test_build_multiple_repos` | Two repos → both in `report.repos`. |
| `test_build_sets_generated_at` | Verify `generated_at` is within 1 second of `datetime.now()`. |
| `test_merge_contributors_same_email` | Same email in 2 repos → merged: summed lines, unioned files. |
| `test_merge_contributors_different_emails` | Different emails → separate entries. |
| `test_merge_contributors_empty` | Empty analyses list → empty dict. |

**File: `tests/test_markdown_export.py`**

| Test | Description |
|------|-------------|
| `test_render_header` | Verify date range and repo names appear in output. |
| `test_render_executive_summary` | Verify narrative text present under `## Executive Summary`. |
| `test_render_contributor_table` | Verify GFM table syntax with correct columns. |
| `test_render_ascii_chart_basic` | 2-item dict → chart with bars, labels aligned. |
| `test_render_ascii_chart_single_item` | 1-item dict → full-width bar. |
| `test_render_ascii_chart_zero_values` | All values 0 → no bars, no division-by-zero crash. |
| `test_render_empty_report` | Empty SprintReport → valid Markdown (no crash). |
| `test_render_missing_narrative` | Empty `overall_narrative` → section present but gracefully empty. |
| `test_render_special_characters` | Commit messages with `|`, `*`, etc. → properly escaped. |
| `test_save_markdown_writes_file` | Use `tmp_path`, verify file created with correct content. |

### Criteria for Success
- `ReportBuilder` correctly assembles `SprintReport` from added components.
- Cross-repo contributor merging by email works correctly.
- Markdown output is valid GFM with tables, headers, and ASCII charts.
- ASCII bar charts render correctly with proportional bars.
- Edge cases (empty report, zero values, missing narratives, special chars) handled.
- All 17 unit tests pass.

---

## Group 5: PySide6 GUI

### Agentic Profile
**PySide6 UI Engineer** — experienced with Qt6/PySide6, QThread/QObject worker pattern, Signal/Slot, and responsive desktop UIs.

### Context
The GUI follows AuraRouter's established patterns. Key references:

- **Worker pattern:** `InferenceWorker(QObject)` at `c:\projects\auracore\aurarouter\src\aurarouter\gui\main_window.py:54-128`
  - QObject with Signals, moved to QThread, `started.connect(worker.run)`, `finished.connect(thread.quit)`, `thread.finished.connect(cleanup)`.
- **Thread lifecycle:** `main_window.py:465-487` (creation), `main_window.py:534-540` (cleanup via `deleteLater()`).
- **App bootstrap:** `c:\projects\auracore\aurarouter\src\aurarouter\gui\app.py:40-48`.
- **GUI guard:** `c:\projects\auracore\aurarouter\src\aurarouter\gui\__init__.py` — `check_pyside6()` that raises helpful error if PySide6 missing.

### Constraints
- PySide6 >= 6.6.
- ALL long-running operations (clone, diff, LLM) run in `QThread` workers. Main thread never blocks.
- Progress updates ONLY via `Signal/Slot` — never manipulate widgets from worker threads.
- Follow AuraRouter naming: `_build_ui()`, `_wire_signals()`, `_on_<event>()` for slots.
- Keyboard shortcuts: `Ctrl+Return` → start analysis, `Escape` → cancel.
- Window: title "Sprint Snitch", minimum size 900×600.
- The GUI must work without AuraRouter installed (shows "AuraRouter: Not Found" status, produces quantitative-only reports).

### Task List

1. **Implement `src/sprint_snitch/gui/__init__.py`**:
   - `check_pyside6()` function: tries `import PySide6`, raises `ImportError` with install instructions if missing.

2. **Implement `src/sprint_snitch/gui/workers.py`**:
   - `class AnalysisWorker(QObject)`:
     - **Signals:**
       - `progress(int, int, str)` — (current_step, total_steps, message)
       - `repo_cloned(str)` — repo URL
       - `repo_analyzed(str)` — repo URL
       - `llm_progress(str)` — description of current LLM call
       - `model_tried(str, str, bool, float)` — (role, model_id, success, elapsed)
       - `finished(object)` — the SprintReport
       - `error(str)` — error message
     - `__init__(self, repo_urls: list[str], date_from: datetime, date_to: datetime, config_path: str | None, use_llm: bool, work_dir: str | None)`.
     - `run(self)`:
       - Step 1: Clone/fetch each repo (emit `progress` + `repo_cloned` per repo).
       - Step 2: Extract commits + compute metrics per repo (emit `progress` + `repo_analyzed`).
       - Step 3 (if `use_llm` and FabricBridge available): Run LLM summarization via `SprintSummarizer.summarize_all()` (emit `llm_progress` per call).
       - Step 4: Build report via `ReportBuilder`, emit `finished(report)`.
       - On any exception: emit `error(str(exc))`.
     - `_on_model_tried(...)`: callback adapter that emits the `model_tried` signal.
   - Worker must be robust — wrap each major step in try/except, report partial progress even on failures.

3. **Implement `src/sprint_snitch/gui/input_panel.py`**:
   - `class InputPanel(QWidget)`:
     - **Layout (vertical):**
       - QLabel "Repository URLs (one per line):"
       - QTextEdit for URLs — placeholder: "https://github.com/org/repo.git", 4-6 lines tall.
       - QHBoxLayout for date range:
         - QLabel "From:" + QDateEdit (default: 14 days ago)
         - QLabel "To:" + QDateEdit (default: today)
       - QCheckBox "Include AI-powered qualitative analysis" (checked by default, unchecked if AuraRouter unavailable)
       - QPushButton "Analyze Sprint" (prominent, primary style)
       - QLabel for AuraRouter status: "AuraRouter: Connected ✓" or "AuraRouter: Not Found (quantitative-only mode)"
     - **Signal:** `analyze_requested(list, object, object, bool)` — (urls, date_from, date_to, use_llm). Emitted when Analyze button clicked.
     - **Validation on click:**
       - At least one non-empty URL line.
       - date_from < date_to.
       - Show `QMessageBox.warning()` on validation failure.
     - **On construction:** check `FabricBridge().is_available()` to set AuraRouter status and checkbox default.

4. **Implement `src/sprint_snitch/gui/progress_panel.py`**:
   - `class ProgressPanel(QWidget)`:
     - **Layout (vertical):**
       - QLabel "Analysis Progress"
       - QProgressBar (overall progress)
       - QTextEdit (read-only, monospace font) — scrolling log console
       - QPushButton "Cancel" (disabled until analysis starts)
     - **Slots:**
       - `on_progress(current, total, message)`: update progress bar, append to log.
       - `on_repo_cloned(url)`: append "✓ Cloned: <url>" to log.
       - `on_repo_analyzed(url)`: append "✓ Analyzed: <url>" to log.
       - `on_llm_progress(desc)`: append "⚡ LLM: <desc>" to log.
       - `on_error(msg)`: append "✗ Error: <msg>" to log in red/bold.
       - `reset()`: clear log and progress bar.
     - **Signal:** `cancel_requested()` — emitted when Cancel clicked.

5. **Implement `src/sprint_snitch/gui/report_viewer.py`**:
   - `class ReportViewer(QWidget)`:
     - **Layout (vertical):**
       - QLabel "Sprint Report"
       - QTextEdit (read-only, monospace font) — displays rendered Markdown as plain text.
       - QHBoxLayout:
         - QPushButton "Export to Markdown..." → QFileDialog → `save_markdown()`.
         - QPushButton "Copy to Clipboard" → `QApplication.clipboard().setText()`.
     - **Slots:**
       - `on_report_ready(report: SprintReport)`: calls `render_markdown(report)`, displays text, enables buttons.
       - `reset()`: clears display, disables buttons.

6. **Implement `src/sprint_snitch/gui/main_window.py`**:
   - `class SprintSnitchWindow(QMainWindow)`:
     - `__init__(self)`:
       - Call `_build_ui()` and `_wire_signals()`.
       - `self._worker: AnalysisWorker | None = None`
       - `self._thread: QThread | None = None`
     - `_build_ui(self)`:
       - Window title: "Sprint Snitch"
       - Minimum size: 900×600
       - Central widget: QTabWidget with 3 tabs:
         1. "Input" → InputPanel
         2. "Progress" → ProgressPanel
         3. "Report" → ReportViewer
       - Status bar: QStatusBar with QLabel for status text
     - `_wire_signals(self)`:
       - `input_panel.analyze_requested → self._on_analyze`
       - `progress_panel.cancel_requested → self._on_cancel`
     - `_on_analyze(self, urls, date_from, date_to, use_llm)`:
       - Switch to Progress tab.
       - Reset progress panel.
       - Create `AnalysisWorker` and `QThread`.
       - Wire all worker signals to progress_panel and report_viewer slots.
       - Wire `worker.finished → self._on_finished`, `worker.error → self._on_error`.
       - Wire `worker.finished → thread.quit`, `worker.error → thread.quit`.
       - Wire `thread.finished → self._cleanup_thread`.
       - Start thread.
       - Update status bar: "Analyzing..."
     - `_on_finished(self, report)`:
       - Switch to Report tab.
       - Update status bar: "Done."
       - Call `report_viewer.on_report_ready(report)`.
     - `_on_error(self, message)`:
       - Update status bar with error.
       - Progress panel shows error.
     - `_on_cancel(self)`:
       - If thread running: `thread.quit()`, `thread.wait(3000)`.
       - Cleanup thread.
       - Update status bar: "Cancelled."
     - `_cleanup_thread(self)`:
       ```python
       if self._thread:
           self._thread.deleteLater()
           self._thread = None
       if self._worker:
           self._worker.deleteLater()
           self._worker = None
       ```
     - `closeEvent(self, event)`: cleanup thread, accept event.
     - Keyboard shortcuts: `Ctrl+Return` → `_on_analyze`, `Escape` → `_on_cancel`.

7. **Implement `src/sprint_snitch/gui/app.py`**:
   - `def launch_gui() -> None`:
     ```python
     from sprint_snitch.gui import check_pyside6
     check_pyside6()
     from PySide6.QtWidgets import QApplication
     from sprint_snitch.gui.main_window import SprintSnitchWindow
     import sys
     app = QApplication(sys.argv)
     app.setApplicationName("Sprint Snitch")
     window = SprintSnitchWindow()
     window.show()
     sys.exit(app.exec())
     ```

### Unit Tests

**File: `tests/test_workers.py`**

| Test | Description |
|------|-------------|
| `test_worker_emits_progress` | Mock `clone_or_fetch` and `extract_commits`, run worker in a QThread, verify `progress` signal emitted with correct (current, total, message). |
| `test_worker_emits_finished_with_report` | Mock full pipeline, verify `finished` signal carries a `SprintReport` instance. |
| `test_worker_emits_error_on_clone_failure` | Mock `clone_or_fetch` to raise `GitError`, verify `error` signal emitted. |
| `test_worker_no_llm_mode` | Set `use_llm=False`, mock git_analysis, verify report produced without LLM calls. |
| `test_worker_llm_unavailable_graceful` | Set `use_llm=True` but mock `FabricBridge.is_available()` returning False → quantitative-only report produced. |

### Criteria for Success
- GUI launches with `launch_gui()` and displays 3 tabs.
- User can enter repo URLs (multi-line text) and date range (date pickers).
- AuraRouter status correctly detected and displayed on launch.
- Clicking "Analyze" starts background worker; UI remains responsive.
- Progress tab shows real-time updates (cloning, analyzing, LLM progress).
- Report tab displays rendered Markdown after completion.
- "Export to Markdown" opens file dialog and saves.
- "Copy to Clipboard" works.
- Cancel stops the background thread.
- `Ctrl+Return` and `Escape` shortcuts work.
- Graceful behavior when AuraRouter is unavailable.
- All 5 unit tests pass.

---

## Group 6: CLI Entry Point & End-to-End Integration

### Agentic Profile
**Integration/DevOps Engineer** — experienced with argparse, end-to-end testing, and wiring modules together.

### Context
This group wires everything into a CLI entry point and provides shared test fixtures. The CLI mirrors AuraRouter's pattern from `c:\projects\auracore\aurarouter\src\aurarouter\cli.py` (argparse with subcommands). The CLI must support both headless (for CI/automation) and GUI modes.

### Constraints
- `python -m sprint_snitch` must work via `__main__.py`.
- CLI and GUI share the same pipeline logic — the CLI just orchestrates synchronously without Qt.
- Exit code 0 on success, 1 on error.
- `--no-llm` flag for quantitative-only mode.
- Console output during headless: print progress to stderr, final report path to stdout.

### Task List

1. **Implement `src/sprint_snitch/__init__.py`**:
   ```python
   """Sprint Snitch — Automated sprint report generator from git repositories."""
   __version__ = "0.1.0"
   ```

2. **Implement `src/sprint_snitch/__main__.py`**:
   - `def main()`:
     - Parse args with `argparse.ArgumentParser(description="Sprint Snitch — Automated sprint report generator")`.
     - Subcommands:
       - `gui`: launches PySide6 GUI via `launch_gui()`. No additional required args.
       - Default (no subcommand): headless mode requiring `--repos`.
     - Headless args:
       - `--repos` (nargs="+", required in headless mode): remote git URLs.
       - `--from-date`: ISO date string (default: 14 days ago).
       - `--to-date`: ISO date string (default: today).
       - `--output` / `-o`: output file path (default: `sprint_report.md`).
       - `--work-dir`: directory for cloned repos (default: temp dir).
       - `--no-llm`: skip LLM summarization.
       - `--config`: path to AuraRouter config file.
     - Headless execution flow:
       1. Print "Sprint Snitch v{__version__}" to stderr.
       2. For each repo: clone/fetch, print progress to stderr.
       3. For each repo: extract commits + compute metrics.
       4. If not `--no-llm`: create FabricBridge + SprintSummarizer, run summarization.
       5. Build report via ReportBuilder.
       6. Save to Markdown via `save_markdown()`.
       7. Print output path to stdout.
       8. Exit 0.
     - On error: print error to stderr, exit 1.
   - `if __name__ == "__main__": main()`

3. **Update `README.md`** with:
   - One-line project description.
   - Installation: `pip install -e ".[dev]"` and optional `pip install -e ".[llm]"`.
   - Quick start (CLI headless):
     ```
     sprint-snitch --repos https://github.com/org/repo1 https://github.com/org/repo2 \
                   --from-date 2025-01-01 --to-date 2025-01-14 -o report.md
     ```
   - Quick start (GUI): `sprint-snitch gui`.
   - AuraRouter integration note: install aurarouter and configure `~/.auracore/aurarouter/auraconfig.yaml`.
   - `--no-llm` for quantitative-only reports.

4. **Implement `tests/conftest.py`** with shared fixtures:
   - `sample_file_change() -> FileChange`: fixture returning a realistic FileChange.
   - `sample_commit_info() -> CommitInfo`: fixture with 2 FileChanges.
   - `sample_author_metrics() -> AuthorMetrics`: fixture with 3 commits.
   - `sample_repo_analysis() -> RepoAnalysis`: fixture with 2 authors.
   - `sample_sprint_report() -> SprintReport`: full report with 1 repo, 2 contributors.
   - `mock_fabric_bridge()`: fixture returning a mock FabricBridge where `is_available()=True` and `execute()` returns canned summary text.

### Unit Tests

**File: `tests/test_cli.py`**

| Test | Description |
|------|-------------|
| `test_main_help` | Run `main(["--help"])`, catch `SystemExit(0)`, verify no crash. |
| `test_main_gui_subcommand` | Mock `launch_gui`, run `main(["gui"])`, verify `launch_gui` called. |
| `test_main_headless_no_repos` | Run `main([])` (no repos, no subcommand) → `SystemExit(2)` (argparse error). |
| `test_main_headless_quantitative` | Mock all git_analysis functions, run with `--repos URL --no-llm -o tmpfile`, verify Markdown file created. |
| `test_main_headless_with_llm` | Mock git_analysis + FabricBridge, run without `--no-llm`, verify LLM summarization invoked. |
| `test_main_date_defaults` | Run with `--repos URL --no-llm` without date args, verify defaults to last 14 days. |
| `test_main_git_error_exits_1` | Mock `clone_or_fetch` to raise `GitError`, verify `SystemExit(1)`. |

### Criteria for Success
- `python -m sprint_snitch gui` launches the GUI.
- `python -m sprint_snitch --repos <URL> --no-llm -o report.md` produces a valid Markdown file.
- `python -m sprint_snitch --repos <URL> -o report.md` (with AuraRouter configured) produces a report with qualitative summaries.
- Date defaults work (last 14 days).
- Error handling: git failures produce exit code 1 with helpful message.
- conftest.py fixtures are importable by all test files.
- `README.md` contains accurate usage instructions.
- All 7 unit tests pass.
- Full pipeline test: `pip install -e ".[dev]"` → `pytest tests/ -x -q` → all pass.

---

## Cross-Cutting Concerns

### Error Handling Strategy

| Layer | Error Type | Handling |
|-------|-----------|----------|
| git_analysis | `GitError` (clone fail, parse fail) | Raised to caller; CLI prints + exits 1; GUI emits `error` signal |
| llm_integration | `fabric.execute()` returns `None` | Substitute fallback text: `"(Qualitative summary unavailable)"` |
| llm_integration | `ImportError` (no aurarouter) | `FabricBridge.is_available()` returns `False`; skip LLM entirely |
| gui/workers | Any exception in `run()` | Caught at top level, emitted via `error(str)` signal |
| reporting | Edge cases (empty data) | Produce valid but minimal Markdown |

### Logging

```python
import logging

def get_logger(name: str = "SprintSnitch") -> logging.Logger:
    return logging.getLogger(name)
```

Use child loggers per module: `get_logger("SprintSnitch.GitAnalysis")`, `get_logger("SprintSnitch.LLM")`, etc.

### Testing Commands

```bash
# Install in dev mode
pip install -e ".[dev]"

# Run all tests
pytest tests/ -x -q

# Run specific group's tests
pytest tests/test_models.py -v
pytest tests/test_clone.py tests/test_diff_extractor.py tests/test_metrics.py -v
pytest tests/test_fabric_bridge.py tests/test_prompts.py tests/test_summarizer.py -v
pytest tests/test_report_builder.py tests/test_markdown_export.py -v
pytest tests/test_workers.py -v
pytest tests/test_cli.py -v

# Coverage
pytest tests/ --cov=sprint_snitch --cov-report=term-missing
```

### AuraGrid Integration TODO Summary

The following locations need future AuraGrid integration:

| File | What | Reference |
|------|------|-----------|
| `llm_integration/fabric_bridge.py` | `AuraGridBridge` class | `aurarouter.auragrid.services.UnifiedRouterService` |
| `gui/input_panel.py` | Environment selector (local vs grid) | `aurarouter.gui.app._create_context()` pattern |
| `__main__.py` | `--environment` CLI flag | `aurarouter.cli` environment arg pattern |

### Total Test Count

| Group | Test File(s) | Count |
|-------|-------------|-------|
| G1: Models | `test_models.py` | 8 |
| G2: Git Analysis | `test_clone.py`, `test_diff_extractor.py`, `test_metrics.py` | 22 |
| G3: LLM Integration | `test_fabric_bridge.py`, `test_prompts.py`, `test_summarizer.py` | 22 |
| G4: Reporting | `test_report_builder.py`, `test_markdown_export.py` | 17 |
| G5: GUI | `test_workers.py` | 5 |
| G6: CLI | `test_cli.py` | 7 |
| **Total** | | **81** |

### Estimated Lines of Code

| Group | Module | Est. LOC |
|-------|--------|----------|
| G0: Scaffold | (config only) | ~50 |
| G1: Models | `models/data.py` | ~130 |
| G2: Git Analysis | `git_analysis/*` | ~350 |
| G3: LLM Integration | `llm_integration/*` | ~300 |
| G4: Reporting | `reporting/*` | ~300 |
| G5: GUI | `gui/*` | ~550 |
| G6: CLI | `__main__.py`, conftest | ~200 |
| **Total** | | **~1,880** |
