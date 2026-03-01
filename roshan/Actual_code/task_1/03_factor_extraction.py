"""
Step 3: Factor extraction via LLM.

For each filing:
  1. Load subsections from Step 2
  2. Route relevant questions to each subsection
  3. Call LLM for chunk-level Q&A (per subsection)
  4. Synthesize multi-subsection answers into per-filing factor JSONs

Usage:
    python3 03_factor_extraction.py                     # process all tickers
    python3 03_factor_extraction.py --tickers AAL LMT   # specific tickers
    python3 03_factor_extraction.py --max-filings 5     # limit per ticker (for testing)
"""

import argparse
import json
import logging
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from config import (
    SUBSECTIONS_DIR, FACTORS_DIR, TICKER_MAPPING_PATH,
    MAX_WORKERS_FILINGS,
)
from utils.llm_client import get_client, call_llm_json
from utils.question_router import get_applicable_questions, route_questions

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(FACTORS_DIR.parent / "factor_extraction.log", mode="a"),
    ],
)
log = logging.getLogger(__name__)


# ── Prompts ──────────────────────────────────────────────────────────────────

CHUNK_SYSTEM_PROMPT = """\
You are a financial analyst extracting thematic factors from SEC filing text.

You will receive:
1. A subsection of an SEC filing (MD&A or Risk Factors)
2. A list of analytical questions

For each question, determine if the subsection contains relevant information to answer it.

Respond with a JSON array. For each question that HAS relevant information in the text, include an entry:
{
  "key": "<question_key>",
  "found": true,
  "summary": "<1-3 sentence answer based on the text>",
  "evidence": "<exact quote from the text that supports your answer, max 2 sentences>"
}

For questions with NO relevant information in the text, include:
{
  "key": "<question_key>",
  "found": false
}

Rules:
- Only mark "found": true if the text clearly addresses the question
- Summaries must be directional — state whether something is improving, declining, stable, etc.
- Evidence must be verbatim quotes from the provided text
- Do not infer beyond what the text states
- Return valid JSON array only, no other text"""

SYNTHESIS_SYSTEM_PROMPT = """\
You are a financial analyst consolidating information about a single thematic factor from multiple subsections of an SEC filing.

You will receive multiple summaries and evidence quotes about the same factor, each from a different subsection of the same filing.

Produce a single consolidated entry:
{
  "summary": "<2-4 sentence consolidated summary capturing the full picture>",
  "evidence": [
    "<most important evidence quote>",
    "<second most important evidence quote>",
    "<third evidence quote if materially different>"
  ]
}

Rules:
- The consolidated summary should reconcile or integrate all inputs
- Be directional: state whether the factor is positive, negative, or mixed
- Select the 2-4 most informative evidence quotes (verbatim, do not combine or edit)
- If inputs conflict, note the tension in the summary
- Return valid JSON only, no other text"""


# ── Chunk-level Q&A ─────────────────────────────────────────────────────────

def build_chunk_prompt(subsection: dict, questions: list[dict]) -> str:
    """Build the user prompt for chunk-level Q&A."""
    question_block = "\n".join(
        f"- [{q['key']}] {q['question']}"
        for q in questions
    )

    return f"""## Subsection: {subsection['name']}
(Section: {subsection['section']})

### Text:
{subsection['text']}

### Questions:
{question_block}

Analyze the text above and answer each question. Return a JSON array."""


def process_subsection(client, model, subsection: dict, questions: list[dict]) -> list[dict]:
    """
    Run chunk-level Q&A on one subsection.

    Returns list of {key, found, summary, evidence, section, subsection_name} dicts
    for questions where found=True.
    """
    if not questions:
        return []

    prompt = build_chunk_prompt(subsection, questions)
    result = call_llm_json(client, model, CHUNK_SYSTEM_PROMPT, prompt, max_tokens=4096)

    if result is None:
        log.warning(f"    LLM returned None for subsection: {subsection['name'][:50]}")
        return []

    if not isinstance(result, list):
        log.warning(f"    LLM returned non-list for subsection: {subsection['name'][:50]}")
        return []

    # Filter to found=True and enrich with source info
    found_items = []
    for item in result:
        if not isinstance(item, dict):
            continue
        if item.get("found") is True and item.get("key") and item.get("summary"):
            found_items.append({
                "key": item["key"],
                "summary": item["summary"],
                "evidence": item.get("evidence", ""),
                "section": subsection["section"],
                "subsection_name": subsection["name"],
            })

    return found_items


