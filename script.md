# Mid-Term Presentation Script

**Total time target:** ~25 minutes (leave ~5 min for Q&A within the 30-min slot)

| Speaker | Slides | Approx. Time |
|---------|--------|-------------|
| **Maggie** | 1-9 | ~8 min |
| **Luka** | 10-16 | ~7 min |
| **Roshan** | 17-26 | ~10 min |

---

## MAGGIE (Slides 1-9)

### Slide 1 — Title

- "Good morning/afternoon everyone. We're Team [name] — Roshan, Maggie, and Luka."
- "Our project is Reasoning-Augmented Factor Extraction — using LLMs and reinforcement learning to turn SEC filings into investment signals."
- "This is our mid-term presentation covering Tasks 1, 2, and 4.1."

> **Time: ~20 sec**

---

### Slide 2 — Agenda

- "Here's our roadmap for today."
- "We'll start with the problem and project overview, walk through how we discover and score financial factors from SEC filings, then show how we fine-tuned a 14-billion parameter model to improve sentiment classification, how we consolidated those scores into filing-level signals using a multi-agent system, and finally validate everything with backtesting against actual stock returns."
- "Maggie will cover the first three sections, Luka takes over for sentiment classification and multi-agent, and Roshan closes with the backtesting results."

> **Time: ~30 sec**

---

### Slide 3 — Problem

- "So why are we doing this?"
- "Every public company in the US files quarterly and annual reports with the SEC — 10-Qs and 10-Ks. These filings contain a section called MD&A — Management Discussion and Analysis — where the company's leadership discusses what went well, what didn't, and what they expect going forward."
- "The problem is scale. We're looking at 86 companies across the industrial, defense, and airlines sectors, over 10 years. That's roughly 2,500 filings, each one 50 to 100 pages long. No human analyst can read all of this consistently."
- "Our goal: have an LLM read every filing, extract the key financial themes, score the sentiment, and ultimately predict whether the stock outperforms or underperforms the market."

> **Time: ~50 sec**

---

### Slide 4 — Project Overview

- "The full project has four tasks."
- "Task 1 is Factor Discovery — extracting consistent financial themes from the raw HTML filings using LLMs. We processed 86 tickers over 10 years and extracted about 68,000 individual factors."
- "Task 2 is Sentiment Classification — fine-tuning the LLM to be more precise at scoring those factors on a 5-class scale from very negative to very positive."
- "Task 3, which is post-midterm, is RL Alignment — using GRPO to align the model's sentiment outputs with actual stock returns over different time horizons."
- "Task 4 is Quantitative Backtesting — validating whether our signals actually predict excess returns relative to the S&P 500."
- "For this midterm, we've completed Tasks 1, 2, and 4.1."

> **Time: ~50 sec**

---

### Slide 5 — End-to-End Pipeline Architecture

- "Here's our full pipeline from left to right."
- "We start with raw EDGAR filings — 10-Ks and 10-Qs in HTML format."
- "Step two: we use DeepSeek-R1, a 14-billion parameter model running on ACCRE via vLLM, to extract factors. The model answers 60 targeted questions across 14 categories for each filing — things like 'is revenue growing?', 'are costs under control?', 'any regulatory risk?'"
- "Step three: the same model scores each factor with a 5-class sentiment label plus a confidence score and rationale."
- "Step four: we fine-tune the model with QLoRA on 5,000 annotated samples to improve classification accuracy."
- "Step five: a 4-agent system consolidates individual factor scores into one investment signal per filing."
- "Step six — still ahead — is RL alignment with GRPO to optimize the signal for return prediction."
- "The key numbers at the bottom: 86 tickers, 10 years of history, about 68,000 factors scored, 5,000 SFT annotations, and a 14-billion parameter model."

> **Time: ~90 sec**

---

### Slide 6 — Task 1: Factor Discovery

- "Let me walk through the factor discovery pipeline in more detail."
- "Step 1.1 is HTML parsing. SEC filings are in iXBRL format — heavily nested HTML with inline XBRL tags. We built a parser that handles both modern and legacy formats, extracts the MD&A and Risk Factors sections via table-of-contents anchor matching, and splits them into about 20 logical subsections per filing. We achieved over 95% extraction success rate."
- "Step 1.2 is factor extraction. We route our 60 questions across 14 categories to the relevant subsections. The LLM processes each subsection in 6,000-token batches, then synthesizes the chunk-level answers into consolidated factors. Each filing produces about 25 to 30 factors."
- "On the right you can see all 14 question categories — from Demand & Revenue and Cost & Margins at the top, which are universal, down to sector-specific categories like Airlines-Specific and Defense-Specific at the bottom."
- "Step 1.3 is sentiment scoring. Each factor gets a 5-class label — very negative through very positive — plus a rationale explaining why, and a confidence score from 0 to 1."

