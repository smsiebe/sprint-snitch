# Sprint Snitch — Developer Guide

## Project overview

Sprint Snitch is an automated sprint report generator. It clones git repos, extracts commits over a date range, computes quantitative metrics, optionally generates qualitative LLM summaries via AuraRouter, and renders a Markdown report.

## Project structure

```
src/sprint_snitch/
├── __init__.py                  # Version string (__version__)
├── __main__.py                  # CLI entry point (argparse + headless pipeline)
├── models/
│   └── data.py                  # All dataclasses (12 types, stdlib @dataclass only)
├── git_analysis/
│   ├── clone.py                 # clone_or_fetch() via subprocess
│   ├── diff_extractor.py        # extract_commits() parses git log --numstat
│   ├── metrics.py               # compute_author_metrics(), compute_repo_analysis()
│   └── enrichment.py            # Pure computation: file types, commit categories, timelines, churn
├── llm_integration/
│   ├── fabric_bridge.py         # FabricBridge wraps AuraRouter ComputeFabric
│   ├── prompts.py               # Prompt builders + context truncation (12k char budget)
│   └── summarizer.py            # SprintSummarizer orchestrates the LLM pipeline
├── reporting/
│   ├── report_builder.py        # ReportBuilder (builder pattern) + cross-repo contributor merging
│   └── markdown_export.py       # Markdown rendering with GFM tables + ASCII bar charts
└── gui/
    ├── app.py                   # launch_gui() entry point
    ├── main_window.py           # QMainWindow with 3 tabs, QThread lifecycle
    ├── input_panel.py           # URL input, date pickers, LLM toggle
    ├── progress_panel.py        # Progress bar + log console
    ├── report_viewer.py         # Report display + export/clipboard
    └── workers.py               # AnalysisWorker (QObject on QThread)
```

## Key conventions

- **Dataclasses only** — All models use `@dataclass` from stdlib. No Pydantic.
- **Subprocess for git** — All git operations use `subprocess.run()`. No GitPython.
- **Pure enrichment** — `enrichment.py` has zero I/O. It takes parsed data and computes analytics.
- **Graceful LLM degradation** — `FabricBridge` catches `ImportError`/`FileNotFoundError` and disables itself. Always check `bridge.is_available()`.
- **AuraRouter is a library import** — Sprint-snitch imports `aurarouter.config.ConfigLoader` and `aurarouter.fabric.ComputeFabric` directly. It does NOT connect to a running AuraRouter process over the network.
- **Prompt context budget** — LLM prompts cap file content at 12,000 characters via `truncate_context()`.
- **File content cap** — Individual file contents are truncated at 50KB during extraction.
- **Contributors deduped by email** — When analyzing multiple repos, authors with the same email are merged (metrics unioned, summaries concatenated).
- **Builder pattern** — `ReportBuilder` assembles `SprintReport` from components.
- **Qt threading** — GUI uses `QThread` + `QObject` worker with Signal/Slot. The worker is moved to a thread, not subclassed.

## Testing

```bash
pytest tests/ -x -q
```

- ~120 tests across 13 test files + conftest.py
- Shared fixtures in `conftest.py` build layered test data
- Git operations are mocked via `unittest.mock.patch` on `subprocess.run`
- LLM bridge is mocked with configurable return values and token tracking
- GUI workers tested with `QCoreApplication`

## Common tasks

### Adding a new data model field
1. Add field to the dataclass in `models/data.py`
2. Populate it in the appropriate pipeline stage (metrics, enrichment, or summarizer)
3. Render it in `markdown_export.py`
4. Update fixtures in `conftest.py` if needed
5. Add tests

### Adding a new report section
1. Create a `_render_*()` function in `markdown_export.py`
2. Add it to the `sections` list in `render_markdown()`
3. Return empty string if no data (section is skipped)

### Adding a new enrichment metric
1. Add the computation function to `enrichment.py` (pure function, no I/O)
2. Call it from `enrich_repo_analysis()`
3. Add per-author variant if needed
4. Add merge helper if the metric needs cross-repo merging

## Dependencies

- **Required:** PySide6 >= 6.6
- **Optional:** `aurarouter` (installed via `pip install -e ".[llm]"`)
- **Dev:** pytest, pytest-mock, pytest-cov, ruff

## Ruff config

Line length: 100. Config in `pyproject.toml`.
