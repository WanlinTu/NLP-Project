# Handoff Document: AB-VU RLSentiment 2026 Spring — GPT OSS Migration on ACCRE

**Purpose:** Full context for assisting with migrating from OpenAI GPT-4o API to GPT OSS (open-source LLM) on Vanderbilt's ACCRE HPC cluster, to run factor extraction and downstream cells without paid API costs.

---

## 1. Project Overview

**Project:** Reasoning-Augmented Factor Extraction: Enhancing SEC Sentiment Signals through Reinforcement Learning (AB-VU RLSentiment 2026 Spring)

**Objective:** Turn SEC filings (10-K, 10-Q, 8-K) into investment signals by:
1. Extracting thematic factors from MD&A sections
2. Classifying sentiment per factor (5-class: very bad → very good)
3. (Future) RL alignment and backtesting

**Reference:** `AB-VU_RLSentiment_2026Spring.pdf` in this repo.

---

## 2. Current Pipeline (Step-by-Step)

The main workflow lives in `sample_code/DATA.ipynb`. Execution order:

| Step | Cell / Action | What It Does |
|------|---------------|---------------|
| **1** | Cell 2: `%run cut_mda.py --in_root ../Data --out_root ../Data/mda_output` | Extracts MD&A HTML from raw SEC filings. **No LLM.** Uses lxml, BeautifulSoup. |
| **2** | Cell 3: Factor Extraction | **Uses OpenAI.** Reads `Data/mda_output/mda_clean/*_mda.html`, chunks, calls LLM per chunk (extract) + per report (synthesize). Writes to `factors/mda_factors/{TICKER}/*_FACTORS_DETAILED.json` |
| **3** | Cell 7: df Builder | Builds `df` from factor JSONs + `filing_returns_1m.csv` for event study. **No LLM.** |
| **4** | Cell 8: Event Study | Backtests sentiment vs returns. **No LLM.** |
| **5** | Cell 5: 5-Label Rescore | **Uses OpenAI.** Re-scores factor sentiments to strict 5-class. Updates files in-place in `factors/mda_factors/`. |
| **6** | Cell 11: Majority Vote | **Uses OpenAI.** Multiple stochastic votes per factor, majority-wins. Writes to `factors/mda_factors_mv10/`. |

---

## 3. Where the OpenAI API Is Used

All LLM calls use `openai` Python client with:

```python
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
resp = client.chat.completions.create(model=..., messages=..., tools=..., tool_choice=...)
```

**Critical:** The pipeline uses **tool/function calling**. Each call passes `tools=[{...}]` and `tool_choice={...}`. The model must return structured JSON via `tool_calls[0].function.arguments`. **Not all open-source models support this.**

### 3.1 Factor Extraction (Cell 3)

- **call_extract(client, model, prompt, chunk_id)**  
  - Tool: `record_answers`  
  - Purpose: Per-chunk Q&A extraction. Returns `{chunk_id, answers: [{key, found, summary, evidence}]}`  
  - Called: ~10–30 times per filing (one per HTML chunk)

- **call_synthesize(client, model, prompt)**  
  - Tool: `compile_factors`  
  - Purpose: Cross-chunk synthesis. Returns `{items: [{factor, detailed_summary, impact: {classification, rationale}}]}`  
  - Called: 1–2 times per filing (batches of ~18 factors)

- **Model:** `gpt-4o-2024-08-06` (EXTRACT_MODEL, SYNTH_MODEL)
- **Config:** `MAX_WORKERS_REPORTS=5`, `MAX_WORKERS_CHUNKS=10`, `MAX_IN_FLIGHT_OPENAI=6`
- **Input:** `BASE_DIR = "../Data/mda_output/mda_clean"`
- **Output:** `factors/mda_factors/{TICKER}/{TICKER}_{MM-DD-YYYY}_{FORM}_FACTORS_DETAILED.json`
- **Intermediate:** `factors/intermediate/{TICKER}/*.answers.json`, `*__index.json`

### 3.2 5-Label Rescore (Cell 5)

- **call_openai_score(items)** — Tool: `score_factors`  
  - Purpose: Map 4-class (Tailwind/Headwind/Mixed/Unclear) → 5-class (very bad/bad/neutral/good/very good)  
  - Returns: `{factor: classification}`  
- **Input:** `INPUT_ROOT = "factors/mda_factors"`
- **Output:** In-place update to same JSON files

### 3.3 Majority Vote (Cell 11)

- **one_vote(items_slim)** — Tool: `score_factors`  
  - Purpose: N stochastic votes per factor, majority wins  
  - Config: `N_VOTES=10`, `TEMPERATURE_VOTE=0.4`
- **Output:** `factors/mda_factors_mv10/{TICKER}/*.json` (copy, not in-place)

---

## 4. Data Layout and Formats

### 4.1 Directory Structure

```
fillings/
├── Data/
│   ├── {TICKER}/
│   │   ├── 10-K/*.html
│   │   └── 10-Q/*.html
│   └── mda_output/          # Output of cut_mda.py
│       ├── mda_clean/       # *_mda.html — INPUT to factor extraction
│       ├── mda_structured/
│       ├── mda_factors/     # cut_mda metadata, not LLM factors
│       └── mda_metadata/
├── sample_code/
│   ├── DATA.ipynb           # Main pipeline
│   ├── cut_mda.py           # MD&A extraction
│   ├── questions.json       # Factor taxonomy (~50 questions)
│   ├── filing_returns_1m.csv
│   ├── .env                 # OPENAI_API_KEY (will change for GPT OSS)
│   └── factors/
│       ├── intermediate/{TICKER}/  # Chunks, answers
│       ├── mda_factors/{TICKER}/   # Final factor JSONs
│       └── mda_factors_mv10/      # Majority-vote output
├── tickers_cik_sec.csv
├── AB-VU_RLSentiment_2026Spring.pdf
└── handoff.md               # This file
```