> **Time: ~75 sec**

---

### Slide 7 — Sentiment Distribution & Sector Heatmap

- "Here's what we found across all 67,741 factors."
- "On the left — the sentiment distribution. Most factors land in neutral or positive. Very negative and very positive are rare — about 4% and 3% respectively. This makes sense: management tends to put a positive spin in MD&A."
- "In the center — the category-by-sector heatmap. The red cells at the top — regulatory, macro, labor — are consistently negative across all four sectors. These are our risk signals. The green cells at the bottom — technology, capital allocation, demand — are consistently positive. These are our driver signals."
- "On the right — a quick scatter of average sentiment score versus 21-day excess return per filing. There's a slight positive relationship but it's noisy. This is the raw signal before any consolidation or weighting."

> **Time: ~60 sec**

---

### Slide 8 — Top Factors by Significance

- "This chart ranks the top 25 individual factors by significance — defined as the absolute information coefficient times coverage."
- "The IC, or information coefficient, measures how well a factor's sentiment predicts the 21-day excess return. Coverage is how many filings contain that factor. So the bar length captures both predictive power and breadth."
- "Green bars mean positive sentiment expects positive return. Red bars mean the opposite — positive sentiment on that factor actually predicts negative returns."
- "The top signal is interest_rate_impact with an IC of 0.10 — it appears in about 1,200 filings and has a 54% hit rate. It's red because when companies are positive about interest rates, the stock tends to underperform — rates are a headwind for industrials."
- "The airlines-specific factors — capacity_load_yield and fuel_costs_hedging — rank high because they're very predictive within that sub-sector, even though they appear in fewer filings."
- "On the right we have a quick guide on how to read the chart."

> **Time: ~75 sec**

---

### Slide 9 — Per-Sector Analysis

- "Finally for Task 1, here's the sentiment-return relationship broken down by our four sub-sectors."
- "Airlines on the far left — very dispersed, high variance. The Spearman correlation is essentially zero."
- "Defense is the interesting one — it has a statistically significant negative Spearman of -0.146, p-value 0.007. This means negative sentiment in defense filings actually predicts positive returns. It's the contrarian or 'kitchen sink' effect — defense companies dump bad news, then the stock recovers."
- "General and industrial equipment — the two largest groups — show slight positive trends but not yet statistically significant."
- "The takeaway: the raw factor-level signal has promise, especially in specific sectors, but it needs consolidation and alignment to become consistently predictive. That's exactly what Tasks 2 and 3 are designed to do."
- "With that, I'll hand it over to Luka for Task 2."

> **Time: ~60 sec**

---

## LUKA (Slides 10-16)

### Slide 10 — Task 2: Annotation Dataset

- "Thanks, Maggie. I'll walk through how we fine-tuned the model and then built the multi-agent system."
- "First, we needed training data. We started with all 67,741 scored factors and applied a quality filter — only keeping factors where the model's confidence was at least 0.5 and the rationale was non-empty. That gave us about 66,000 high-quality factors."
- "From those, we sampled exactly 5,000 data points — 1,000 per sentiment class — balanced across sub-sectors and all 14 categories."
- "On the left you can see the perfectly balanced label distribution. In the center, the sub-sector by label heatmap shows proportional representation. On the right, category coverage — demand_revenue has the most samples, but even the smallest categories like ESG are represented."
- "Three key design decisions at the bottom: First, the base model's own labels ARE our annotations — this is self-distillation, a standard technique where SFT sharpens the model's existing behavior. Second, we balanced exactly 1,000 per class. Third, we applied an 80/20 stratified split — 4,000 train, 1,000 validation."

> **Time: ~60 sec**

---

### Slide 11 — Fine-Tuning

