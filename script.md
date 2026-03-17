# Mid-Term Presentation Script

**Total time target:** ~25 minutes (leave ~5 min for Q&A within the 30-min slot)

| Speaker | Slides | Approx. Time |
|---------|--------|-------------|
| **Maggie** | 1-9 | ~8 min |
| **Luka** | 10-16 | ~6 min |
| **Roshan** | 17-27 | ~10 min |

---

## MAGGIE (Slides 1-9)

### Slide 1 — Title

- "Good morning/afternoon everyone. We're Roshan, Maggie, and Luka."
- "Our project — Reasoning-Augmented Factor Extraction — tackles a simple question: can we teach an LLM (Large Language Model) to read SEC (Securities and Exchange Commission) filings and produce real investment signals? We combine factor discovery, supervised fine-tuning, and reinforcement learning to find out."
- "Today we're presenting our midterm results — Tasks 1, 2, and our initial backtesting in 4.1."

> **Time: ~20 sec**

---

### Slide 2 — Agenda

- "Here's how we've structured this." [gesture to slide]
- "I'll set up the problem, walk through our end-to-end pipeline, and take you through how we discovered and scored about 68,000 financial factors from raw SEC filings. Luka will then show how we fine-tuned our model with SFT (Supervised Fine-Tuning) and built a multi-agent system to consolidate those factors into filing-level signals. Roshan closes with the backtesting — does any of this actually predict stock returns?"

> **Time: ~25 sec**

---

### Slide 3 — Problem

- "Let's start with why this matters."
- "Every public U.S. company files 10-Ks and 10-Qs with the SEC. Inside each filing is the MD&A section — Management Discussion and Analysis — where leadership tells you what happened, what went wrong, and what they expect. It's the richest source of forward-looking qualitative information in public markets."
- "The problem is volume. 86 companies. Four sub-sectors — airlines, defense, general industrials, and industrial equipment. Ten years of filings. That's roughly 2,500 filings, each 50 to 100 pages. No human analyst can read all of them, and certainly not consistently."
- "So our goal is to have a reasoning LLM do it — extract the key financial themes, classify the sentiment on a 5-class scale, and ultimately generate signals that predict whether a stock outperforms or underperforms the S&P 500 (Standard & Poor's 500)."
- "And here's the punchline up front — our best cohort outperforms the market by nearly 4% in just three weeks. Let me walk you through how we got there."

> **Time: ~55 sec**

---

### Slide 4 — Project Overview

- "The project is organized into four tasks, and they build on each other." [gesture to slide]
- "Task 1: Factor Discovery — we extract consistent financial themes from the raw HTML filings using a 14-billion parameter reasoning model. Across 86 tickers and 10 years, that produced about 68,000 scored factors."
- "Task 2: Sentiment Classification — we fine-tune that same model with QLoRA (Quantized Low-Rank Adaptation) on 5,000 annotated samples to sharpen its 5-class labeling, especially at the extremes."
- "Task 3 — post-midterm — is RL (Reinforcement Learning) Alignment. We'll use GRPO (Group Relative Policy Optimization) to directly optimize the model's sentiment outputs against actual stock returns across 1-month, 3-month, and 6-month horizons."
- "Task 4: Quantitative Backtesting — the ultimate test. Do our signals generate excess return? We measure Sharpe ratio, information ratio, and alpha versus the S&P 500."
- "For this midterm, Tasks 1, 2, and 4.1 are complete."

> **Time: ~50 sec**

---

### Slide 5 — End-to-End Pipeline Architecture

- "This is the full pipeline, left to right." [gesture across the diagram]
- "We start with raw EDGAR (Electronic Data Gathering, Analysis, and Retrieval) filings — 10-Ks and 10-Qs in HTML. Our parser extracts the MD&A sections and splits them into processable chunks. We focused on 10-Ks and 10-Qs because they contain the structured MD&A narrative — 8-Ks are event-driven disclosures without a consistent MD&A section, so they weren't a fit for factor extraction."
- "Those chunks go to DeepSeek-R1 — a 14-billion parameter reasoning model running on ACCRE's (Advanced Computing Center for Research and Education) GPU cluster via vLLM — A6000 GPUs for inference and A100 GPUs for fine-tuning. The model answers 60 targeted questions across 14 categories per filing. Questions like: is revenue growing? Are input costs under control? Any new regulatory risk?"
- "From those answers, the model produces factors — each with a 5-class sentiment label, a written rationale, and a confidence score — a number between 0 and 1 representing how certain the LLM is in its own classification."
- "We then fine-tune the model with QLoRA on 5,000 curated samples to improve that classification — that's the SFT step."
- "A 4-agent system consolidates all the factor scores into a single investment signal per filing."
- "And the final step — still ahead — is RL alignment with GRPO to directly optimize for return prediction."
- "The scale: 86 tickers, 10 years, about 68,000 factors, 5,000 SFT annotations, one 14-billion parameter model powering it all."

