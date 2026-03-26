**Data folder (Google Drive):** https://drive.google.com/drive/folders/1bnqSx1pfY6kl5SoKOxBPCCSPH640F-b7?usp=sharing

Google Doc: https://docs.google.com/document/d/1pO_aZJfCujaOTlTdMzWrOZdifnR9t8Cg4uFwxbXjDaQ/edit?tab=t.0

---

# Reasoning-Augmented Factor Extraction from SEC Filings

**Course:** NLP Asset Management (Spring 2026, AllianceBernstein partnership)

Extract thematic factors from 10-K/10-Q filings across 86 industrial/defense/airline tickers, score sentiment via LLM, fine-tune for improved classification, and consolidate into filing-level investment signals validated against 21-day excess returns.

---

## Mid-Term Progress Summary

Everything below covers **Tasks 1, 2, and 4.1** — the full mid-term scope. Tasks 3 (RL alignment) and 4.2-4.3 (portfolio construction, backtesting) are post-midterm.

| Task | Description | Status |
|------|-------------|--------|
| **Task 1** | Thematic Factor Discovery in SEC Filings | Done |
| **Task 2** | Specialized Sentiment Classification | Done |
| **Task 4.1** | Factor and Sentiment Analysis | Done |
| Task 3 | Reinforcement Learning Alignment | Post-midterm |
| Task 4.2-4.3 | Portfolio Construction & Backtesting | Post-midterm |

---

## Project Structure

```
fillings/
  AB-VU_RLSentiment_2026Spring.pdf       # Project spec from AllianceBernstein
  Data/                                   # Raw SEC filing HTMLs (per ticker)
  sample_code/                            # Professor reference only (DO NOT USE)

  roshan/Actual_code/
    task_1/                               # Task 1: Factor discovery pipeline
      task_1_1_Data_processing.ipynb
      task_1_2_Factor_extraction.ipynb
      task_1_3_Sentiment_scoring.ipynb
      task_1_5_Reasoning_model.ipynb
      config.py                           # LLM provider, model, concurrency settings
      questions.json                      # 60 questions across 14 categories
      ticker_mapping.json                 # 86 tickers -> 4 sub-sectors
      requirements.txt
      utils/
        html_parser.py                    # SEC HTML parser (iXBRL + legacy)
        llm_client.py                     # OpenAI-compatible client with retries
        question_router.py                # Maps subsections to question categories
      output/
        extracted_sections/               # Step 1: MD&A + Risk Factors HTML
        subsections/                      # Step 1: Parsed subsection JSONs
        factors/                          # Step 2: Extracted factors (sentiment: null)
        factors_scored/                   # Step 3: Sentiment-scored factors
        filing_returns.csv                # Step 4: 21-day excess returns (2,542 filings)
        reasoning_output.json             # Step 4: Per-sector LLM reasoning

    task_2/                               # Task 2: Fine-tuning + multi-agent
      task_2_1_annotation_dataset.ipynb
      task_2_2_fine_tuning.ipynb
      task_2_3_evaluation.ipynb
      task_2_4_multi_agent.ipynb
      task2.md                            # Detailed plan with results
      requirements.txt
      data/
        sft_dataset.jsonl                 # 5,000-sample SFT dataset
        sft_train.jsonl                   # 4,000 training samples (80%)
        sft_val.jsonl                     # 1,000 validation samples (20%)
        dataset_stats.json                # Distribution statistics
      models/
        sentiment_lora/                   # QLoRA adapter weights
      output/
        eval_report.json                  # SFT vs base model evaluation
        filing_signals.jsonl              # Filing-level investment signals (2,441 filings)
```

---

## Task 1: Thematic Factor Discovery in SEC Filings

**Spec requirement:** Extract and quantify consistent financial factors/themes from 10 years of EDGAR filings using LLMs. Apply reasoning models to identify patterns with measurable impact on stock movements.

**Model used:** `deepseek-ai/DeepSeek-R1-Distill-Qwen-14B` via vLLM on ACCRE (DGX A100 40GB)

### Task 1.1 — Data Processing

**What was asked:** Pre-process each SEC filing HTML file.