- "We fine-tuned with QLoRA — 4-bit quantization plus LoRA adapters. This lets us train a 14-billion parameter model on a single A100 GPU by only updating about 1.3% of the parameters."
- "The loss curve on the left shows training loss dropping from 0.65 to 0.10 over 3 epochs, with sharp drops at each epoch boundary. The model converged cleanly."
- "Key config on the right: LoRA rank 64, alpha 128, targeting all attention and MLP projection layers. Effective batch size of 16 through gradient accumulation. Cosine learning rate schedule starting at 2e-4."

> **Time: ~45 sec**

---

### Slide 12 — Confusion Matrices

- "Here's where it gets interesting. On the left is our fine-tuned SFT model, on the right is the base model — same architecture, same val set, no LoRA."
- "The biggest win is in the bottom-right corner. Look at the very_positive row in the base model — it predicted 177 out of 200 as just 'positive' and only got 23 right. It essentially couldn't distinguish very positive from positive."
- "After fine-tuning, the SFT model gets 161 out of 200 very_positive correct. That's an F1 improvement from 0.206 to 0.793 — the single largest gain."
- "And critically — every single error in the SFT model is between neighboring classes. Zero distant errors. The model never confuses very negative with positive, for example. It understands the ordinal scale."

> **Time: ~60 sec**

---

### Slide 13 — Evaluation Results

- "The headline numbers: SFT achieves macro F1 of 0.731, up from 0.604 for the base model — a +0.127 improvement. Accuracy is 73.3%, up 9.1 points. And both models produce valid JSON 100% of the time."
- "On the bottom left — F1 by sub-sector. The SFT model improves across all four sectors. General sees the biggest gain at +0.185, followed by industrial equipment at +0.114."
- "On the bottom right — F1 by category. The blue bars are SFT, red is base. Competitive position had the biggest improvement, going from 0.50 to 0.87. The large categories — cost margins, demand revenue, macro external — all improved substantially."
- "The key takeaway: the SFT model is significantly better at classifying sentiment, especially at the extremes. This matters because the extreme labels — very positive and very negative — are the ones that generate the strongest investment signals."

> **Time: ~60 sec**

---

### Slide 14 — Multi-Agent Signal Consolidation (Architecture + Chart)

- "Now we need to consolidate those 68,000 individual factor scores into one investment signal per filing. That's what our 4-agent system does."
- "Agent 1 loads all the scored factors. Agent 2 computes a confidence-weighted average score per category for each filing — reducing roughly 25 factors per filing into 14 category-level scores. Agent 3 identifies the top 3 key drivers and top 3 risk flags per filing. And Agent 4 produces the final signal as an IC-weighted sum of category scores, then assigns each filing to one of five cohorts."
- "Below is the cohort distribution across all 2,441 filings. Most filings land in neutral — 54%. The tails are thin: 50 very negative, 24 very positive. This is expected when you average many categories — the central limit theorem pushes signals toward the middle."

> **Time: ~60 sec**

---

### Slide 15 — Multi-Agent (Full Chart)

- "Here's the cohort distribution in full size so you can see the counts clearly. 50 very negative, 446 negative, 1,314 neutral, 607 positive, and 24 very positive."
- "The positive skew — more filings in positive than negative — is consistent with what Maggie showed earlier about management's tendency toward optimistic language in MD&A."
- "The key question is: do these cohort assignments actually predict stock returns? That's what the backtesting section answers."

> **Time: ~30 sec**

---

### Slide 16 — Task 4.1: Category Coverage

- "Before we dive into returns, here's the coverage table showing how robust our factor data is."
- "We have 14 categories. The top ones — demand revenue, cost margins, capital allocation — span all 83 tickers and 126 active months. That's essentially complete coverage across the full 10-year window."
- "The sector-specific categories naturally have narrower coverage — airlines transport only covers 5 tickers, defense government covers 12 — but that's by design."
- "This table confirms that our backtesting results are built on a broad, well-populated dataset, not sparse outliers."
- "And with that, I'll hand it over to Roshan for the backtesting results."

> **Time: ~40 sec**

---

## ROSHAN (Slides 17-26)

### Slide 17 — Per-Category Returns by Cohort (TRAIN)

- "Thanks, Luka. Now the central question: does sentiment actually predict stock returns?"
- "We split our data into three periods: Train is 2015 to 2019, Validation is 2020 to 2022, and Test is 2023 to 2025. This is a strict time-based split — no data leakage."
- "This slide shows the training period — 1,106 filings. On the left is the mean 21-day excess return for each category crossed with each sentiment cohort. On the right is the observation count."
- "Focus on a few rows. Cost margins: very negative returns -0.91%, while positive returns +0.40%. That's a roughly 1.3 percentage point spread from negative to positive sentiment. Demand revenue shows a similar pattern — very positive at +0.77%."
- "The equal-weight average at the bottom shows the overall trend: very negative averages -1.04%, positive averages +0.29%. There's a clear left-to-right improvement from negative to positive sentiment."
- "The count table on the right shows we have substantial sample sizes — over 27,000 total factor observations in the training period."