> **Time: ~80 sec**

---

### Slide 6 — Task 1: Factor Discovery

- "Let me go deeper on how factor discovery works."
- "First, the parsing challenge. SEC filings come in iXBRL (inline eXtensible Business Reporting Language) format — dense, heavily nested HTML with inline XBRL tags. Formats change over the decade. We built a parser that handles both modern and legacy structures, locates the MD&A and Risk Factors sections through table-of-contents anchor matching, and splits each filing into roughly 20 logical subsections. Over 95% extraction success rate across the full corpus."
- "Next, factor extraction itself. We route 60 questions across 14 categories to the relevant subsections — you can see all 14 categories on the right." [gesture to chart] "The universal ones — Demand & Revenue, Cost & Margins — apply everywhere. The sector-specific ones — Airlines, Defense — only target the relevant tickers. The LLM processes each subsection in 6,000-token batches, then synthesizes chunk-level answers into consolidated factors. Each filing yields about 25 to 30 factors."
- "Finally, sentiment scoring. Every factor receives a 5-class label — very negative through very positive — along with a rationale and a confidence score between 0 and 1. This gives us interpretability and a natural quality filter for downstream tasks."

> **Time: ~75 sec**

---

### Slide 7 — Sentiment Distribution & Sector Heatmap

- "So what did 67,741 factors actually look like?" [gesture to left panel]
- "The distribution on the left tells the first story. Most factors cluster in neutral and positive. The tails are thin — about 4% very negative, about 3% very positive. That's not surprising. Management language in MD&A skews optimistic. But those tails are exactly where the strongest investment signals live, so getting them right is critical."
- "The heatmap in the center breaks sentiment down by category and sector." [gesture to center] "Red at the top — regulatory, macro, labor — these are consistently negative across all four sectors. These are the structural risk themes. Green at the bottom — technology, capital allocation, demand — consistently positive. The driver themes. This pattern is stable and intuitive."
- "On the right, a scatter of average sentiment versus 21-day excess return per filing — that's how much the stock outperformed or underperformed the S&P 500 in the 21 trading days after the filing. There's a directional relationship, but it's noisy. This is the raw, unconsolidated signal — no weighting, no aggregation. Cleaning this up is what the rest of the pipeline does."

> **Time: ~65 sec**

---

### Slide 8 — Top Factors by Significance

- "Which individual factors carry the most predictive weight? This chart ranks the top 25 by significance — the absolute IC (Information Coefficient) multiplied by coverage." [gesture to chart]
- "Quick primer on IC: it's the Spearman rank correlation between a factor's sentiment score and the subsequent 21-day excess return. It ranges from -1 to +1 — anything above 0.05 is considered meaningful in factor research. Coverage is how many filings contain that factor. The bar captures both — you need a factor that's predictive and that appears broadly enough to trade on."
- "Color matters. Green bars: positive sentiment predicts positive return, as you'd expect. Red bars: positive sentiment actually predicts negative return — a contrarian signal."
- "The top factor — interest_rate_impact — stands out. IC of 0.10, roughly 1,200 filings, 54% hit rate — meaning the sentiment direction matched the return direction 54% of the time. It's red because when management is optimistic about rates, the stock tends to underperform. For industrials, rates are a headwind, and optimistic language signals complacency."
- "Also notable: the airlines-specific factors — capacity_load_yield and fuel_costs_hedging — rank highly despite narrower coverage. Within that sub-sector, they're very predictive."

> **Time: ~75 sec**

---

### Slide 9 — Per-Sector Analysis

- "Last slide on Task 1 — the sentiment-return relationship by sub-sector." [gesture across panels]
- "We use Spearman rank correlation here — it measures whether more positive filings tend to rank higher in returns, from -1 to +1. It captures rank order without assuming a linear relationship."
- "Airlines, far left — high dispersion, Spearman near zero. Too much noise at this stage to draw conclusions."
- "Defense is where it gets interesting. Spearman of negative 0.146 with a p-value of 0.007 — less than 1% probability this is due to chance, so statistically significant. Negative sentiment in defense filings predicts positive returns. This is the classic 'kitchen sink' effect: management front-loads bad news, the market overreacts, and the stock recovers. It's a contrarian signal, and it's real."
- "General and industrial equipment — the two largest groups — show slight positive trends, but not yet statistically significant at the individual factor level."
- "Here's the key takeaway: the raw signal has genuine predictive content, especially in certain sectors. But it's inconsistent. It needs consolidation — combining 25 to 30 factors into one signal per filing — and it needs alignment with actual returns. That's precisely what Tasks 2 and 3 deliver."
- "With that, let me hand it to Luka, who'll walk you through how we fine-tuned the model and built the multi-agent consolidation system."

> **Time: ~65 sec**

---

## LUKA (Slides 10-16)

### Slide 10 — Task 2: Annotation Dataset