**What we did:**
- Parsed raw iXBRL HTML filings (both 2021+ and legacy formats) for 86 tickers across 10-K and 10-Q forms
- Extracted MD&A (Item 7 in 10-K, Item 2 in 10-Q) and Risk Factors (Item 1A) sections via TOC anchor matching
- Split extracted sections into logical subsections by bold headings (MD&A) or risk item blocks (Risk Factors)
- All steps are resume-safe (skip filings with existing output)

**Files:**
| File | Description |
|------|-------------|
| `task_1/task_1_1_Data_processing.ipynb` | Main notebook |
| `task_1/utils/html_parser.py` | BeautifulSoup-based parser handling iXBRL + legacy anchor formats |
| `task_1/output/extracted_sections/{TICKER}/` | Extracted HTML fragments per filing |
| `task_1/output/subsections/{TICKER}/` | Parsed subsection JSONs with text + token estimates |

**Stats:** 2,542 filings processed across 86 tickers, covering 2015-2025.

---

### Task 1.2 — Factor and Theme Extraction

**What was asked:** Use pre-trained LLMs to extract factors/themes. Develop targeted questions to extract consistent factors over time. Quantify each factor's significance.

**What we did:**
- Developed a taxonomy of 60 targeted questions across 14 categories (11 universal + 3 sub-sector-specific: airlines_transport, defense_government, industrial_infrastructure)
- Built a question router that maps subsection titles to relevant question categories via keyword matching
- Used chunked Q&A approach: route questions to subsections, extract answers per chunk, then synthesize into consolidated per-filing factor JSONs
- Each factor has: `key`, `category`, `summary`, `evidence[]` (with section/subsection provenance)

**Files:**
| File | Description |
|------|-------------|
| `task_1/task_1_2_Factor_extraction.ipynb` | Main notebook |
| `task_1/questions.json` | 60 questions across 14 categories |
| `task_1/utils/question_router.py` | Maps subsections to question categories |
| `task_1/output/factors/{TICKER}/*.json` | Per-filing factor JSONs (sentiment: null at this stage) |

**Stats:** 67,741 factors extracted across 2,542 filings. 430 unique factor keys, 15 categories.

**Factor JSON schema:**
```json
{
  "ticker": "AAL", "form": "10-K", "filing_date": "2015-02-25",
  "model": "deepseek-ai/DeepSeek-R1-Distill-Qwen-14B",
  "num_factors": 34,
  "factors": [{
    "key": "revenue_mix", "category": "demand_revenue",
    "summary": "Revenue mix shifted towards higher-margin segments...",
    "evidence": [{"text": "...", "section": "mda", "subsection": "..."}],
    "sentiment": null
  }]
}
```

---

### Task 1.3 — Sentiment Scoring

**What was asked:** (Implied by factor pipeline — factors need sentiment labels for downstream analysis.)

**What we did:**
- Scored all 67,741 factors with 5-class sentiment: `very_negative`, `negative`, `neutral`, `positive`, `very_positive`
- Each score includes a rationale and confidence (0.0-1.0)
- Used the same DeepSeek-R1 model with JSON-forced output and Pydantic validation
- Batched processing with resume-safe checkpointing

**Files:**
| File | Description |
|------|-------------|
| `task_1/task_1_3_Sentiment_scoring.ipynb` | Main notebook |
| `task_1/output/factors_scored/{TICKER}/*.json` | Scored factor JSONs (sentiment populated) |

**Stats:**
| Label | Count | % |
|-------|-------|---|
| very_negative | 2,772 | 4.1% |
| negative | 16,636 | 24.6% |
| neutral | 22,203 | 32.8% |
| positive | 24,009 | 35.4% |
| very_positive | 2,121 | 3.1% |

After scoring, each factor's `sentiment` field contains:
```json
{
  "label": "positive",
  "rationale": "The company's cost management initiatives...",
  "confidence": 0.85
}
```

---

### Task 1.4 — Reasoning Model

**What was asked:** Apply reasoning LLMs to identify complex patterns within extracted factors. Highlight key factors/themes with measurable impact on historical stock movements.

**What we did:**
- Generated 21-day post-filing excess returns (stock return minus SPY return) for all filings using yfinance
- Computed per-factor Spearman IC (information coefficient) and hit rates to quantify which factors predict returns
- Ran LLM reasoning per sector to identify key trends, sentiment-return links, and sector-specific factors
- Produced cross-sector synthesis identifying the most predictive factors