> **Time: ~75 sec**

---

### Slide 18 — Per-Category Returns by Cohort (VAL)

- "Validation period — 2020 to 2022, 729 filings."
- "This period covers COVID and the subsequent recovery, which was a strong bull market. You can see that all cohorts show positive returns — even very negative factors averaged +2.38%."
- "The interesting thing is that the equal-weight spread from very negative to positive still holds directionally — 2.38% down to 0.61% — but it's inverted compared to what we'd expect. The negative sentiment cohorts actually had higher returns."
- "This is the contrarian effect we saw in the defense sector earlier — during market dislocations, companies that dump bad news often see stronger recoveries. This is exactly the kind of regime-dependence that RL alignment in Task 3 is designed to handle."

> **Time: ~50 sec**

---

### Slide 19 — Per-Category Returns by Cohort (TEST)

- "Test period — 2023 to 2025, 605 filings. This is fully out-of-sample."
- "Most returns are negative across the board — the industrial sector underperformed the S&P during this period."
- "But look at cost margins — very positive is the only cohort with a positive return at +0.35%. And demand revenue — very positive at +0.90%. The extreme positive sentiment cohorts still outperform even in a down market."
- "The dash marks indicate cells with zero observations — for example, airlines_transport had no very_negative factors in the test period."

> **Time: ~45 sec**

---

### Slide 20 — Factor Ranking IS vs OOS

- "Now the Sharpe ratio analysis. This is where we test which categories are actually tradeable signals."
- "On the left — in-sample, the training period. We compute a long-short return for each category: go long when sentiment is positive, short when negative. Then we aggregate monthly and compute the annualized Sharpe ratio."
- "Cost margins leads with a Sharpe of 1.03 and a t-statistic of 2.29 — statistically significant. Supply chain operations at 1.01, competitive position at 0.97. The top three all have IS Sharpe above 0.9, which is very strong."
- "On the right — out-of-sample. This is the real test. Most categories decay, which is normal in factor research. But two categories hold: cost margins maintains a positive Sharpe of 0.27, and labor workforce actually improves from 0.58 to 0.54."
- "The fact that cost margins and labor workforce hold out-of-sample suggests these are real signals, not overfitting. The Sharpe decay from 1.03 to 0.27 is expected — in-sample always looks better — but remaining positive is what matters."

> **Time: ~75 sec**

---

### Slide 21 — Cumulative Returns

- "Here's the cumulative return chart for the top 5 categories over the full 10-year period."
- "The blue line — cost margins — shows persistent upward drift from 2015 through 2025. It doesn't peak and crash; it accumulates steadily across all three periods. That's the hallmark of a robust signal."
- "The cyan line — labor workforce — is more volatile but also trends upward, especially in the post-2023 test period."
- "The dashed black line is the equal-weight average across all 14 categories. It peaks around 2020 then declines — most factors don't hold out-of-sample."
- "The red dotted line marks the train-to-validation boundary, and the blue dotted line marks validation-to-test. Cost margins continues climbing through both boundaries."

> **Time: ~60 sec**

---

### Slide 22 — Rolling t-statistics

- "Rolling t-statistics tell us whether the signal is stable over time or just worked in one lucky period."
- "The top panel shows 12-month rolling t-stats, the bottom shows 24-month. The gray dashed lines at plus and minus 1.96 are the 95% significance threshold."
- "Cost margins — the blue-green line — crosses above 1.96 multiple times across the full timeline, including after the validation and test boundaries. It's not a one-time fluke."
- "Labor workforce — the dark blue line — shows strong significance in the training period, dips during COVID, but recovers in the test period."
- "The key insight: signal strength is time-varying. Some categories are predictive in certain regimes but not others. This is precisely why RL alignment — optimizing for return prediction across different time horizons — is the natural next step."

> **Time: ~60 sec**

---

### Slide 23 — Cohort vs. 21-Day Excess Return

