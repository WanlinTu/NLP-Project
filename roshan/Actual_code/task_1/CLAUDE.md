# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

SEC filing factor extraction pipeline for an NLP Asset Management course (Spring 2026, AllianceBernstein partnership). Extracts thematic factors from MD&A and Risk Factors sections of 10-K/10-Q filings across ~87 industrial/defense/airline tickers, then scores sentiment via LLM.

The `sample_code/` directory in the parent folder is professor-provided reference only. Never depend on it or its outputs (including `mda_output/`). All project code lives in `Actual_code/`.

## Running the Pipeline

```bash
cd Actual_code

# Steps 1-2: HTML extraction + subsection parsing (no GPU needed)
python3 run_pipeline.py --steps 1 2

# Steps 3-4: LLM factor extraction + sentiment scoring (requires vLLM on ACCRE)
python3 run_pipeline.py --steps 3 4

# Quick LLM test on a few filings
python3 run_pipeline.py --steps 3 4 --tickers AAL --max-filings 2

# Run individual steps directly
python3 01_extract_sections.py --tickers AAL LMT --workers 4
python3 02_parse_subsections.py --tickers AAL
python3 03_factor_extraction.py --tickers AAL --max-filings 5 --workers 2
python3 04_sentiment_scoring.py --tickers AAL --batch-size 8
```

All steps are resume-safe — they skip filings that already have output files.

## Architecture

**4-step sequential pipeline**, each step reads the previous step's output:

1. **01_extract_sections.py** — Parses raw SEC filing HTML (iXBRL 2021+ and legacy formats), finds MD&A and Risk Factors via TOC anchor parsing, outputs minimal HTML preserving `<b>` headings for Step 2.
2. **02_parse_subsections.py** — Splits minimal HTML into logical subsections by bold headings (MD&A) or risk item blocks (Risk Factors). Outputs JSON with text + token estimates.
3. **03_factor_extraction.py** — Routes relevant questions (from `questions.json`) to each subsection via keyword matching (`question_router.py`), calls LLM for chunk-level Q&A, then synthesizes multi-subsection answers into consolidated per-filing factor JSONs.
4. **04_sentiment_scoring.py** — Reads factor JSONs, batches factors, calls LLM for 5-class sentiment labels (`very_negative` / `negative` / `neutral` / `positive` / `very_positive`) with rationale and confidence.

**`run_pipeline.py`** orchestrates steps as subprocesses.

### Key utilities

- **`utils/html_parser.py`** — BeautifulSoup-based SEC HTML parser. Handles both iXBRL (`<div id="...">`) and legacy (`<a name="...">`) anchor formats. Uses case-insensitive regex for anchor matching (critical fix for pre-2018 filings).
- **`utils/llm_client.py`** — OpenAI-compatible client with provider toggle (`config.PROVIDER`). Global `BoundedSemaphore` limits concurrent LLM calls. Exponential backoff retries.
- **`utils/question_router.py`** — Maps subsection titles to question categories via keyword matching. Falls back to all questions if routing yields <10 matches.

### Data flow

```
Data/{TICKER}/10-K/*.html
  → output/extracted_sections/{TICKER}/{STEM}/mda.html + risk_factors.html
  → output/subsections/{TICKER}/{STEM}_subsections.json
  → output/factors/{TICKER}/{STEM}_factors.json
  → output/factors_scored/{TICKER}/{STEM}_factors.json
```

## LLM Configuration

Configured in `config.py`. Two providers:
- **ACCRE** (primary): Qwen3-30B-A3B-Instruct via vLLM at `http://127.0.0.1:8000/v1`
- **OpenAI** (fallback): GPT-4o via standard API. Set `PROVIDER = "openai"` in config.py and export `OPENAI_API_KEY`.

## Dependencies

`beautifulsoup4`, `lxml`, `openai`. Python 3.10+.

## Data

87 tickers classified in `ticker_mapping.json` across 4 sub-sectors: airlines (5), defense (13), industrial_equipment (34), general (35). Raw filing HTMLs are in `Data/` (parent directory). `questions.json` contains 60 questions across 14 categories (46 universal + 14 sub-sector-specific).