- "Thanks, Maggie. So we have 68,000 raw factor scores, and as Maggie just showed, the signal is there — but it's noisy and inconsistent. My job was to fix the classifier, then consolidate everything into tradeable signals."
- "To fine-tune, we need training data. The project spec requires 5,000+ annotated data points. Here's how we built that dataset." [gesture to slide]
- "We started with all 67,741 scored factors and applied a quality gate — confidence at least 0.5, non-empty rationale. That left about 66,000 high-quality factors. From those, we sampled exactly 5,000 — 1,000 per sentiment class — balanced across sub-sectors and all 14 categories. You can see the balanced distribution on the left, sub-sector representation in the center, and category coverage on the right."
- "Now, I want to address the annotation approach directly, because it's a deliberate design choice. Our annotations are the base model's own high-confidence labels. This is self-training — a well-established technique where a model's best outputs become its training signal, similar to Noisy Student Training by Xie et al. The reasoning is straightforward: the base model scored 67,000 factors and was mostly correct, but inconsistent. It almost never predicted 'very positive' even when the evidence clearly warranted it. So we selected the 5,000 best examples — where the model was confident and articulate, with an average confidence of 0.834 — and trained it to match its own best behavior, consistently. The proof is in the results: very positive recall went from 11.5% to 80.5% after SFT."
- "We also chose to train a single universal model rather than separate sector-specific models. With 5,000 total samples, splitting four ways would leave only about 500 per sector for airlines — not enough for reliable fine-tuning. The universal model still improves across all four sectors, as we'll show."
- "We used an 80/20 stratified split — 4,000 train, 1,000 validation — preserving class and sector balance throughout."

> **Time: ~70 sec**

---

### Slide 11 — Fine-Tuning

- "For fine-tuning, we used QLoRA — 4-bit NF4 (NormalFloat 4-bit) quantization with LoRA (Low-Rank Adaptation) adapters. This lets us train a 14-billion parameter model on a single A100 40GB GPU by only updating about 1.8% of the parameters — roughly 275 million out of 15 billion total."
- "The loss curve on the left tells the story." [point to chart] "Training loss drops sharply over 3 epochs and 750 steps — you can see the clean drops at each epoch boundary. Total training time: about 82 minutes."
- "On the right, the key hyperparameters. LoRA rank 64, alpha 128, targeting all 7 projection layers — Q, K, V, O in attention, plus gate, up, and down in the MLP (Multi-Layer Perceptron). Effective batch size of 16 through gradient accumulation. Cosine learning rate at 2e-4 with 5% warmup, paged AdamW 8-bit optimizer, and gradient checkpointing to stay within GPU memory."
- "One important design detail: we used label masking during training — the loss is computed only on the assistant's response tokens, not on the prompt tokens. This ensures the model learns to produce the correct classification output rather than memorizing the input format."

> **Time: ~45 sec**

---

### Slide 12 — Confusion Matrices

- "This is the slide I want you to focus on." [pause] "SFT model on the left, base model on the right. Same architecture, same validation set."
- "Look at the bottom-right corner of the base model first." [point] "The very_positive row. Out of 200 true very_positive samples, the base model classified 177 of them as just 'positive.' Only 23 correct. It was collapsing two distinct classes into one."
- "Now the SFT model. 161 out of 200 correct. The F1 score — which is the harmonic mean of precision and recall, penalizing models that sacrifice one for the other — goes from 0.206 to 0.793 for the very_positive class. That's the single largest class-level improvement. That 11.5% to 80.5% recall jump I mentioned? This is where it lives."
- "But here's the finding that really matters." [pause] "Every single misclassification in the SFT model falls between neighboring classes. Zero distant errors. It never confuses very negative with positive. It never confuses very positive with neutral. The model has learned the ordinal structure of the sentiment scale — and that's something we didn't explicitly train for. It emerged from the fine-tuning."

> **Time: ~60 sec**

---

### Slide 13 — Evaluation Results

- "Headline numbers. Macro F1 — that's F1 averaged equally across all five sentiment classes, regardless of how many samples each class has — comes in at 0.731, up from 0.604. That's a +0.127 improvement. Accuracy: 73.3%, up 9.1 points. Both models produce valid JSON 100% of the time, so output format was never the bottleneck — classification quality was."
- "Bottom left — F1 by sub-sector. SFT improves across all four. General sees the biggest gain at +0.185, industrial equipment at +0.114, defense at +0.112, and airlines at +0.028."
- "Bottom right — F1 by category." [gesture to chart] "The standout is competitive position, jumping from 0.50 to 0.87. The high-volume categories — cost margins, demand revenue, macro external — all improved substantially."
- "Why does this matter for the investment signal? Because the extreme labels — very positive and very negative — are exactly the classes that drive the strongest return predictions. The base model was crushing those extremes into neighboring classes. The SFT model preserves them. And as Roshan will show, that distinction translates directly into excess return."

