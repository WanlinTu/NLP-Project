# Task 2: Specialized Sentiment Classification — Plan

## Objective (from project spec)
Fine-tune an LLM to provide high-precision sentiment scoring tailored to the nuances of individual financial factors. Consolidate factor sentiments into investment signals.

## What We Have
- **~100K+ scored factors** across all 86 tickers (all teammates' data combined on ACCRE)
- All tickers are **industrial sector**, split into 4 **sub-sectors**: airlines (5), defense (13), industrial_equipment (34), general (35)
- Each scored factor has: `key`, `category`, `summary`, `evidence[]`, `sentiment: {label, rationale, confidence}`
- Sentiment labels: `very_negative`, `negative`, `neutral`, `positive`, `very_positive`
- 14 question categories (11 universal + 3 sub-sector-specific), 60 factor keys
- `filing_returns.csv` + `reasoning_output.json` already generated from full dataset on ACCRE
- Scored factors live on ACCRE at `output/factors_scored/{TICKER}/`
- Base model: `deepseek-ai/DeepSeek-R1-Distill-Qwen-14B` via vLLM on DGX A100 40GB

---

## Subtask 2.1: Annotation Dataset Creation (~5,000 data points)

### 2.1.1 Source Data
- Pull from `output/factors_scored/` on ACCRE (all 86 tickers, all teammates' data already combined)
- Each data point = one factor with its sentiment label from the base DeepSeek-R1 model

### 2.1.2 Selection Strategy (Balance Across)
Need 5,000 well-balanced data points. Balance across:
- **Sentiment classes**: ~1,000 per class (very_negative, negative, neutral, positive, very_positive)
  - If a class is underrepresented, oversample from it; if over, subsample
- **Sub-sectors**: proportional to sub-sector size (airlines ~6%, defense ~15%, industrial ~39%, general ~40%)
- **Categories**: ensure all 14 categories are represented
- **Time diversity**: spread across filing years (2015–2025)
- **Quality filter**: only include factors where `confidence >= 0.5` and `rationale` is non-empty

### 2.1.3 SFT Data Format
Each data point = a chat-format prompt/completion pair for supervised fine-tuning.

**Input (user message):**
```
Given the following factor extracted from a {form} filing for {ticker} ({sub_sector} sub-sector), classify the sentiment.

Category: {category}
Factor: {key}
Summary: {summary}
Evidence: {evidence_text}

Classify the sentiment as one of: very_negative, negative, neutral, positive, very_positive.
Provide a brief rationale and confidence score (0.0–1.0).
Respond with JSON only.
```

**Output (assistant message):**
```json
{
  "label": "positive",
  "rationale": "The company's cost management initiatives...",
  "confidence": 0.85
}
```

### 2.1.4 Output Files
- `task_2/data/sft_dataset.jsonl` — full 5K dataset in chat-format JSONL
- `task_2/data/sft_train.jsonl` — 80% training split (~4,000)
- `task_2/data/sft_val.jsonl` — 20% validation split (~1,000)
- `task_2/data/dataset_stats.json` — distribution stats for reporting

### 2.1.5 Key Decisions
- **Label source**: The base DeepSeek-R1 (14B) labels ARE our annotations. SFT refines the same model's behavior — teaching it to be more consistent and precise at this specific task. This is a standard self-distillation / refinement approach.
- **Include evidence in prompt**: Yes — gives the model grounding to verify the summary.
- **Include returns in labels**: No — sentiment is about the factor itself, not return prediction. Returns come in Task 3 (RL alignment).

---

## Subtask 2.2: Model Fine-Tuning

### 2.2.1 Base Model
- **`deepseek-ai/DeepSeek-R1-Distill-Qwen-14B`** — the same model we used for extraction and scoring
- Fine-tune with **QLoRA** (4-bit quantized LoRA) — fits on A100 40GB with 14B parameters
- Why same model? It generated the labels, so SFT sharpens its own sentiment classification without switching architectures

### 2.2.2 Fine-Tuning Method
- **QLoRA**: 4-bit quantization + LoRA adapters
  - LoRA rank: 64, alpha: 128
  - Target modules: `q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj`
- **Libraries**: `transformers`, `peft`, `trl` (SFTTrainer), `bitsandbytes`
- **Training params**:
  - Epochs: 3
  - Batch size: 4 (with gradient accumulation = 4 → effective batch 16)
  - Learning rate: 2e-4 with cosine scheduler
  - Max sequence length: 2048
  - Warmup ratio: 0.05

### 2.2.3 "By Sector and Theme"
The spec says "fine-tune by sector and theme." Approach:
- **Single model with sub-sector/category in the prompt** — the prompt includes `{sub_sector}` and `{category}`, so the model learns sub-sector-specific patterns
- Why not 4 separate models? With 5K data points, splitting into 4 sub-sectors gives only ~1,250 each — too few for reliable fine-tuning. One model with contextual info is better.

### 2.2.4 Evaluation
- **Metrics**: Precision, Recall, F1 (macro + per-class) on the 1,000-sample validation set
- **Confusion matrix**: identify which label pairs are most confused
- **Sub-sector breakdown**: F1 per sub-sector
- **Before vs after SFT**: run base DeepSeek-R1 (no SFT) on the same val set to measure improvement

### 2.2.5 Output
- LoRA adapter weights: `task_2/models/sentiment_lora/`
- Evaluation report: `task_2/output/eval_report.json`
- Merged model (for inference): `task_2/models/sentiment_merged/` (optional)

---

## Subtask 2.3: Multi-Agent System

The spec requires: "Explore a multi-agent framework and design an effective orchestration framework if needed. Consolidate different factor signals from LLM agents."

### 2.3.1 Agent Design
Each agent handles a different aspect of the filing analysis, producing its own signal:

- **Agent 1: Factor Sentiment Agent** — The fine-tuned SFT model (from 2.2). Scores individual factors with 5-class sentiment. Produces per-factor labels.
- **Agent 2: Category Aggregator Agent** — Groups factors by their 14 categories, computes category-level sentiment (weighted by confidence). Produces per-category signals.
- **Agent 3: Sub-Sector Context Agent** — LLM call that takes the category signals + sub-sector context (e.g., airline-specific factors like fleet_strategy, capacity_load_yield) and produces a sub-sector-aware filing-level assessment. Uses the SFT model with a different prompt template.
- **Agent 4: Signal Consolidator** — Combines outputs from all agents into a single filing-level investment signal. No LLM needed — rule-based weighted aggregation.

### 2.3.2 Orchestration Framework
```
Raw Filing HTML
    │
    ▼
[Task 1 Pipeline: Extract → Score]
    │
    ▼
Agent 1: Factor Sentiment Agent (SFT model)
    │  per-factor: {key, label, confidence}
    ▼
Agent 2: Category Aggregator
    │  per-category: {category, avg_score, n_factors, top_factor}
    ▼
Agent 3: Sub-Sector Context Agent (SFT model, different prompt)
    │  filing-level: {sub_sector_assessment, key_drivers[], risk_flags[]}
    ▼
Agent 4: Signal Consolidator (rule-based)
    │  filing-level: {ticker, filing_date, signal: float, cohort: str}
    ▼
Investment Signal
```

### 2.3.3 Signal Consolidation Logic
Agent 4 combines the upstream signals:
- **Weighted category scores**: weight each category by its IC from task_1_5 significance analysis
- **Confidence weighting**: higher-confidence factors get more weight
- **Sub-sector adjustment**: Agent 3's assessment can boost/dampen the signal (e.g., fleet_strategy is critical for airlines but irrelevant for defense)
- **Output per filing**:
  ```json
  {
    "ticker": "AAL",
    "filing_date": "2024-02-21",
    "signal": 0.65,
    "cohort": "positive",
    "category_scores": {"demand_revenue": 0.8, "cost_margins": -0.3, ...},
    "key_drivers": ["cost_actions", "volume_trends"],
    "risk_flags": ["fuel_cost_hedging"]
  }
  ```
- **Cohort assignment**: Map continuous signal → 5 cohorts (very_negative < -0.6, negative < -0.2, neutral < 0.2, positive < 0.6, very_positive ≥ 0.6)

### 2.3.4 Implementation
- Notebook: `task_2_3_multi_agent.ipynb`
- Runs the full pipeline on all scored filings
- Outputs: `task_2/output/filing_signals.jsonl` (one line per filing)
- Visualization: cohort distribution, signal vs actual 21d excess return

---

## Notebook Blueprints

### `task_2_1_annotation_dataset.ipynb` (No GPU)
**Purpose**: Build balanced 5K SFT dataset from scored factors.

| Cell | What |
|------|------|
| 1 | Imports, paths, config. Load `ticker_mapping.json` for sub-sector lookup. |
| 2 | Walk all `output/factors_scored/{TICKER}/` — load every scored factor into a flat DataFrame with columns: `ticker, sub_sector, form, filing_date, key, category, summary, evidence_text, label, rationale, confidence`. |
| 3 | **Quality filter**: drop rows where `confidence < 0.5` or `rationale` is empty/null. Print before/after counts. |
| 4 | **Label distribution analysis**: show counts per label, per sub-sector, per category, per year. Identify imbalances. |
| 5 | **Stratified sampling**: select 5,000 data points balanced across (a) ~1,000 per sentiment class, (b) proportional sub-sector representation, (c) all 14 categories represented, (d) spread across years. Use `sklearn.model_selection.train_test_split` with stratify. |
| 6 | **Format as chat JSONL**: convert each row into `{"messages": [{"role": "system", ...}, {"role": "user", ...}, {"role": "assistant", ...}]}` format compatible with `trl` SFTTrainer. |
| 7 | **Train/val split**: 80/20 stratified split → `sft_train.jsonl` (4,000) + `sft_val.jsonl` (1,000). |
| 8 | **Save & stats**: write `sft_dataset.jsonl`, `sft_train.jsonl`, `sft_val.jsonl`, `dataset_stats.json`. Print final distribution summaries. |
| 9 | **Visualizations**: label distribution bar chart, sub-sector × label heatmap, category coverage plot. |

**Inputs**: `output/factors_scored/{TICKER}/*_factors.json`, `ticker_mapping.json`
**Outputs**: `task_2/data/sft_dataset.jsonl`, `sft_train.jsonl`, `sft_val.jsonl`, `dataset_stats.json`

---

### `task_2_2_fine_tuning.ipynb` (GPU — A100 40GB)
**Purpose**: QLoRA fine-tune DeepSeek-R1-Distill-Qwen-14B on the 4K training set.

| Cell | What |
|------|------|
| 1 | Imports: `transformers`, `peft`, `trl`, `bitsandbytes`, `torch`. Config: model name, LoRA params, training hyperparams. |
| 2 | **Load base model** in 4-bit quantization (`BitsAndBytesConfig` with `load_in_4bit=True`, `bnb_4bit_compute_dtype=bfloat16`). Load tokenizer. |
| 3 | **Prepare LoRA config**: `LoraConfig(r=64, lora_alpha=128, target_modules=[...], task_type="CAUSAL_LM")`. Apply `get_peft_model()`. Print trainable param count. |
| 4 | **Load training data**: read `sft_train.jsonl`, convert to `Dataset`. Apply chat template tokenization. |
| 5 | **Training args**: `TrainingArguments(output_dir, num_train_epochs=3, per_device_train_batch_size=4, gradient_accumulation_steps=4, learning_rate=2e-4, lr_scheduler_type="cosine", warmup_ratio=0.05, bf16=True, logging_steps=10, save_strategy="epoch")`. |
| 6 | **SFTTrainer**: initialize with model, tokenizer, train dataset, training args. Run `trainer.train()`. |
| 7 | **Save LoRA adapter**: `model.save_pretrained("task_2/models/sentiment_lora/")`. Save tokenizer. |
| 8 | **Training curves**: plot loss vs step from trainer logs. |
| 9 | **(Optional) Merge & save**: merge LoRA into base model for standalone inference → `task_2/models/sentiment_merged/`. |

**Inputs**: `task_2/data/sft_train.jsonl`, HuggingFace model `deepseek-ai/DeepSeek-R1-Distill-Qwen-14B`
**Outputs**: `task_2/models/sentiment_lora/` (adapter weights), training logs

---

### `task_2_3_evaluation.ipynb` (GPU — A100 40GB)
**Purpose**: Evaluate SFT model vs base model on the 1K validation set.

| Cell | What |
|------|------|
| 1 | Imports, load LoRA adapter onto base model (4-bit). Load tokenizer. Load `sft_val.jsonl`. |
| 2 | **SFT model inference**: run each val sample through the fine-tuned model, parse JSON output, extract predicted label. Handle parse failures gracefully. |
| 3 | **Base model inference**: run the SAME val samples through the base model (no LoRA) for comparison. Same parsing logic. |
| 4 | **Metrics — SFT model**: compute per-class Precision, Recall, F1. Macro F1. Accuracy. Print classification report. |
| 5 | **Metrics — Base model**: same metrics for base model. |
| 6 | **Comparison table**: side-by-side SFT vs Base — F1 per class, macro F1, accuracy. Highlight improvements. |
| 7 | **Confusion matrices**: plot 2 confusion matrices (SFT vs Base) side by side. Identify which label pairs are most confused. |
| 8 | **Sub-sector breakdown**: F1 per sub-sector for both models. Does SFT help more for some sub-sectors? |
| 9 | **Category breakdown**: F1 per category. Are some categories harder? |
| 10 | **Error analysis**: sample 20 misclassifications from SFT model, print the factor summary + predicted vs true label. Look for patterns. |
| 11 | **Save report**: `task_2/output/eval_report.json` with all metrics + per-class breakdown. |

**Inputs**: `task_2/data/sft_val.jsonl`, `task_2/models/sentiment_lora/`, base model
**Outputs**: `task_2/output/eval_report.json`, confusion matrix plots

---

### `task_2_4_multi_agent.ipynb` (GPU — A100 40GB)
**Purpose**: Multi-agent pipeline that consolidates factor sentiments into filing-level investment signals.

| Cell | What |
|------|------|
| 1 | Imports, config, load SFT model (LoRA adapter), load `ticker_mapping.json`, load `filing_returns.csv` for later validation. |
| 2 | **Load all scored factors** into DataFrame (same as task_1_5 Cell 4). |
| 3 | **Agent 1 — Factor Sentiment Agent**: Re-score all factors using the SFT model (batched inference). Compare SFT labels vs original base model labels — report how many changed. |
| 4 | **Agent 2 — Category Aggregator**: group factors by `(ticker, filing_date, category)`, compute weighted avg sentiment per category (weight = confidence). Output: per-filing category score vector. |
| 5 | **Agent 3 — Sub-Sector Context Agent**: for each filing, build a prompt with category scores + sub-sector context, call SFT model to produce a filing-level assessment with `key_drivers` and `risk_flags`. |
| 6 | **Agent 4 — Signal Consolidator**: combine category scores (weighted by IC from task_1_5 significance) + Agent 3 adjustment → continuous signal → cohort assignment (very_negative/negative/neutral/positive/very_positive). |
| 7 | **Output**: save `task_2/output/filing_signals.jsonl` — one JSON per filing with `{ticker, filing_date, signal, cohort, category_scores, key_drivers, risk_flags}`. |
| 8 | **Visualization 1**: cohort distribution bar chart (how many filings in each cohort). |
| 9 | **Visualization 2**: cohort vs actual 21d excess return — grouped bar chart showing mean return per cohort. This is the key validation: do positive-sentiment cohorts have higher returns? |
| 10 | **Visualization 3**: signal (continuous) vs excess return scatter plot with regression line and Spearman correlation. |
| 11 | **Summary stats**: print cohort counts, mean return per cohort, Spearman(signal, return), information ratio. |

**Inputs**: `output/factors_scored/`, `task_2/models/sentiment_lora/`, `filing_returns.csv`, `ticker_mapping.json`
**Outputs**: `task_2/output/filing_signals.jsonl`, visualizations

---

## Implementation Order

| Step | What | Notebook / Script | GPU? | Status |
|------|------|-------------------|------|--------|
| 1 | Build annotation dataset | `task_2_1_annotation_dataset.ipynb` | No | Done |
| 2 | Fine-tune with QLoRA | `task_2_2_fine_tuning.ipynb` | Yes (A100) | Done |
| 3 | Evaluate SFT model | `task_2_3_evaluation.ipynb` | Yes (A100) | Done |
| 4 | Multi-agent + signal consolidation | `task_2_4_multi_agent.ipynb` | Yes (A100) | Not started |

---

## Open Questions
1. ~~**SFT data format**: Should we use the `trl` chat template format or raw JSONL?~~ → Resolved: raw JSONL with custom `ChatSFTDataset` + HF `Trainer`.
2. ~~**Evaluation baseline**: Do we re-run the base model on val set, or just compare against the labels themselves?~~ → Resolved: re-ran base model (LoRA disabled) on same val set for fair comparison.

---

## Status
- [x] 2.1.1 Source data — 67,741 scored factors from 83 tickers, 2,542 filings
- [x] 2.1.2 Selection & balancing — 5,000 samples, 1,000 per label, all 15 categories, all years 2015–2025
- [x] 2.1.3 SFT data formatting — chat JSONL with system/user/assistant messages
- [x] 2.1.4 Train/val split — 4,000 train / 1,000 val (stratified)
- [x] 2.2 Fine-tuning — complete (QLoRA, 3 epochs, LoRA adapter saved to models/sentiment_lora/)
- [x] 2.3 Evaluation — complete (results in output/eval_report.json)
- [ ] 2.4 Multi-agent + signal consolidation — not started

---

## Task 2.3 Evaluation Results (2026-03-11)

### Headline Metrics
| Metric | SFT | Base | Delta |
|--------|-----|------|-------|
| Accuracy | 0.733 | 0.642 | **+0.091** |
| Macro F1 | 0.731 | 0.604 | **+0.127** |
| JSON compliance | 100% | 100% | +0.0% |

### Per-Class F1
| Class | SFT F1 | Base F1 | Delta |
|-------|--------|---------|-------|
| very_negative | 0.746 | 0.761 | -0.015 |
| negative | 0.583 | 0.613 | -0.030 |
| neutral | 0.814 | 0.793 | +0.022 |
| positive | 0.718 | 0.645 | +0.072 |
| very_positive | 0.793 | 0.206 | **+0.587** |

### Key Findings
1. **SFT fixed the base model's very_positive collapse**: Base barely predicted very_positive (11.5% recall, F1=0.206). SFT restored it to 0.793 F1 — the single biggest improvement.
2. **SFT slightly worse on the negative end**: Both very_negative (-0.015) and negative (-0.030) F1 decreased. RL alignment (Task 3) should address this.
3. **All 267 errors are adjacent (distance=1)**: Zero catastrophic misclassifications. The model only confuses neighboring classes.
4. **Confidence is not calibrated**: Mean confidence on incorrect predictions (0.860) is slightly higher than on correct ones (0.844). Cannot use confidence as a reliability filter.
5. **Sub-sector improvements**: general (+0.185), industrial_equipment (+0.114), defense (+0.112), airlines (+0.028).
6. **Weak categories**: labor_workforce (-0.126), technology_innovation (-0.118) — small sample sizes, likely noise. All large categories improved.