**Files:**
| File | Description |
|------|-------------|
| `task_1/task_1_5_Reasoning_model.ipynb` | Main notebook |
| `task_1/output/filing_returns.csv` | 2,542 filings with 21-day returns |
| `task_1/output/reasoning_output.json` | Per-sector reasoning + cross-sector synthesis |

**filing_returns.csv columns:** `ticker, form, filing_date, ret_21d, ret_21d_spy, ret_21d_excess, status`

**Key IC findings (from reasoning_output.json):**
| Sector | Factor | IC | Hit Rate |
|--------|--------|----|----------|
| industrial_equipment | risk_factors | -0.262 | 0.60 |
| general | risk_factors | -0.262 | 0.60 |
| airlines | interest_rate_impact | 0.100 | 0.54 |
| defense | trade_tariffs | 0.059 | 0.53 |

---

## Task 2: Specialized Sentiment Classification

**Spec requirement:** Fine-tune LLMs for high-precision sentiment scoring. Create a labeled dataset of at least 5,000 annotated data points. Fine-tune by sector and theme. Build a multi-agent system to consolidate factor signals into investment signals.

**Base model:** `deepseek-ai/DeepSeek-R1-Distill-Qwen-14B`

### Task 2.1 — Annotation Dataset Creation

**What was asked:** Create a labeled dataset containing at least 5,000 annotated data points. Include sentiment labels for factors/themes.

**What we did:**
- Pulled from all 67,741 scored factors on ACCRE (83 tickers)
- Quality filtered: confidence >= 0.5 and non-empty rationale (66,444 passed)
- Stratified sampling: ~1,000 per sentiment class, proportional sub-sector representation, all 14+ categories, spread across 2015-2025
- Formatted as chat JSONL (system/user/assistant messages) compatible with `trl` SFTTrainer
- 80/20 stratified train/val split

**Files:**
| File | Description |
|------|-------------|
| `task_2/task_2_1_annotation_dataset.ipynb` | Main notebook |
| `task_2/data/sft_dataset.jsonl` | Full 5,000-sample dataset (7.2 MB) |
| `task_2/data/sft_train.jsonl` | 4,000 training samples (5.8 MB) |
| `task_2/data/sft_val.jsonl` | 1,000 validation samples (1.4 MB) |
| `task_2/data/dataset_stats.json` | Distribution statistics |

**Dataset balance:**
- Labels: 1,000 per class (perfectly balanced)
- Sub-sectors: industrial_equipment (2,087), general (1,669), defense (755), airlines (489)
- Categories: all 15 represented, demand_revenue (992) to esg_sustainability (17)
- Years: 2015-2025
- Average confidence: 0.834

**Label source:** Base DeepSeek-R1 labels are our annotations. SFT refines the same model's behavior (self-distillation/refinement). Returns are NOT in the labels — sentiment is about the factor itself, not return prediction. Returns come in Task 3 (RL alignment).

---

### Task 2.2 — Model Fine-Tuning

**What was asked:** Fine-tune pre-trained LLM(s) by sector and theme on the annotated dataset. Ensure accurate sentiment classification tailored to financial contexts.

**What we did:**
- QLoRA fine-tuning (4-bit quantization + LoRA adapters) of DeepSeek-R1-Distill-Qwen-14B
- Single model with sub-sector and category in the prompt (the model learns sector-specific patterns from context, rather than training 4 separate models on too-small splits)
- Trained on DGX A100 40GB on ACCRE

**Hyperparameters:**
| Parameter | Value |
|-----------|-------|
| LoRA rank | 64 |
| LoRA alpha | 128 |
| Target modules | q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj |
| Epochs | 3 |
| Batch size | 4 (gradient accumulation 4 = effective 16) |
| Learning rate | 2e-4 (cosine scheduler) |
| Warmup | 5% |
| Max sequence length | 2048 |
| Precision | bf16 |

**Files:**
| File | Description |
|------|-------------|
| `task_2/task_2_2_fine_tuning.ipynb` | Main notebook |
| `task_2/models/sentiment_lora/` | LoRA adapter weights |

---

### Task 2.3 — Evaluation (SFT vs Base)

**What was asked:** (Implied — need to measure improvement from fine-tuning.)

**What we did:**
- Ran both the SFT model (with LoRA) and the base model (LoRA disabled) on the same 1,000-sample validation set
- Computed per-class precision, recall, F1, confusion matrices, sub-sector and category breakdowns
- Full error analysis