### 4.2 Factor JSON Schema (Output of Factor Extraction)

```json
{
  "source_file": "...",
  "model": "gpt-4o-2024-08-06",
  "company_hint": "AAL",
  "filing_hint": "10-K",
  "report_date": "02-25-2015",
  "num_factors": 18,
  "factors": [
    {
      "factor": "end_markets.regional_mix",
      "detailed_summary": "...",
      "impact": {
        "classification": "Tailwind|Headwind|Mixed/Depends|Unclear",
        "rationale": "...",
        "confidence": 0.8
      }
    }
  ]
}
```

After 5-label rescore, `impact.classification` becomes one of: `very bad`, `bad`, `neutral`, `good`, `very good`.

### 4.3 questions.json

Nested dict of factor keys → questions. Example:

```json
{
  "macro": {
    "demand_environment": "What can you say about overall customer demand...",
    "economic_factors": "How does the filing describe the impact of inflation..."
  },
  "end_markets": {...},
  "revenue_and_pricing": {...},
  ...
}
```

Flattened to `(key, question)` tuples for the extract prompt.

---

## 5. ACCRE Context

**ACCRE** = Advanced Computing Center for Research and Education (Vanderbilt University HPC cluster).

- **Goal:** Run GPT OSS (e.g., vLLM, Ollama, or similar) on ACCRE GPU nodes so the notebook can call it instead of OpenAI.
- **Needs:**
  - GPT OSS server exposing OpenAI-compatible API (e.g., `http://<accre-node>:8000/v1` for vLLM)
  - Notebook/client configured with `base_url` and `api_key` (dummy if local)
  - Model must support **tool/function calling** or an alternative (e.g., prompt engineering for JSON output)

---

## 6. What GPT OSS Must Replace

| Current | GPT OSS Equivalent |
|---------|---------------------|
| `OpenAI(api_key=os.environ["OPENAI_API_KEY"])` | `OpenAI(base_url="http://<ACCRE>:8000/v1", api_key="dummy")` |
| `model="gpt-4o-2024-08-06"` | `model="llama-3.1-70b"` or whatever is loaded on ACCRE |
| OpenAI tool calling | Model must support tools, or fallback: parse JSON from raw completion |

**Configuration points to change:**
- Create client with `base_url` pointing to ACCRE GPT OSS endpoint
- Set `EXTRACT_MODEL`, `SYNTH_MODEL` to the loaded model name
- Optionally reduce `MAX_WORKERS_REPORTS`, `MAX_IN_FLIGHT_OPENAI` to avoid overloading local inference

---

## 7. Technical Constraints

1. **Tool/function calling:** Pipeline relies on `tools` and `tool_choice`. vLLM and some models support OpenAI-compatible tool calling. If not, need a fallback (e.g., "Return JSON in this format: {...}" and parse from `choices[0].message.content`).
2. **Concurrency:** OpenAI allows many parallel requests. Local inference may need fewer workers.
3. **Rate limits:** OpenAI had 30k TPM limit. GPT OSS on ACCRE may have different limits (GPU memory, batch size).
4. **Dependencies:** `openai`, `tiktoken`, `bs4`, `lxml`. No `htmlrag` (replaced with local `clean_html`/`build_block_tree`).

---

## 8. Current State

- **cut_mda.py:** Already run on ACCRE. `Data/mda_output/` downloaded locally (~2,828 successful extractions, 521 failed).
- **Factor extraction:** Partially run locally with OpenAI (AAL ticker, 42 filings). Hit 429 rate limits. ~4+ AAL factor JSONs exist.
- **5-label rescore:** Run on 1 file for testing.
- **Majority Vote:** Not yet run.
- **Event study:** Requires `df` from df builder; df builder needs factor JSONs + `filing_returns_1m.csv`.

---

## 9. What to Assist With

1. **Setup GPT OSS on ACCRE:** Guide for running vLLM (or equivalent) with an OpenAI-compatible API on a GPU node.
2. **Model choice:** Recommend a model that supports tool calling and fits ACCRE GPU memory.
3. **Notebook changes:** Update `DATA.ipynb` to use `base_url` + model name for GPT OSS.
4. **Fallback if no tool calling:** Provide prompt-based extraction that returns JSON without tools.
5. **Running the full pipeline:** Batch job or interactive session on ACCRE to process all tickers.

---

## 10. Key File Paths (Relative to sample_code/)

| Purpose | Path |
|---------|------|
| MD&A input | `../Data/mda_output/mda_clean/*_mda.html` |
| Factor output | `factors/mda_factors/{TICKER}/*_FACTORS_DETAILED.json` |
| Questions | `questions.json` |
| Returns | `filing_returns_1m.csv` |
| Env/API key | `.env` (OPENAI_API_KEY) |

---

## 11. Resume-Safe Behavior

- Factor extraction skips reports if `*_FACTORS_DETAILED.json` already exists.
- Skips chunks if `*.answers.json` exists.
- 5-label rescore skips factors already having valid 5-class labels.
- Safe to re-run after interruption.

---

*End of handoff document. Last updated: 2026-02-15*