- "This is the single most important chart in the presentation. Does our multi-agent signal predict stock returns?"
- "The x-axis shows the five sentiment cohorts. The y-axis is the mean 21-day excess return — how much the stock beat or lagged the S&P 500 in the 21 days after the filing."
- "The right half works: neutral at 0.33%, positive at 0.36%, and very positive jumps to 3.69%. That's a strong tail signal — the 24 filings our system is most bullish on outperform by nearly 4% in three weeks."
- "The left half is inverted — very negative and negative actually show positive returns. This is the contrarian effect we've been discussing. Companies that report bad news often precede turnarounds."
- "The Spearman correlation is 0.009 — not statistically significant overall. But the long-short spread — very positive minus very negative — is +2.78%, which is economically meaningful."
- "The signal validation panel on the right summarizes the key numbers. The yellow callout at the bottom is honest: it's not monotonic yet. RL alignment in Task 3 is specifically designed to fix this by directly optimizing for the cohort-return relationship."

> **Time: ~90 sec**

---

### Slide 24 — Signal vs. 21-Day Excess Return

- "Here's the continuous version — filing signal on the x-axis, excess return on the y-axis, colored by sub-sector."
- "The OLS fit is flat — the continuous signal is not linearly predictive. The return cloud is wide, roughly plus or minus 20%, which reflects the natural volatility of individual stock returns over 21-day windows."
- "The value of our pipeline is in the tails, not the average. The very positive cohort at +3.69% is the outlier that matters. Task 3's RL alignment will push the model to produce more extreme and accurate tail predictions."

> **Time: ~40 sec**

---

### Slide 25 — Per-Sector Cohort vs. Return

- "Breaking it down by sector."
- "Airlines — top left — is very noisy with the very positive outlier at about 13% return, but that's only n=1 so we can't draw conclusions."
- "Defense — top right — shows the contrarian pattern clearly. The negative cohort outperforms, and the relationship is significantly inverse at -0.148."
- "General and industrial equipment — the bottom two — are the workhorses. They show the same pattern as the aggregate: flat in the middle, with the very positive tail outperforming. General has a Spearman of 0.039, industrial at 0.018."
- "The per-sector differences motivate sector-specific RL weighting in Task 3."

> **Time: ~50 sec**

---

### Slide 26 — Next Steps & Timeline

- "Here's where we stand and where we're headed."
- "On the left — everything we've completed through Week 8: HTML parsing across 86 tickers, factor extraction producing about 68,000 factors, sentiment scoring, IC analysis, a balanced 5,000-sample SFT dataset, QLoRA fine-tuning with loss dropping from 0.65 to 0.10, evaluation showing F1 of 0.731, and multi-agent consolidation producing 2,441 filing signals."
- "On the right — what's ahead for Weeks 9 through 15. Task 3 is reward model design and GRPO alignment across 1-month, 3-month, and 6-month horizons. The bonus is chain-of-thought reasoning with ORM and PRM. Task 4 includes full portfolio construction with long-short strategies by cohort, and backtesting against the S&P 500 with Sharpe, IR, and alpha metrics."
- "The expected outcome from the bottom callout: RL alignment should enforce the monotonic cohort-return relationship — matching the project spec's Base to SFT to SFT+RL progression. The very positive cohort at +3.69% is the signal to build on."

> **Time: ~60 sec**

---

### Slide 27 — Thank You

- "To wrap up — six key takeaways."
- "86 tickers, 10 years, about 68,000 factors extracted and scored."
- "5,000 annotated samples. SFT macro F1 of 0.731 — a +0.127 improvement over the base model."
- "The key SFT win: very positive F1 went from 0.206 to 0.793. The base model was essentially broken on this class."
- "2,441 filing signals produced by the multi-agent system. The very positive cohort earns +3.69% excess return."
- "Cost margins is our strongest factor — IS Sharpe of 1.03 that holds at 0.27 out-of-sample."
- "Task 3 with RL and GRPO will enforce the full monotonic signal-return relationship."
- "Thank you. We're happy to take questions."

> **Time: ~45 sec**

---

## Total Time Estimate

| Speaker | Slides | Time |
|---------|--------|------|
| Maggie | 1-9 | ~8 min |
| Luka | 10-16 | ~5.5 min |
| Roshan | 17-27 | ~10 min |
| **Total** | **27 slides** | **~23.5 min** |
| Q&A | | ~6.5 min |

This leaves comfortable room within the 30-minute slot without dragging.