**Files:**
| File | Description |
|------|-------------|
| `task_2/task_2_3_evaluation.ipynb` | Main notebook |
| `task_2/output/eval_report.json` | Complete evaluation metrics |

**Headline results:**

| Metric | SFT | Base | Delta |
|--------|-----|------|-------|
| Accuracy | 0.733 | 0.642 | **+0.091** |
| Macro F1 | 0.731 | 0.604 | **+0.127** |
| JSON compliance | 100% | 100% | +0.0% |

**Per-class F1:**

| Class | SFT | Base | Delta |
|-------|-----|------|-------|
| very_negative | 0.746 | 0.761 | -0.015 |
| negative | 0.583 | 0.613 | -0.030 |
| neutral | 0.814 | 0.793 | +0.022 |
| positive | 0.718 | 0.645 | +0.072 |
| very_positive | 0.793 | 0.206 | **+0.587** |

**Key findings:**
1. **SFT fixed the base model's very_positive collapse**: Base barely predicted very_positive (11.5% recall, F1=0.206). SFT restored it to F1=0.793 — the single biggest improvement.
2. **SFT slightly worse on the negative end**: Both very_negative (-0.015) and negative (-0.030) F1 decreased slightly. RL alignment (Task 3) should address this.
3. **All 267 errors are adjacent (distance=1)**: Zero catastrophic misclassifications. The model only confuses neighboring classes (e.g., negative vs very_negative).
4. **Sub-sector improvements**: general (+0.185), industrial_equipment (+0.114), defense (+0.112), airlines (+0.028).

---

### Task 2.4 — Multi-Agent System

**What was asked:** Explore a multi-agent framework and design an effective orchestration framework. Consolidate different factor signals from LLM agents.

**What we did:**
Built a 4-agent rule-based pipeline that rolls up 67,741 individual factor sentiments into one investment signal per filing, then validates against actual 21-day excess returns.

**Agent architecture:**
```
Agent 1: Factor Sentiment      Load scored factors, map labels to numeric scores (-2 to +2)
         │
         ▼
Agent 2: Category Aggregator   Confidence-weighted avg per (filing, category) → 15 category scores
         │
         ▼
Agent 3: Sub-Sector Context    Top-3 key drivers + top-3 risk flags per filing
         │
         ▼
Agent 4: Signal Consolidator   IC-weighted sum → continuous signal [-1,1] → 5-cohort assignment
```

**Design decisions:**
- **Agent 1 uses existing base model scores** instead of re-scoring ~67K factors with SFT (~130 hrs at 0.15 it/s). SFT improvement proven in task_2_3 — in production, the SFT model replaces the base scorer.
- **Agent 3 is rule-based** (not LLM) — identifies key drivers/risks programmatically. Faster and reproducible.
- **IC weighting** from `reasoning_output.json`: per-sector per-factor Spearman ICs aggregated to category level.
- **Cohort thresholds:** very_negative < -0.6, negative < -0.2, neutral < 0.2, positive < 0.6, very_positive >= 0.6

**Files:**
| File | Description |
|------|-------------|
| `task_2/task_2_4_multi_agent.ipynb` | Main notebook (no GPU required) |
| `task_2/output/filing_signals.jsonl` | One JSON per filing (2,441 lines, 1.2 MB) |

**filing_signals.jsonl schema:**
```json
{
  "ticker": "AAL", "form": "10-K", "filing_date": "2015-02-25",
  "sub_sector": "airlines",
  "signal": 0.1234, "cohort": "neutral",
  "category_scores": {"demand_revenue": 0.48, "cost_margins": 0.56, ...},
  "key_drivers": ["capital_allocation", "demand_revenue", "cost_margins"],
  "risk_flags": ["macro_external", "regulatory_legal"],
  "ret_21d_excess": 0.056690
}
```

**Results:**

| Cohort | Count | % | Mean 21d Excess Return |
|--------|-------|---|----------------------|
| very_negative | 50 | 2.0% | +0.91% |
| negative | 446 | 18.3% | +0.79% |
| neutral | 1,314 | 53.8% | +0.33% |
| positive | 607 | 24.9% | +0.36% |
| very_positive | 24 | 1.0% | **+3.69%** |