# ── Per-filing Synthesis ─────────────────────────────────────────────────────

def synthesize_factor(client, model, key: str, category: str, entries: list[dict]) -> dict:
    """
    Synthesize multiple chunk-level answers for the same factor into one consolidated entry.

    If only one entry exists, use it directly (no LLM call needed).
    """
    if len(entries) == 1:
        e = entries[0]
        return {
            "key": key,
            "category": category,
            "summary": e["summary"],
            "evidence": [
                {
                    "text": e["evidence"],
                    "section": e["section"],
                    "subsection": e["subsection_name"],
                }
            ],
            "sentiment": None,
        }

    # Multiple entries — call LLM to synthesize
    input_block = "\n\n".join(
        f"### From subsection: {e['subsection_name']} ({e['section']})\n"
        f"Summary: {e['summary']}\n"
        f"Evidence: \"{e['evidence']}\""
        for e in entries
    )

    user_prompt = f"""Factor: {key}

The following summaries and evidence quotes come from different subsections of the same SEC filing, all addressing the same factor.

{input_block}

Consolidate into a single entry with one summary and 2-4 best evidence quotes."""

    result = call_llm_json(client, model, SYNTHESIS_SYSTEM_PROMPT, user_prompt, max_tokens=2048)

    if result and isinstance(result, dict):
        # Build evidence list with source info
        evidence_list = []
        raw_evidence = result.get("evidence", [])
        if isinstance(raw_evidence, list):
            for i, quote in enumerate(raw_evidence):
                if isinstance(quote, str) and quote.strip():
                    # Match quote back to source subsection (best effort)
                    source_entry = entries[min(i, len(entries) - 1)]
                    evidence_list.append({
                        "text": quote.strip(),
                        "section": source_entry["section"],
                        "subsection": source_entry["subsection_name"],
                    })

        return {
            "key": key,
            "category": category,
            "summary": result.get("summary", entries[0]["summary"]),
            "evidence": evidence_list if evidence_list else [
                {"text": entries[0]["evidence"], "section": entries[0]["section"],
                 "subsection": entries[0]["subsection_name"]}
            ],
            "sentiment": None,
        }

    # Fallback: if synthesis LLM call failed, use the longest entry
    best = max(entries, key=lambda e: len(e["summary"]))
    return {
        "key": key,
        "category": category,
        "summary": best["summary"],
        "evidence": [
            {"text": e["evidence"], "section": e["section"], "subsection": e["subsection_name"]}
            for e in entries[:3]
        ],
        "sentiment": None,
    }


# ── Filing-level Processing ─────────────────────────────────────────────────

def process_filing(subsections_file: Path, client, model) -> dict | None:
    """
    Process one filing: chunk-level Q&A + synthesis → factor JSON.

    Returns the factor JSON dict or None on failure.
    """
    with open(subsections_file) as f:
        data = json.load(f)

    ticker = data["ticker"]
    form_type = data["form"]
    filing_date = data["filing_date"]
    subsections = data["subsections"]

    if not subsections:
        log.warning(f"  {ticker} {filing_date}: no subsections")
        return None

    # Get applicable questions for this ticker (based on sub-sector)
    all_questions = get_applicable_questions(ticker)

    if not all_questions:
        log.warning(f"  {ticker}: no applicable questions found")
        return None

    # Phase 1: Chunk-level Q&A
    all_chunk_answers: list[dict] = []

    for i, sub in enumerate(subsections):
        # Route relevant questions to this subsection
        routed = route_questions(sub["name"], sub["text"], all_questions)

        log.debug(
            f"    Subsection {i+1}/{len(subsections)}: {sub['name'][:50]}... "
            f"→ {len(routed)} questions"
        )

        # Call LLM
        answers = process_subsection(client, model, sub, routed)
        all_chunk_answers.extend(answers)

        if answers:
            log.debug(f"      → {len(answers)} factors found")

    log.info(
        f"  {ticker} {form_type} {filing_date}: "
        f"{len(all_chunk_answers)} chunk-level answers from {len(subsections)} subsections"
    )

    if not all_chunk_answers:
        log.warning(f"  {ticker} {filing_date}: no factors extracted")
        return None

    # Phase 2: Group by factor key and synthesize
    grouped: dict[str, list[dict]] = defaultdict(list)
    for answer in all_chunk_answers:
        grouped[answer["key"]].append(answer)

    # Build category lookup from all_questions
    key_to_category: dict[str, str] = {}
    for category_name, questions in all_questions.items():
        for key in questions:
            key_to_category[key] = category_name

    # Synthesize each factor
    factors = []
    for key, entries in grouped.items():
        category = key_to_category.get(key, "unknown")
        factor = synthesize_factor(client, model, key, category, entries)
        factors.append(factor)

    log.info(f"  {ticker} {form_type} {filing_date}: {len(factors)} factors after synthesis")

    return {
        "ticker": ticker,
        "form": form_type,
        "filing_date": filing_date,
        "model": model,
        "num_factors": len(factors),
        "factors": factors,
    }


