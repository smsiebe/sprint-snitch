# Sprint Snitch

Automated sprint report generator that analyzes git repositories to produce comprehensive end-of-sprint reports. Combines quantitative metrics (commits, lines changed, file types, churn) with optional AI-powered qualitative summaries via [AuraRouter](https://github.com/auracore-dynamics/aurarouter).

## Features

- **Multi-repo analysis** — Analyze one or more git repositories across a date range
- **Quantitative metrics** — Commits, lines added/removed, files changed, contributor breakdown
- **Rich analytics** — File type breakdown, conventional commit classification, daily activity timelines, churn detection, weekday/weekend splits
- **AI-powered summaries** (optional) — Per-contributor narratives, per-repo overviews, and executive sprint summaries via AuraRouter's multi-model LLM fabric
- **Dual interface** — Headless CLI for automation or PySide6 desktop GUI with live progress
- **Graceful degradation** — Works without AuraRouter installed; produces quantitative-only reports

## Requirements

- Python 3.11+
- Git (accessible on `PATH`)
- PySide6 >= 6.6

## Installation

```bash
# Clone the repository
git clone https://github.com/auracore-dynamics/sprint-snitch.git
cd sprint-snitch

# Install (basic — quantitative reports only)
pip install -e .

# Install with LLM support
pip install -e ".[llm]"

# Install with dev dependencies
pip install -e ".[dev]"
```

### LLM support

The `[llm]` extra installs the `aurarouter` package. Sprint-snitch imports AuraRouter as a Python library — it does not connect to a running AuraRouter instance over the network. The `aurarouter` package must be installed in the **same Python environment** as sprint-snitch.

If you have AuraRouter checked out locally:

```bash
pip install -e path/to/aurarouter
```

You also need a valid `auraconfig.yaml` at one of these locations:
1. Path passed via `--config`
2. `AURACORE_ROUTER_CONFIG` environment variable
3. `~/.auracore/aurarouter/auraconfig.yaml` (default)

## Usage

### CLI (headless)

```bash
# Basic usage — last 14 days, single repo
sprint-snitch --repos https://github.com/org/repo.git

# Multiple repos with custom date range
sprint-snitch \
  --repos https://github.com/org/repo-a.git https://github.com/org/repo-b.git \
  --from-date 2026-01-01 \
  --to-date 2026-01-14 \
  -o my_report.md

# Quantitative-only (skip LLM even if available)
sprint-snitch --repos https://github.com/org/repo.git --no-llm

# Custom AuraRouter config
sprint-snitch --repos https://github.com/org/repo.git --config /path/to/auraconfig.yaml

# Custom working directory for cloned repos
sprint-snitch --repos https://github.com/org/repo.git --work-dir ./repos
```

### CLI options

| Flag | Default | Description |
|------|---------|-------------|
| `--repos URL [URL ...]` | *(required)* | One or more remote git repository URLs |
| `--from-date YYYY-MM-DD` | 14 days ago | Start of the date range (inclusive) |
| `--to-date YYYY-MM-DD` | today | End of the date range (inclusive) |
| `-o, --output PATH` | `sprint_report.md` | Output file path |
| `--work-dir DIR` | temp directory | Directory for cloned/fetched repos |
| `--no-llm` | off | Skip LLM summarization |
| `--config PATH` | AuraRouter default | Path to `auraconfig.yaml` |
| `--version` | — | Print version and exit |

### GUI

```bash
sprint-snitch gui
```

The GUI provides three tabs:

1. **Input** — Enter repository URLs, pick a date range, toggle LLM summarization
2. **Progress** — Live progress bar and scrolling log with model fallback details
3. **Report** — View the rendered report, export to file, or copy to clipboard

Keyboard shortcuts: `Ctrl+Enter` to start analysis, `Escape` to cancel.

## Report output

Generated reports include:

| Section | Requires LLM |
|---------|:---:|
| Executive Summary | Yes |
| Repository metrics (commits, lines, files, contributors) | No |
| Repository qualitative summary + key areas | Yes |
| Contributor metrics | No |
| Contributor qualitative narrative | Yes |
| Activity Overview (ASCII bar charts) | No |
| File Type Breakdown (tables + charts per repo and contributor) | No |
| Commit Categories (conventional commit distribution) | No |
| Sprint Timeline (daily activity chart, peak day, weekday/weekend) | No |
| Change Analysis (add/modify/delete/rename + top 10 churned files) | No |
| LLM token usage footer | Yes |

## How it works

1. **Clone/fetch** — Clones repos fresh or fetches updates into a working directory
2. **Extract** — Parses `git log --numstat` output into structured commit data with file contents (capped at 50KB per file)
3. **Compute metrics** — Aggregates per-author and per-repo quantitative stats
4. **Enrich** — Classifies file types (40+ languages), categorizes commits (conventional commit regex + keyword heuristics), computes daily timelines, change types, and file churn
5. **Summarize** (optional) — Sends structured prompts to AuraRouter's `reasoning` role for contributor narratives, repo overviews, and an executive sprint narrative
6. **Render** — Assembles a Markdown report with GFM tables and ASCII bar charts

See [architecture.md](architecture.md) for detailed design documentation.

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -x -q

# Run linter
ruff check src/ tests/
```

### Test suite

The project has ~120 tests covering all modules:

| Area | Test file |
|------|-----------|
| Data models | `test_models.py` |
| Git cloning | `test_clone.py` |
| Commit parsing | `test_diff_extractor.py` |
| Metrics computation | `test_metrics.py` |
| Analytics enrichment | `test_enrichment.py` |
| LLM bridge | `test_fabric_bridge.py` |
| Prompt building | `test_prompts.py` |
| Summarization pipeline | `test_summarizer.py` |
| Report assembly | `test_report_builder.py` |
| Markdown rendering | `test_markdown_export.py` |
| CLI | `test_cli.py` |
| GUI workers | `test_workers.py` |

## License

MIT License. Copyright 2026 Steven Siebert.