| Metric | Value |
|--------|-------|
| Spearman(signal, return) | 0.013 (p=0.53) |
| Long-short return (VP - VN) | **+2.78%** |
| Information ratio | 0.067 |

**Interpretation:** The right half is monotonic (neutral < positive < very_positive at 3.69%). The left half is inverted — very_negative and negative outperform neutral, which is a known contrarian/"kitchen sink" effect. This is the **Base model baseline**. SFT improves classification (task_2_3), and RL alignment (Task 3) is designed to fix the full monotonicity.

---

## Task 4.1: Factor and Sentiment Analysis

**What was asked:** Conduct in-depth analysis on selected factors/themes across a representative sample of companies.

**What we did:**
- Covered by `task_1_5_Reasoning_model.ipynb`: per-sector IC analysis, factor significance, hit rates across all 83 tickers, LLM-generated reasoning narratives
- Covered by `task_2_4_multi_agent.ipynb`: cohort-vs-return validation, per-sector breakdown, signal-return correlation analysis

**Key findings:**
- Top drivers across filings: capital_allocation, demand_revenue, cost_margins
- Top risk flags: macro_external, regulatory_legal, supply_chain_operations
- Defense sector shows significant negative Spearman (-0.148, p=0.007) — contrarian signal
- General and industrial_equipment sectors drive the aggregate positive-tail result

---

## Tickers

86 tickers across 4 sub-sectors (defined in `task_1/ticker_mapping.json`):

| Sub-sector | Count | Tickers |
|------------|-------|---------|
| Airlines | 5 | AAL, ALK, DAL, LUV, UAL |
| Defense | 13 | BA, COL, GD, HII, LDOS, LHX, LLL, LMT, NOC, RTN, RTX, TDG, TXT |
| Industrial Equipment | 34 | AOS, AYI, BLDR, CARR, CAT, CMI, DE, DOV, EMR, ETN, FBIN, FLS, FTV, GE, GNRC, HON, HUBB, IR, ITW, JCI, LII, MAS, MMM, NDSN, OTIS, PCAR, PH, PNR, PWR, ROK, SNA, SWK, TT, XYL |
| General | 34 | ADT, ALLE, AME, AMTM, AXON, CHRW, CPRT, CSX, CTAS, EFX, EXPD, FAST, FDX, FLR, GWW, INFO, J, JBHT, KSU, NLSN, NSC, ODFL, R, RHI, ROL, ROP, RSG, UNP, UPS, URI, VNT, VRSK, WAB, WM |

---

## How to Run

### Prerequisites
- ACCRE account with GPU access (account `p_dsi_acc`, partition `batch_gpu`)
- Python 3.10+

### Task 1 dependencies
```bash
pip install -r roshan/Actual_code/task_1/requirements.txt
# beautifulsoup4, lxml, openai, pydantic, tqdm, numpy, pandas, matplotlib, seaborn, scipy, yfinance
```

### Task 2 dependencies
```bash
pip install -r roshan/Actual_code/task_2/requirements.txt
# torch, transformers, peft, trl, bitsandbytes, datasets, accelerate, numpy, pandas, matplotlib, seaborn, scikit-learn
```

### Running on ACCRE
- **Task 1 notebooks (1.1-1.3):** Require vLLM server running with DeepSeek-R1-Distill-Qwen-14B on GPU
- **Task 1.5 (Reasoning):** Partial GPU (LLM reasoning calls only)
- **Task 2.1 (Dataset):** No GPU
- **Task 2.2 (Fine-tuning):** GPU required (A100 40GB)
- **Task 2.3 (Evaluation):** GPU required (A100 40GB)
- **Task 2.4 (Multi-agent):** No GPU — purely computational

All notebooks are self-contained and resume-safe. Run them in Jupyter on ACCRE from the `task_1/` or `task_2/` directory.

---

## Post-Midterm: Opus-Labeled SFT Re-scoring Pipeline

After the midterm, we improved the annotation quality by using Claude Opus 4.6 (a stronger model) to re-label the 5,000 SFT training samples — replacing self-training with proper knowledge distillation. The Opus-labeled SFT model is then used to re-score all ~68K factors.

### Setup Instructions (for teammates)

**1. Download the merged SFT model from Google Drive:**