> **Time: ~55 sec**

---

### Slide 14 — Multi-Agent Signal Consolidation (Architecture + Chart)

- "So now we have 68,000 improved factor scores. The next problem: each filing has roughly 25 individual scores across 14 categories. We need one investment signal per filing. That's what the multi-agent system delivers." [gesture to architecture diagram]
- "Four agents, each with a clear role. Agent 1 loads the scored factors. Agent 2 computes a confidence-weighted average per category — collapsing 25 factors into 14 category-level scores. Agent 3 extracts the top 3 key drivers and top 3 risk flags for interpretability. And Agent 4 produces the final signal: an IC-weighted sum of category scores, mapped to one of five cohorts — cohorts are just buckets of filings grouped by their signal strength, from very negative to very positive."
- "The cohort distribution across 2,441 filings is shown below. Most filings land in neutral — 54%. The tails are thin: 50 very negative, 24 very positive. That's the expected shape — averaging across 14 categories naturally concentrates the signal near the center and reduces variance."

> **Time: ~55 sec**

---

### Slide 15 — Multi-Agent (Full Chart)

- "Here's the full distribution. 50 very negative, 446 negative, 1,314 neutral, 607 positive, 24 very positive."
- "The positive skew — more filings classified positive than negative — is consistent with the optimistic management language Maggie showed earlier. Our pipeline reflects the underlying language distribution faithfully."
- "So: we've gone from 68,000 raw factor scores to 2,441 filing-level signals, each assigned to a cohort. The question now is whether these cohort labels actually predict future stock returns."

> **Time: ~25 sec**

---

### Slide 16 — Task 4.1: Category Coverage

- "One more piece before Roshan takes over — the coverage table." [gesture to table]
- "14 categories. The universal ones — demand revenue, cost margins, capital allocation — cover 83 of our 86 tickers across 126 active months. The remaining 3 had incomplete filing data. That's essentially the full 10-year window."
- "Sector-specific categories are narrower by design — airlines transport covers 5 tickers, defense government covers 12 — matching the actual universe for those sectors."
- "This matters because it means the backtesting results you're about to see are built on dense, well-populated data, not sparse edge cases."
- "Roshan, over to you."

> **Time: ~35 sec**

---

## ROSHAN (Slides 17-27)

### Slide 17 — Per-Category Returns by Cohort (TRAIN)

- "Thanks, Luka. So — Maggie showed you how we discover factors, Luka showed you how we sharpen and consolidate them. Now the question that matters: does any of this actually predict stock returns?"
- "We use a strict time-based split — train is 2015 to 2019, validation is 2020 to 2022, test is 2023 to 2025. No lookahead, no data leakage."
- "This table shows the training period — 1,106 filings, over 27,000 factor observations. Each cell is the mean 21-day excess return versus the S&P 500 for a given category-sentiment pair." [gesture to heatmap]
- "I won't read every number — let me point you to the pattern. Look at the equal-weight average row at the bottom: very negative averages -1.04%, and it improves as you move right — positive averages +0.29%. That's a clear left-to-right gradient from bad sentiment to good returns."
- "The standout categories: cost margins shows a 1.3 percentage point spread from very negative at -0.91% to positive at +0.40%. Demand revenue hits +0.77% in the very positive cohort. These are the categories to watch as we move forward."

> **Time: ~65 sec**

---

### Slide 18 — Per-Category Returns by Cohort (VAL)

- "Validation period — 2020 to 2022, 729 filings. And here things get interesting."
- "This is the COVID window plus the recovery — a strong bull market. Every cohort shows positive returns, including very negative at +2.38%. The gradient actually inverts: negative sentiment cohorts outperformed positive ones."
- "This is not a failure — it's a regime effect. During market dislocations, companies that front-load bad news in their filings often see stronger recoveries. Maggie showed this same contrarian pattern in the defense sector earlier."
- "This is exactly the type of time-varying behavior that motivates RL alignment in Task 3 — we need a model that adapts to different market regimes rather than assuming one static relationship."

> **Time: ~50 sec**

---

### Slide 19 — Per-Category Returns by Cohort (TEST)

- "Test period — 2023 to 2025, 605 filings, fully out-of-sample."
- "Industrials broadly underperformed the S&P here, so most cells are negative. But look at the very positive column: cost margins at +0.35%, demand revenue at +0.90%. Even in a down market for the sector, the extreme positive sentiment cohorts still outperform."
- "That persistence across three very different market environments — a normal period, a crisis-and-recovery, and a sector downturn — is what gives us confidence there's a real signal here, especially in the tails. Keep that in mind — the tails are going to be the story."

> **Time: ~45 sec**

---

### Slide 20 — Factor Ranking IS vs OOS

