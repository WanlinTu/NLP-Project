# NLP Project

MD&A text
    ↓
Sentiment / uncertainty / tone (NLP output)
    ↓
Performance check (future returns)

Reading the Energy Market: Evidence from MD&A Disclosures




Reading the Energy Market: Evidence from MD&amp;A Disclosures

Concrete project pipeline 
Step 1 — Filter the universe (this is key)

From your SEC dataset, subset to energy-related firms.

Examples (you don’t need all):

Oil & Gas producers

Utilities

Integrated energy

Renewable / clean energy

You can justify this as:

“Sector-focused NLP improves signal coherence.”

Step 2 — Clean the MD&A with intent (important)

Now cleaning is investment-driven, not generic.

You should:

Remove boilerplate safe-harbor language

Keep:

forward-looking language

risk discussion

capex / investment plans

demand & pricing language

This is where your project becomes smart, not just technical.

Step 3 — Define 4–6 ENERGY-SPECIFIC dimensions

Instead of 100 questions like the sample report, keep it simple and interpretable.

For example:

Demand & Pricing Outlook

Capital Expenditure / Investment

Operational Risk

Regulatory / ESG Pressure

Growth / Expansion Narrative

Uncertainty & Hedging Language

You are not predicting returns directly yet — you’re building signals.

Step 4 — Sentiment + intensity (this is where stocks come in)

For each MD&A (or chunk), compute:

Overall sentiment

Uncertainty score

Positive vs negative forward-looking tone

You can do this with:

Lexicon-based methods (safe)

Or pre-trained financial sentiment models (still safe)

Now you can say things like:

“Company A’s MD&A became more confident and capex-focused before year X.”

Step 5 — Link text → stock performance (lightweight)

This is the “what stocks to buy” part, done correctly.

You don’t need fancy backtesting.

You can:

Compare:

high-sentiment vs low-sentiment energy firms

rising vs falling uncertainty

Look at future returns (3–12 months)

Even descriptive stats are enough:

averages

boxplots

trends

That’s already investment insight.