- **Link:** https://drive.google.com/drive/folders/1iOLwncMtuq1Atsdg3g94gmcP6Qyjh6Pd?usp=sharing
- Download ALL files from the folder (6 safetensors shards + config files, ~28GB total)
- Place them at: `roshan/Actual_code/task_2/models/sentiment_merged_opus/`
- Verify you have these files:
  - `model-00001-of-00006.safetensors` through `model-00006-of-00006.safetensors`
  - `config.json`
  - `model.safetensors.index.json`
  - `generation_config.json`
  - `tokenizer.json`, `tokenizer_config.json`, `chat_template.jinja`

**2. Start vLLM serving the merged model:**

```bash
cd roshan/Actual_code/task_2
bash start_vllm.sh
```

Wait until you see `Application startup complete` in the terminal output.

**3. Set your ticker assignment in `task_2_5_sft_rescoring.ipynb`:**

Open the notebook, find the "Discover Factor Files" cell. The ticker assignments are already in the code — just uncomment YOUR line:

- **Person 1 (Roshan):** Uncomment the `# MY_TICKERS = {"AAL", ...}` line (A-FDX, 29 tickers)
- **Person 2 (Luka):** Uncomment the `# MY_TICKERS = {"FLR", ...}` line (FLR-PH, 33 tickers)
- **Person 3 (Maggie):** Uncomment the `# MY_TICKERS = {"PNR", ...}` line (PNR-XYL, 24 tickers)

**4. Run `task_2_5_sft_rescoring.ipynb`:**

- Skip Phase A (merge cell) — the merged model already exists
- Run Phase B cells — builds prompts and scores all factors via vLLM concurrently
- Output goes to `output/factors_scored_sft/{TICKER}/`

**5. After all 3 people finish:**

- Collect all `output/factors_scored_sft/` folders into one directory
- Run these notebooks locally (no GPU needed):
  - `task_2_6_sft_multi_agent.ipynb` — consolidates SFT scores into filing signals
  - `task_2_7_sft_backtesting.ipynb` — backtesting + Base vs SFT comparison
  - `task_4_1_ticker_analysis.ipynb` — per-ticker signal analysis

### Key Files

| File | Description |
|------|-------------|
| `task_2/start_vllm.sh` | One-command vLLM startup script |
| `task_2/merge_lora.py` | Merges LoRA into base model (already done) |
| `task_2/merge_lora_sharded.py` | Same but saves in 5GB shards (avoids OOM) |
| `task_2/task_2_5_sft_rescoring.ipynb` | Re-score all factors via vLLM |
| `task_2/task_2_6_sft_multi_agent.ipynb` | Multi-agent consolidation on SFT scores |
| `task_2/task_2_7_sft_backtesting.ipynb` | Full backtesting + Base vs SFT comparison |
| `task_2/task_4_1_ticker_analysis.ipynb` | Per-ticker signal analysis |
| `task_2/data/sft_train_opus.jsonl` | Opus-labeled training data (4,172 samples) |
| `task_2/data/sft_val_opus.jsonl` | Opus-labeled validation data (1,045 samples) |
| `task_2/models/sentiment_lora_opus/` | Opus-trained LoRA adapter (on ACCRE) |
| `task_2/models/sentiment_merged_opus/` | Merged model (Google Drive) |

### Important Notes

- The `VLLM_MODEL_NAME` in `task_2_5` must match what vLLM reports at startup: `/workspace/models/sentiment_merged_opus/`
- The notebook is resume-safe — if interrupted, re-run and it skips already-scored filings
- All 3 people can write to the same `output/factors_scored_sft/` directory since each ticker gets its own subfolder (no conflicts)
- If pyarrow import fails in Jupyter, add this as the first line in the notebook: `import sys; sys.path.insert(0, "/cvmfs/soft.computecanada.ca/easybuild/software/2023/x86-64-v3/Compiler/gcccore/arrow/23.0.1/lib/python3.12/site-packages")`

---

## Post-Midterm Roadmap

| Task | Description | Dependencies |
|------|-------------|--------------|
| **3.1** | Reward model design — GRPO to align sentiment with stock returns | Task 2 output |
| **3.2** | Chain-of-thought reasoning (bonus) — ORM/PRM for CoT | Task 3.1 |
| **4.2** | Portfolio construction — sentiment cohort performance | Task 2.4 signals |
| **4.3** | Backtesting — multi-horizon (1m, 3m, 6m), cross-sector analysis | Task 4.2 |