- "Now let's formalize this. For each of the 14 categories, I constructed a simple long-short strategy — buy stocks where sentiment is positive and simultaneously short-sell stocks where sentiment is negative, so you profit from the spread between winners and losers regardless of the overall market direction. Aggregate monthly, and compute the annualized Sharpe ratio — excess return divided by volatility. Above 1.0 is very strong for a single factor." [gesture to left table]
- "In-sample, cost margins leads at 1.03 with a t-statistic of 2.29 — above the 1.96 significance threshold, so we can be 95% confident this is real signal. Supply chain operations at 1.01, competitive position at 0.97. Three categories above 0.9 in-sample is strong."
- "But in-sample Sharpe is easy. The right column is the real test — out-of-sample." [gesture to right table] "Most categories decay, which is completely normal in factor research. But cost margins holds at 0.27, and labor workforce actually stays at 0.54 versus 0.58 in-sample."
- "A positive out-of-sample Sharpe means the signal is real, not overfit. And these are simple long-short strategies with no optimization — the raw sentiment signal from our LLM is already generating tradeable alpha — excess return that can't be explained by broad market movements."

> **Time: ~70 sec**

---

### Slide 21 — Cumulative Returns

- "This chart shows it visually — cumulative long-short returns for the top 5 categories over the full decade." [gesture to chart]
- "Cost margins — the blue line — is the one to focus on. Persistent upward drift from 2015 through 2025. It doesn't spike and crash; it accumulates steadily. That's what a robust factor looks like."
- "The dashed black line is the equal-weight average across all 14 categories — it peaks around 2020 and declines. Most factors don't survive out-of-sample. Cost margins does." [gesture to period boundaries] "It keeps climbing through the validation boundary and through the test boundary."
- "Labor workforce — the cyan line — is more volatile, but trends upward in the test period. These two categories are our strongest candidates for the full portfolio construction in Task 4."

> **Time: ~55 sec**

---

### Slide 22 — Rolling t-statistics

- "One more robustness check before we get to the main event. Rolling t-statistics tell us whether these signals are stable over time or whether they just got lucky in one period." [gesture to chart]
- "The gray dashed lines at plus and minus 1.96 mark 95% significance. Cost margins crosses above 1.96 multiple times — during the training period, again during validation, and again in the test period. This is not a one-time artifact."
- "Labor workforce shows significance in training, dips during COVID — understandably — then recovers."
- "The takeaway: signal strength is time-varying and regime-dependent. Some categories predict well in certain environments but not others. This is precisely what motivates RL alignment — optimizing the model's outputs against actual returns across 1-month, 3-month, and 6-month horizons to capture these dynamics."
- "Now — with all of that context — let me show you the chart that ties it all together."

> **Time: ~60 sec**

---

### Slide 23 — Cohort vs. 21-Day Excess Return

- [pause briefly] "This is the most important chart in the presentation. Everything we've built — the factor extraction, the SFT fine-tuning, the multi-agent consolidation — all of it distills into this one question: when our system says a filing is very positive, does the stock actually outperform?"
- "The x-axis is our five sentiment cohorts. The y-axis is the mean 21-day excess return versus the S&P 500 — measured starting the day after the filing." [gesture to right side of chart]
- "Start on the right. Neutral: 0.33%. Positive: 0.36%. Very positive: plus 3.69%." [let it land] "That is 24 filings where our system had the highest conviction, and they outperformed the market by nearly 4% in three weeks. Now, to be transparent — n equals 24 means the standard error is roughly 2%, so this is directionally strong but not individually significant at the 95% level. What gives us confidence is that this tail pattern is consistent with the category-level results we saw in cost margins and demand revenue, which have much larger sample sizes."
- "The long-short spread — very positive minus very negative — is +2.78%. The IR (Information Ratio) comes in at 0.067. In a 21-day window, that spread is economically meaningful."
- "Now, the honest part." [gesture to left side] "The left side is inverted. Very negative and negative cohorts also show positive returns. The overall Spearman correlation is 0.009 — not statistically significant. The relationship is not monotonic — meaning the returns don't consistently increase from left to right across all five cohorts."
- "But I want to frame this correctly. This is the SFT-only pipeline — we have not applied RL alignment yet. The project spec's expected progression is Base to SFT to SFT plus RL, with RL specifically designed to enforce monotonicity by directly optimizing the model's sentiment outputs against return outcomes." [gesture to yellow callout] "The +3.69% tail signal tells us the pipeline is extracting real information. RL's job in Task 3 is to fix the left side — to make the full cohort-return curve monotonically increasing."

> **Time: ~90 sec**

---

### Slide 24 — Signal vs. 21-Day Excess Return

- "Here's the same data in continuous form — filing signal strength on the x-axis, 21-day excess return on the y-axis, each point colored by sub-sector."
- "The OLS (Ordinary Least Squares) regression line — the standard linear best fit — is flat. The continuous signal is not linearly predictive. And the return cloud spans roughly plus or minus 20%, which is the natural volatility of individual stock returns over 21-day windows."
- "But that is exactly the point — our pipeline's value is not in the average, it's in the tails. The very positive cohort at +3.69% is the actionable signal. Task 3's GRPO alignment will push the model to produce sharper, more extreme predictions where it has genuine information."

