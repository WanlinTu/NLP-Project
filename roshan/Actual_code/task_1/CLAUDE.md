# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

SEC filing factor extraction pipeline for an NLP Asset Management course (Spring 2026, AllianceBernstein partnership). Extracts thematic factors from MD&A and Risk Factors sections of 10-K/10-Q filings across ~87 industrial/defense/airline tickers, then scores sentiment via LLM.

**IMPORTANT: `sample_code/` is professor-provided reference only.** Never depend on it, import from it, or use its outputs (including `mda_output/`, `filing_returns_1m.csv`, `factors/`). The tickers, data files, and schemas in `sample_code/` do NOT match our project — e.g., `sample_code/filing_returns_1m.csv` contains ~80 tech tickers (AAPL, MSFT, etc.) while our project uses 87 industrial/defense/airline tickers. All project code and data lives exclusively in `Actual_code/`.

## Running the Pipeline (Notebooks)

The primary pipeline runs as Jupyter notebooks on ACCRE GPU nodes. Each notebook is self-contained and resume-safe.

```
# Run in order on ACCRE Jupyter (GPU session, RTX A6000, account p_dsi_acc):
task_1_1_Data_processing.ipynb       # Steps 1-2: HTML extraction + subsection parsing (no GPU needed)
task_1_2_Factor_extraction.ipynb     # Step 3: LLM factor extraction (requires vLLM)
task_1_3_Sentiment_scoring.ipynb     # Step 4: LLM sentiment scoring (requires vLLM)
task_1_5_Reasoning_model.ipynb       # Steps 5-11: Returns, analysis, LLM reasoning (Steps 1-7 no GPU; 8-9 require vLLM)
```

Each notebook has a ticker filter (default `["AAL"]` for testing). Comment out the filter line to process all 87 tickers.

### Running the Pipeline (CLI — alternative)

```bash
python3 run_pipeline.py --steps 1 2                              # no GPU
python3 run_pipeline.py --steps 3 4                              # requires vLLM
python3 run_pipeline.py --steps 3 4 --tickers AAL --max-filings 2  # quick test
```

All steps are resume-safe — they skip filings that already have output files.

## Architecture

**5-step sequential pipeline**, each step reads the previous step's output:

1. **task_1_1 / 01+02** — Parses raw SEC filing HTML (iXBRL 2021+ and legacy formats), finds MD&A and Risk Factors via TOC anchor parsing, splits into logical subsections by bold headings. Outputs JSON with text + token estimates.
2. **task_1_2 / 03** — Routes relevant questions (from `questions.json`) to each subsection via keyword matching, calls LLM for chunk-level Q&A (concurrent batches via ThreadPoolExecutor), then synthesizes multi-subsection answers into consolidated per-filing factor JSONs.
3. **task_1_3 / 04** — Reads factor JSONs, batches factors (8 per LLM call), scores concurrently via ThreadPoolExecutor for 5-class sentiment labels (`very_negative` / `negative` / `neutral` / `positive` / `very_positive`) with rationale and confidence.
4. **task_1_5** — Generates 21-day post-filing excess returns via `yfinance`, performs statistical analysis (factor coverage, Spearman IC, sentiment-return correlation), produces visualizations (stacked bar, heatmaps, scatter), then runs LLM pairwise+synthesis reasoning to identify factor-return patterns. Outputs `filing_returns.csv` and `reasoning_output.json`.

### Notebook LLM client

Each notebook inlines a self-contained LLM client (no imports from `utils/`):
- `call_llm()` — OpenAI-compatible, `BoundedSemaphore(4)` concurrency, exponential backoff retries
- `parse_json_response()` — strips markdown code blocks, fallback JSON extraction
- `call_llm_json()` — combines both above
- Hardcoded to ACCRE vLLM: `http://127.0.0.1:8000/v1`, model `Qwen/Qwen2.5-14B-Instruct`

### CLI utilities (used by .py scripts only)

- **`utils/html_parser.py`** — BeautifulSoup-based SEC HTML parser. Handles both iXBRL (`<div id="...">`) and legacy (`<a name="...">`) anchor formats. Uses case-insensitive regex for anchor matching (critical fix for pre-2018 filings).
- **`utils/llm_client.py`** — OpenAI-compatible client with provider toggle (`config.PROVIDER`). Global `BoundedSemaphore` limits concurrent LLM calls. Exponential backoff retries.
- **`utils/question_router.py`** — Maps subsection titles to question categories via keyword matching. Falls back to all questions if routing yields <10 matches.

### Data flow

```
Data/{TICKER}/10-K/*.html
  → output/extracted_sections/{TICKER}/{STEM}/mda.html + risk_factors.html
  → output/subsections/{TICKER}/{STEM}_subsections.json
  → output/factors/{TICKER}/{STEM}_factors.json       (sentiment: null)
  → output/factors_scored/{TICKER}/{STEM}_factors.json (sentiment populated)
  → output/filing_returns.csv                          (21-day excess returns)
  → output/reasoning_output.json                       (LLM reasoning results)
```

## LLM Configuration

**Notebooks**: Hardcoded to ACCRE vLLM — `Qwen/Qwen2.5-14B-Instruct` at `http://127.0.0.1:8000/v1`.

**CLI scripts** (`config.py`): Two providers:
- **ACCRE** (primary): Qwen3-30B-A3B-Instruct via vLLM at `http://127.0.0.1:8000/v1`
- **OpenAI** (fallback): GPT-4o via standard API. Set `PROVIDER = "openai"` in config.py and export `OPENAI_API_KEY`.

## Dependencies

`beautifulsoup4`, `lxml`, `openai`, `yfinance`, `scipy`. Python 3.10+.

## Data

87 tickers classified in `ticker_mapping.json` across 4 sub-sectors: airlines (5), defense (13), industrial_equipment (34), general (35). Raw filing HTMLs are in `Data/` (parent directory). `questions.json` contains 60 questions across 14 categories (46 universal + 14 sub-sector-specific).
