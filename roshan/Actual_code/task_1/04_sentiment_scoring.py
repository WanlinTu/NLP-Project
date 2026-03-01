"""
Step 4: Sentiment scoring for extracted factors.

Reads factor JSONs from Step 3 and adds 5-class sentiment labels
to each factor via LLM.

Usage:
    python3 04_sentiment_scoring.py                     # process all tickers
    python3 04_sentiment_scoring.py --tickers AAL LMT   # specific tickers
    python3 04_sentiment_scoring.py --batch-size 8       # factors per LLM call
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from config import (
    FACTORS_DIR, FACTORS_SCORED_DIR, TICKER_MAPPING_PATH,
)
from utils.llm_client import get_client, call_llm_json

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(FACTORS_SCORED_DIR.parent / "sentiment_scoring.log", mode="a"),
    ],
)
log = logging.getLogger(__name__)


# ── Prompt ───────────────────────────────────────────────────────────────────

SENTIMENT_SYSTEM_PROMPT = """\
You are a financial analyst assigning sentiment labels to thematic factors extracted from SEC filings.

For each factor, you will receive its summary and evidence quotes from the filing.

Assign a sentiment label from exactly these five classes:
- "very_negative": Clear, significant deterioration or major risk
- "negative": Moderate headwind, declining trend, or concern
- "neutral": Stable, mixed signals, or no clear directional signal
- "positive": Moderate improvement, tailwind, or opportunity
- "very_positive": Clear, significant improvement or major positive development

Respond with a JSON array where each entry has:
{
  "key": "<factor_key>",
  "label": "<one of: very_negative, negative, neutral, positive, very_positive>",
  "rationale": "<1 sentence explaining why you chose this label>",
  "confidence": <float 0.0 to 1.0>
}

Rules:
- Base your label ONLY on the summary and evidence provided
- Be decisive — avoid defaulting to "neutral" unless genuinely mixed
- Confidence should reflect how clearly the text supports a directional reading
- Return valid JSON array only, no other text"""


# ── Batch Scoring ────────────────────────────────────────────────────────────

def build_sentiment_prompt(factors_batch: list[dict]) -> str:
    """Build user prompt for a batch of factors."""
    blocks = []
    for factor in factors_batch:
        evidence_text = "\n".join(
            f"  - \"{e['text']}\""
            for e in factor.get("evidence", [])
            if isinstance(e, dict) and e.get("text")
        )
        blocks.append(
            f"### Factor: {factor['key']} (category: {factor['category']})\n"
            f"Summary: {factor['summary']}\n"
            f"Evidence:\n{evidence_text}"
        )

    return "\n\n".join(blocks) + "\n\nAssign sentiment labels to each factor above. Return a JSON array."


def score_batch(client, model, factors_batch: list[dict]) -> dict[str, dict]:
    """
    Score a batch of factors for sentiment.

    Returns {factor_key: {label, rationale, confidence}} for successfully scored factors.
    """
    prompt = build_sentiment_prompt(factors_batch)
    result = call_llm_json(client, model, SENTIMENT_SYSTEM_PROMPT, prompt, max_tokens=2048)

    if result is None or not isinstance(result, list):
        log.warning(f"    Sentiment LLM returned invalid result for batch of {len(factors_batch)}")
        return {}

    scored = {}
    valid_labels = {"very_negative", "negative", "neutral", "positive", "very_positive"}

    for item in result:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        label = item.get("label")
        if not key or label not in valid_labels:
            continue
        scored[key] = {
            "label": label,
            "rationale": item.get("rationale", ""),
            "confidence": min(1.0, max(0.0, float(item.get("confidence", 0.5)))),
        }

    return scored


# ── Filing-level Processing ─────────────────────────────────────────────────

def process_filing(factor_file: Path, client, model, batch_size: int) -> dict | None:
    """
    Score all factors in one filing for sentiment.

    Returns the updated factor JSON with sentiment populated, or None on failure.
    """
    with open(factor_file) as f:
        data = json.load(f)

    factors = data.get("factors", [])
    if not factors:
        return None

    # Batch factors for scoring
    all_scored: dict[str, dict] = {}

    for i in range(0, len(factors), batch_size):
        batch = factors[i:i + batch_size]
        scored = score_batch(client, model, batch)
        all_scored.update(scored)

    # Apply sentiment labels to factors
    scored_count = 0
    for factor in factors:
        sentiment = all_scored.get(factor["key"])
        if sentiment:
            factor["sentiment"] = sentiment
            scored_count += 1
        else:
            # Leave as None if scoring failed for this factor
            factor["sentiment"] = None

    log.info(
        f"  {data['ticker']} {data['form']} {data['filing_date']}: "
        f"{scored_count}/{len(factors)} factors scored"
    )

    return data


# ── Main ─────────────────────────────────────────────────────────────────────

def get_all_tickers() -> list[str]:
    with open(TICKER_MAPPING_PATH) as f:
        mapping = json.load(f)
    tickers = []
    for sector_tickers in mapping.values():
        tickers.extend(sector_tickers)
    return sorted(tickers)


def main():
    parser = argparse.ArgumentParser(description="Score extracted factors for sentiment")
    parser.add_argument("--tickers", nargs="+", help="Process specific tickers")
    parser.add_argument("--batch-size", type=int, default=8, help="Factors per LLM call")
    args = parser.parse_args()

    FACTORS_SCORED_DIR.mkdir(parents=True, exist_ok=True)

    # Initialize LLM client
    client, model = get_client()
    log.info(f"Using provider model: {model}")

    tickers = [t.upper() for t in args.tickers] if args.tickers else get_all_tickers()
    log.info(f"Processing {len(tickers)} tickers")

    total_filings = 0
    total_success = 0
    total_factors_scored = 0

    for ticker in tickers:
        ticker_input = FACTORS_DIR / ticker
        if not ticker_input.exists():
            log.warning(f"{ticker}: no factor files found")
            continue

        ticker_output = FACTORS_SCORED_DIR / ticker
        ticker_output.mkdir(parents=True, exist_ok=True)

        factor_files = sorted(ticker_input.glob("*_factors.json"))

        for factor_file in factor_files:
            total_filings += 1

            out_file = ticker_output / factor_file.name

            # Resume-safe
            if out_file.exists():
                continue

            try:
                result = process_filing(factor_file, client, model, args.batch_size)
                if result:
                    with open(out_file, "w") as f:
                        json.dump(result, f, indent=2)
                    total_success += 1
                    total_factors_scored += sum(
                        1 for fac in result["factors"]
                        if fac.get("sentiment") is not None
                    )
            except Exception as e:
                log.error(f"  {factor_file.name}: CRASHED — {e}")

        log.info(f"  {ticker}: done ({len(factor_files)} filings)")

    log.info("=" * 60)
    log.info(
        f"DONE: {total_success}/{total_filings} filings, "
        f"{total_factors_scored} total factors scored"
    )


if __name__ == "__main__":
    main()