> **Time: ~40 sec**

---

### Slide 25 — Per-Sector Cohort vs. Return

- "Finally, breaking the cohort analysis down by sub-sector."
- "Airlines — top left — is noisy. The very positive outlier is about 13% return, but that's n equals 1, so we set it aside."
- "Defense — top right — shows the contrarian effect most clearly. At the cohort level, Spearman is -0.148 — consistent with the -0.146 we saw at the factor level. The negative cohort outperforms. This is the same contrarian dynamic Maggie described earlier, and it's statistically significant."
- "General and industrial equipment — bottom row — are the largest groups. Both show the same tail pattern as the aggregate: flat in the middle, very positive outperforming. Spearman of 0.039 and 0.018 respectively."
- "These sector-level differences are exactly why we plan to incorporate sector-specific weighting in the GRPO reward function for Task 3."

> **Time: ~50 sec**

---

### Slide 26 — Next Steps & Timeline

- "So here's where we stand and where we're going." [gesture to left column]
- "Through Week 8 we've completed the full pipeline end to end: 86 tickers parsed, 68,000 factors extracted and scored, 5,000 balanced annotations, SFT fine-tuning with F1 of 0.731, multi-agent consolidation producing 2,441 filing-level signals, and the backtesting analysis you've just seen."
- "Weeks 9 through 15 are about closing the gap." [gesture to right column] "Task 3: we design a reward model around actual stock returns and run GRPO alignment across three time horizons — 1-month, 3-month, and 6-month — to capture both short-term and longer-term signal dynamics. The bonus track is CoT (Chain-of-Thought) reasoning with ORM (Outcome-supervised Reward Model) and PRM (Process-supervised Reward Model) — ORM rewards correct final answers, PRM rewards correct intermediate reasoning steps."
- "Task 4 scales up to full portfolio construction — long-short strategies by cohort, transaction cost modeling, and benchmarking against the S&P 500 with Sharpe ratio, information ratio, and alpha as the success metrics."
- "The bottom line: the project spec expects monotonic improvement from Base to SFT to SFT plus RL. We've shown that SFT already produces a +3.69% tail signal. RL alignment is specifically designed to fix the left side of the cohort curve and deliver that full monotonic relationship."

> **Time: ~65 sec**

---

### Slide 27 — Thank You

- "Let me close with six numbers that summarize where we are."
- "86 tickers, 10 years of filings, roughly 68,000 factors extracted and sentiment-scored."
- "SFT macro F1 of 0.731 — the critical gain being very positive recall going from 11.5% to 80.5%. The model can now actually identify the extreme positive signals that drive returns."
- "2,441 filing-level signals. The very positive cohort earns +3.69% excess return in 21 days."
- "Cost margins is our strongest individual factor — in-sample Sharpe of 1.03 that holds at 0.27 out-of-sample."
- "And the path forward is clear: GRPO alignment will enforce the monotonic cohort-return relationship across multiple time horizons, and full portfolio construction will translate these signals into measurable Sharpe, IR, and alpha."
- "We're building on a pipeline that already finds real signal in the tails. RL's job is to make the whole curve work. Thank you — happy to take questions."

> **Time: ~50 sec**

---

## Total Time Estimate

| Speaker | Slides | Time |
|---------|--------|------|
| Maggie | 1-9 | ~8 min |
| Luka | 10-16 | ~6 min |
| Roshan | 17-27 | ~10 min |
| **Total** | **27 slides** | **~23.5 min** |
| Q&A | | ~6.5 min |

This leaves comfortable room within the 30-minute slot without dragging.

---

## Formulas

Reference sheet for every metric, formula, and term used in the presentation and PPT slides. Organized by pipeline stage.

---

### Returns (Slides 17-25)

**21-Day Stock Return (simple/arithmetic)**
```
ret_21d = (P_t+21 / P_t) - 1
```
Where `P_t` = adjusted close price on filing date (or next trading day), `P_t+21` = adjusted close price 21 trading days later.

**21-Day SPY (Benchmark) Return**
```
ret_21d_spy = (SPY_t+21 / SPY_t) - 1
```
Same window, same formula, applied to SPY (S&P 500 ETF).

**21-Day Excess Return**
```
ret_21d_excess = ret_21d - ret_21d_spy
```
Positive = stock outperformed the market. Negative = stock underperformed. This is the ground truth for the entire project.

---

### Information Coefficient — IC (Slides 8, 14, 20)

**Spearman IC (per factor)**
```
IC = Spearman_ρ(sentiment_score, ret_21d_excess)
```
Computed across all filings where a given factor appears. Measures rank-order correlation between sentiment and subsequent excess return. Range: [-1, +1]. Values above |0.05| are considered meaningful in factor research.

