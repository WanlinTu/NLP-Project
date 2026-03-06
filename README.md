**Data folder (Google Drive):** https://drive.google.com/drive/folders/1bnqSx1pfY6kl5SoKOxBPCCSPH640F-b7?usp=sharing

Google Doc: https://docs.google.com/document/d/1pO_aZJfCujaOTlTdMzWrOZdifnR9t8Cg4uFwxbXjDaQ/edit?tab=t.0

---

# Reasoning-Augmented Factor Extraction from SEC Filings

Extract thematic factors from 10-K/10-Q filings across ~87 industrial/defense/airline tickers, score sentiment via LLM, and align with stock returns using reinforcement learning.

**Course:** NLP Asset Management (Spring 2026, AllianceBernstein partnership)

## Project Structure

```
fillings/
  Data/                          # Raw SEC filing HTMLs (per ticker)
  AB-VU_RLSentiment_2026Spring.pdf  # Project spec
  roshan/Actual_code/task_1/     # Pipeline notebooks + config
    task_1_1_Data_processing.ipynb
    task_1_2_Factor_extraction.ipynb
    task_1_3_Sentiment_scoring.ipynb
    task_1_5_Reasoning_model.ipynb
    questions.json               # 60 questions across 14 categories
    ticker_mapping.json          # 87 tickers across 4 sub-sectors
    requirements.txt
    output/
      extracted_sections/        # Step 1: MD&A + Risk Factors HTML
      subsections/               # Step 1: Parsed subsection JSONs
      factors/                   # Step 2: Extracted factor JSONs (sentiment: null)
      factors_scored/            # Step 3: Sentiment-scored factor JSONs
      filing_returns.csv         # Step 5: 21-day excess returns
      reasoning_output.json      # Step 5: LLM reasoning results
  sample_code/                   # Professor reference only (DO NOT USE)
```

## Pipeline

Run notebooks in order on ACCRE GPU (DGX A100 40GB):

| Step | Notebook | GPU | Description |
|------|----------|-----|-------------|
| 1 | `task_1_1_Data_processing.ipynb` | No | Parse HTML filings, extract MD&A + Risk Factors, split into subsections |
| 2 | `task_1_2_Factor_extraction.ipynb` | Yes | Route questions to subsections, chunk-level QA, synthesize factors |
| 3 | `task_1_3_Sentiment_scoring.ipynb` | Yes | Score each factor with 5-class sentiment (very_negative to very_positive) |
| 4 | `task_1_5_Reasoning_model.ipynb` | Partial | Generate returns, statistical analysis, LLM reasoning on patterns |

All steps are **resume-safe** -- they skip filings that already have output files.

## Data Flow

```
Data/{TICKER}/10-K/*.html
  -> output/extracted_sections/{TICKER}/{STEM}/mda.html + risk_factors.html
  -> output/subsections/{TICKER}/{STEM}_subsections.json
  -> output/factors/{TICKER}/{STEM}_factors.json         (sentiment: null)
  -> output/factors_scored/{TICKER}/{STEM}_factors.json   (sentiment populated)
  -> output/filing_returns.csv
  -> output/reasoning_output.json
```

## LLM Setup

- **Model:** `deepseek-ai/DeepSeek-R1-Distill-Qwen-14B` via vLLM on ACCRE
- **GPU:** DGX A100 40GB
- **Key adaptations for DeepSeek-R1:**
  - `response_format={"type": "json_object"}` to force valid JSON
  - `temperature=0.6` (DeepSeek-R1 recommendation)
  - `<think>` tag stripping in response parser
  - Pydantic models for response validation
  - JSON schema in user prompt (DeepSeek-R1 ignores system prompt formatting)

## Tickers

87 tickers across 4 sub-sectors (defined in `ticker_mapping.json`):
- **Airlines** (5): AAL, ALK, DAL, LUV, UAL
- **Defense** (13): BA, GD, HII, LHX, LLL, LMT, NOC, RTN, RTX, TDG, TXT, LDOS, COL
- **Industrial Equipment** (34): CAT, CMI, DE, DOV, EMR, ETN, FLS, GE, HON, IR, ITW, JCI, PH, ROK, SNA, SWK, TT, XYL, ...
- **General** (35): CHRW, CPRT, CSX, EFX, EXPD, FAST, FDX, GWW, JBHT, NSC, ODFL, RHI, ROL, ROP, RSG, UNP, URI, UPS, VRSK, WAB, WM, ...

## Dependencies

```
pip install -r roshan/Actual_code/task_1/requirements.txt
```

beautifulsoup4, lxml, openai, pydantic, tqdm, numpy, pandas, matplotlib, seaborn, scipy, yfinance

## Project Goals (from spec)

1. **Task 1 - Thematic Factor Discovery:** Extract factors from SEC filings, score sentiment, apply reasoning models
2. **Task 2 - Specialized Sentiment Classification:** Create ~5,000 annotated dataset, fine-tune LLM by sector/theme
3. **Task 3 - RL Alignment:** Use GRPO to align sentiment with stock returns over chosen time horizons
4. **Task 4 - Quantitative Backtesting:** Portfolio construction, sentiment cohort performance, multi-horizon analysis