# ── Main ─────────────────────────────────────────────────────────────────────

def get_all_tickers() -> list[str]:
    with open(TICKER_MAPPING_PATH) as f:
        mapping = json.load(f)
    tickers = []
    for sector_tickers in mapping.values():
        tickers.extend(sector_tickers)
    return sorted(tickers)


def main():
    parser = argparse.ArgumentParser(description="Extract factors from filing subsections via LLM")
    parser.add_argument("--tickers", nargs="+", help="Process specific tickers")
    parser.add_argument("--max-filings", type=int, default=0, help="Max filings per ticker (0=all)")
    parser.add_argument("--workers", type=int, default=1, help="Parallel filing processing")
    args = parser.parse_args()

    FACTORS_DIR.mkdir(parents=True, exist_ok=True)

    # Initialize LLM client
    client, model = get_client()
    log.info(f"Using provider model: {model}")

    tickers = [t.upper() for t in args.tickers] if args.tickers else get_all_tickers()
    log.info(f"Processing {len(tickers)} tickers")

    total_filings = 0
    total_success = 0
    total_factors = 0

    for ticker in tickers:
        ticker_input = SUBSECTIONS_DIR / ticker
        if not ticker_input.exists():
            log.warning(f"{ticker}: no subsections found")
            continue

        ticker_output = FACTORS_DIR / ticker
        ticker_output.mkdir(parents=True, exist_ok=True)

        sub_files = sorted(ticker_input.glob("*_subsections.json"))
        if args.max_filings > 0:
            sub_files = sub_files[:args.max_filings]

        def _process_one(sub_file: Path) -> tuple[Path, dict | None]:
            stem = sub_file.stem.replace("_subsections", "")
            out_file = ticker_output / f"{stem}_factors.json"

            # Resume-safe
            if out_file.exists():
                return out_file, None

            result = process_filing(sub_file, client, model)
            if result:
                with open(out_file, "w") as f:
                    json.dump(result, f, indent=2)
            return out_file, result

        if args.workers > 1:
            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                futures = {pool.submit(_process_one, sf): sf for sf in sub_files}
                for future in as_completed(futures):
                    total_filings += 1
                    try:
                        out_file, result = future.result()
                        if result:
                            total_success += 1
                            total_factors += result["num_factors"]
                    except Exception as e:
                        sf = futures[future]
                        log.error(f"  {sf.name}: CRASHED — {e}")
        else:
            for sub_file in sub_files:
                total_filings += 1
                try:
                    out_file, result = _process_one(sub_file)
                    if result:
                        total_success += 1
                        total_factors += result["num_factors"]
                except Exception as e:
                    log.error(f"  {sub_file.name}: CRASHED — {e}")

        log.info(f"  {ticker}: done ({len(sub_files)} filings)")

    log.info("=" * 60)
    log.info(f"DONE: {total_success}/{total_filings} filings, {total_factors} total factors")


if __name__ == "__main__":
    main()