**Factor Significance Score (Slide 8 chart)**
```
significance = |IC| × coverage
```
Where `coverage` = number of filings containing that factor. Captures both predictive power and breadth.

**Hit Rate (Slide 8)**
```
hit_rate = (# filings where sentiment direction matched return direction) / (# total filings with factor)
```
A 54% hit rate means the sentiment correctly predicted the direction of excess return 54% of the time.

---

### Spearman Rank Correlation — ρ (Slides 9, 23, 25)

```
ρ = 1 - (6 × Σ d_i²) / (n × (n² - 1))
```
Where `d_i` = difference between the rank of sentiment score and rank of excess return for filing `i`, and `n` = number of filings. Range: [-1, +1]. Does not assume linearity — measures monotonic relationship only.

**p-value** (Slides 9, 23, 25)
```
p-value = P(|ρ_observed| ≥ |ρ| | H₀: no correlation)
```
Probability of observing a correlation at least this strong under the null hypothesis of no relationship. p < 0.05 = statistically significant at 95% confidence.

---

### Multi-Agent Signal Consolidation (Slides 14-15)

**Label-to-Score Mapping (Agent 1)**
```
very_negative → -2
negative      → -1
neutral       →  0
positive      → +1
very_positive → +2
```

**Confidence-Weighted Category Average (Agent 2)**
```
cat_score_c = Σ(score_i × confidence_i) / Σ(confidence_i)
```
For all factors `i` in category `c` within a single filing. If total confidence = 0, falls back to unweighted mean.

**IC-Weighted Filing Signal (Agent 4)**
```
raw_signal = Σ(cat_score_c × weight_c) / Σ(weight_c)
```
Where `weight_c = mean(|IC|)` for all factors in category `c` for the filing's sub-sector, computed from training-period IC data.

**Signal Normalization**
```
signal = clip(raw_signal, -2, +2) / 2.0    →    signal ∈ [-1, +1]
```

**Cohort Thresholds**
```
very_negative:  signal < -0.6
negative:      -0.6 ≤ signal < -0.2
neutral:       -0.2 ≤ signal < +0.2
positive:      +0.2 ≤ signal < +0.6
very_positive:  signal ≥ +0.6
```

---

### Classification Metrics (Slides 12-13)

**Precision (per class)**
```
Precision = TP / (TP + FP)
```
Of all predictions for this class, how many were correct?

**Recall (per class)**
```
Recall = TP / (TP + FN)
```
Of all actual instances of this class, how many did the model find?

**F1 Score (per class)**
```
F1 = 2 × (Precision × Recall) / (Precision + Recall)
```
Harmonic mean of precision and recall. Penalizes models that sacrifice one for the other. Range: [0, 1].

**Macro F1 (Slide 13 headline)**
```
Macro_F1 = (1/K) × Σ F1_k
```
Where `K` = number of classes (5). Averages F1 equally across all classes regardless of class size. This means the rare classes (very_negative, very_positive) count equally to the common classes (neutral, positive).

**Accuracy**
```
Accuracy = (# correct predictions) / (# total predictions)
```

---

### Sharpe Ratio (Slide 20)

**Monthly Long-Short Return (per category)**
```
r_month = mean(ret_21d_excess for positive sentiment filings)
        - mean(ret_21d_excess for negative sentiment filings)
```
Computed for each calendar month across all filings in that month.

**Annualized Sharpe Ratio**
```
Sharpe = (mean(r_monthly) / std(r_monthly)) × √12
```
Risk-adjusted return. Annualized by multiplying by √12 (12 months per year). Benchmarks: >0.5 = good for a single factor, >1.0 = very strong.

**t-statistic (Slide 20)**
```
t = mean(r_monthly) / (std(r_monthly) / √T)
```
Where `T` = number of months. Tests whether the Sharpe is statistically different from zero. t > 1.96 → 95% confidence the signal is real (not noise).

**Rolling t-statistic (Slide 22)**
```
t_rolling = mean(r_monthly over window) / (std(r_monthly over window) / √W)
```
Where `W` = window size (12 or 24 months). Computed at each month by looking back `W` months. Shows whether the signal is stable or time-varying.

---

### Information Ratio — IR (Slide 23)

```
IR = mean(ret_21d_excess across all filings) / std(ret_21d_excess across all filings)
```
Measures excess return per unit of tracking error relative to the benchmark (SPY). Similar to Sharpe but computed against a benchmark rather than the risk-free rate.

**Long-Short Spread (Slide 23)**
```
LS_spread = mean(ret_21d_excess | cohort = very_positive) - mean(ret_21d_excess | cohort = very_negative)
```
In our results: +3.69% - 0.91% = +2.78%.

**Standard Error of Cohort Mean (Slide 23)**
```
SE = std(ret_21d_excess within cohort) / √n
```
For the very_positive cohort with n=24: SE ≈ 2%, meaning the 3.69% mean has a 95% confidence interval of roughly [−0.3%, 7.7%].

---

### QLoRA Fine-Tuning (Slide 11)

**LoRA Weight Decomposition**
```
W' = W + ΔW = W + B × A
```
Where `W` = frozen pre-trained weight matrix (d × d), `B` = trainable (d × r), `A` = trainable (r × d), `r` = rank (64 in our case). Only `B` and `A` are updated during training. Total trainable parameters ≈ 2 × d × r per target module.

**LoRA Scaling**
```
ΔW_scaled = (α / r) × B × A
```
Where `α` = 128, `r` = 64 → scaling factor = 2.0. Controls how much the LoRA adapters influence the output relative to the frozen weights.

**NF4 Quantization**
```
W_quantized = quantize_nf4(W)    →    4 bits per parameter (vs 16 bits for bf16)
```
Reduces memory from ~28 GB (14B params × 2 bytes) to ~7 GB (14B params × 0.5 bytes), enabling training on a single 40GB A100.

**Cross-Entropy Training Loss (Slide 11 curve)**
```
L = -(1/N) × Σ log P(y_true | x)
```
Where the sum is over assistant response tokens only (label masking). Prompt tokens are masked with label = -100 and excluded from loss computation.

**Effective Batch Size**
```
effective_batch = per_device_batch × gradient_accumulation_steps × num_gpus
               = 4 × 4 × 1 = 16
```
(Per PPT slide values)

---

### OLS Regression (Slide 24)

**Ordinary Least Squares**
```
ret_21d_excess = β₀ + β₁ × signal + ε
```
Fits a straight line through the scatter of (signal, return) pairs. In our results, β₁ ≈ 0 (flat line), meaning the continuous signal is not linearly predictive — the value is in the discrete cohort tails, not the linear fit.

---

### Terms Referenced in Next Steps (Slide 26)

**GRPO (Group Relative Policy Optimization)**
```
L_GRPO = -E[Σ (min(r_θ × A, clip(r_θ, 1-ε, 1+ε) × A)) - β × KL(π_θ || π_ref)]
```
Where `r_θ = π_θ(y|x) / π_old(y|x)` is the probability ratio, `A` is the advantage (computed from reward within a group of sampled outputs), `ε` is the clipping range, and `β` weights the KL divergence penalty against the reference policy. GRPO samples multiple completions per prompt, ranks them by reward, and uses relative ranking as the advantage signal — no separate critic model needed.

**Reward Function (Task 3 design)**
```
reward(sentiment, ret_21d_excess) = alignment_score
```
The exact reward design is post-midterm work. The goal: reward the model when its predicted sentiment cohort aligns with the actual filing-period excess return, penalize misalignment. Monotonicity is enforced by shaping the reward so that very_positive predictions on high-return filings score highest.

**ORM (Outcome-supervised Reward Model)**
```
R_ORM(y) = score based on final answer correctness only
```
Evaluates the complete output — did the model get the right sentiment label?

**PRM (Process-supervised Reward Model)**
```
R_PRM(y) = Σ score_per_reasoning_step
```
Evaluates each intermediate reasoning step — did the model identify the right evidence, apply the right logic, and reach the right conclusion through valid reasoning?

---

### Glossary of Abbreviations

| Abbreviation | Full Form | First Used |
|---|---|---|
| LLM | Large Language Model | Slide 1 |
| SEC | Securities and Exchange Commission | Slide 1 |
| SFT | Supervised Fine-Tuning | Slide 2 |
| S&P 500 | Standard & Poor's 500 | Slide 3 |
| QLoRA | Quantized Low-Rank Adaptation | Slide 4 |
| RL | Reinforcement Learning | Slide 4 |
| GRPO | Group Relative Policy Optimization | Slide 4 |
| EDGAR | Electronic Data Gathering, Analysis, and Retrieval | Slide 5 |
| ACCRE | Advanced Computing Center for Research and Education | Slide 5 |
| iXBRL | inline eXtensible Business Reporting Language | Slide 6 |
| IC | Information Coefficient | Slide 8 |
| RLHF | Reinforcement Learning from Human Feedback | Slide 10 |
| NF4 | NormalFloat 4-bit | Slide 11 |
| LoRA | Low-Rank Adaptation | Slide 11 |
| MLP | Multi-Layer Perceptron | Slide 11 |
| IR | Information Ratio | Slide 23 |
| OLS | Ordinary Least Squares | Slide 24 |
| CoT | Chain-of-Thought | Slide 26 |
| ORM | Outcome-supervised Reward Model | Slide 26 |
| PRM | Process-supervised Reward Model | Slide 26 |
| IS | In-Sample (training period) | Slide 20 |
| OOS | Out-of-Sample (validation + test period) | Slide 20 |
| MD&A | Management Discussion and Analysis | Slide 3 |
| SPY | SPDR S&P 500 ETF Trust (benchmark) | Slide 17 |
