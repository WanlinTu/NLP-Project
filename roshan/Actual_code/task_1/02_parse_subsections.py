"""
Step 2: Parse extracted sections into subsections.

Reads minimal HTML from Step 1 and splits into logical subsections:
- MD&A: split by bold headings
- Risk Factors: split by individual risk items

Usage:
    python3 02_parse_subsections.py                     # process all tickers
    python3 02_parse_subsections.py --tickers AAL LMT   # specific tickers
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path

from config import EXTRACTED_SECTIONS_DIR, SUBSECTIONS_DIR, TICKER_MAPPING_PATH

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# Rough token estimate: ~4 chars per token for English text
CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    return len(text) // CHARS_PER_TOKEN


def strip_html(text: str) -> str:
    """Remove HTML tags, returning plain text."""
    return re.sub(r"<[^>]+>", "", text).strip()


def parse_mda_subsections(html_content: str) -> list[dict]:
    """
    Split MD&A HTML into subsections based on bold headings.

    Looks for <b>...</b> tags that act as section headings.
    Everything between two headings is one subsection.
    """
    # Split on bold tags, keeping the delimiter
    parts = re.split(r"(<b>.*?</b>)", html_content, flags=re.DOTALL)

    subsections = []
    current_name = "Introduction"
    current_text_parts: list[str] = []

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Check if this is a heading
        bold_match = re.match(r"<b>(.*?)</b>", part, re.DOTALL)
        if bold_match:
            heading_text = strip_html(bold_match.group(1)).strip()

            # Skip very short or navigation headings
            if not heading_text or len(heading_text) < 3:
                continue
            if heading_text.lower() in ("table of contents",):
                continue

            # Save previous subsection if it has content
            if current_text_parts:
                text = "\n".join(current_text_parts).strip()
                plain = strip_html(text)
                if len(plain) > 50:  # skip trivially small subsections
                    subsections.append({
                        "name": current_name,
                        "section": "mda",
                        "text": plain,
                        "token_estimate": estimate_tokens(plain),
                    })

            current_name = heading_text
            current_text_parts = []
        else:
            current_text_parts.append(part)

    # Don't forget the last subsection
    if current_text_parts:
        text = "\n".join(current_text_parts).strip()
        plain = strip_html(text)
        if len(plain) > 50:
            subsections.append({
                "name": current_name,
                "section": "mda",
                "text": plain,
                "token_estimate": estimate_tokens(plain),
            })

    # Merge very small subsections (< 200 chars) into the next one
    merged = []
    i = 0
    while i < len(subsections):
        sub = subsections[i]
        if sub["token_estimate"] < 50 and i + 1 < len(subsections):
            # Merge into next
            nxt = subsections[i + 1]
            nxt["text"] = sub["text"] + "\n\n" + nxt["text"]
            nxt["name"] = sub["name"] + " / " + nxt["name"]
            nxt["token_estimate"] = estimate_tokens(nxt["text"])
            i += 1
        else:
            merged.append(sub)
            i += 1

    return merged


def parse_risk_factors_subsections(html_content: str) -> list[dict]:
    """
    Split Risk Factors HTML into individual risk items.

    Risk factors are typically separated by bold or bold-italic headings.
    Each heading describes the specific risk.
    """
    # Split on bold tags
    parts = re.split(r"(<b>.*?</b>)", html_content, flags=re.DOTALL)

    subsections = []
    current_name = "Risk Factors Overview"
    current_text_parts: list[str] = []
    found_first_risk = False

    for part in parts:
        part = part.strip()
        if not part:
            continue

        bold_match = re.match(r"<b>(.*?)</b>", part, re.DOTALL)
        if bold_match:
            heading_text = strip_html(bold_match.group(1)).strip()

            if not heading_text or len(heading_text) < 3:
                continue
            if heading_text.lower() in ("table of contents",):
                continue

            # Check if this looks like a risk factor heading
            # Risk factor headings are typically longer sentences
            is_risk_heading = (
                len(heading_text) > 20
                or heading_text.lower().startswith("risk")
                or "could" in heading_text.lower()
                or "may" in heading_text.lower()
                or "adversely" in heading_text.lower()
            )

            # Also catch category headers like "Risks Related to our Business"
            is_category = (
                heading_text.lower().startswith("risks related")
                or heading_text.lower().startswith("risk factor")
                or "item 1a" in heading_text.lower()
            )

            if is_risk_heading or is_category:
                # Save previous subsection
                if current_text_parts:
                    text = "\n".join(current_text_parts).strip()
                    plain = strip_html(text)
                    if len(plain) > 30:
                        subsections.append({
                            "name": current_name,
                            "section": "risk_factors",
                            "text": plain,
                            "token_estimate": estimate_tokens(plain),
                        })

                current_name = heading_text
                current_text_parts = []
                found_first_risk = True
            else:
                # Non-risk bold text, treat as part of current section
                current_text_parts.append(heading_text)
        else:
            current_text_parts.append(part)

    # Last subsection
    if current_text_parts:
        text = "\n".join(current_text_parts).strip()
        plain = strip_html(text)
        if len(plain) > 30:
            subsections.append({
                "name": current_name,
                "section": "risk_factors",
                "text": plain,
                "token_estimate": estimate_tokens(plain),
            })

    # If we couldn't split into individual risks, return the whole thing as one block
    if len(subsections) <= 1:
        plain = strip_html(html_content)
        if len(plain) > 50:
            return [{
                "name": "Risk Factors",
                "section": "risk_factors",
                "text": plain,
                "token_estimate": estimate_tokens(plain),
            }]

    return subsections


def process_filing(filing_dir: Path) -> dict | None:
    """
    Process one filing directory containing mda.html and risk_factors.html.

    Returns subsections JSON or None if nothing to process.
    """
    mda_file = filing_dir / "mda.html"
    rf_file = filing_dir / "risk_factors.html"

    # Parse filing metadata from directory name: TICKER_FORM_DATE
    parts = filing_dir.name.split("_")
    if len(parts) < 3:
        return None
    ticker = parts[0]
    form = parts[1]
    date = "_".join(parts[2:])

    all_subsections = []

    # Parse MD&A
    if mda_file.exists():
        content = mda_file.read_text(encoding="utf-8")
        if not content.startswith("<!-- EXTRACTION FAILED"):
            subs = parse_mda_subsections(content)
            all_subsections.extend(subs)

    # Parse Risk Factors
    if rf_file.exists():
        content = rf_file.read_text(encoding="utf-8")
        if not content.startswith("<!-- EXTRACTION FAILED"):
            subs = parse_risk_factors_subsections(content)
            all_subsections.extend(subs)

    if not all_subsections:
        return None

    return {
        "ticker": ticker,
        "form": form,
        "filing_date": date,
        "num_subsections": len(all_subsections),
        "total_tokens": sum(s["token_estimate"] for s in all_subsections),
        "subsections": all_subsections,
    }


def get_all_tickers() -> list[str]:
    with open(TICKER_MAPPING_PATH) as f:
        mapping = json.load(f)
    tickers = []
    for sector_tickers in mapping.values():
        tickers.extend(sector_tickers)
    return sorted(tickers)


def main():
    parser = argparse.ArgumentParser(description="Parse extracted sections into subsections")
    parser.add_argument("--tickers", nargs="+", help="Process specific tickers")
    args = parser.parse_args()

    SUBSECTIONS_DIR.mkdir(parents=True, exist_ok=True)

    tickers = [t.upper() for t in args.tickers] if args.tickers else get_all_tickers()

    total_filings = 0
    total_success = 0
    total_subsections = 0

    for ticker in tickers:
        ticker_input = EXTRACTED_SECTIONS_DIR / ticker
        if not ticker_input.exists():
            log.warning(f"{ticker}: no extracted sections found")
            continue

        ticker_output = SUBSECTIONS_DIR / ticker
        ticker_output.mkdir(parents=True, exist_ok=True)

        filing_dirs = sorted(d for d in ticker_input.iterdir() if d.is_dir())

        for filing_dir in filing_dirs:
            total_filings += 1
            out_file = ticker_output / f"{filing_dir.name}_subsections.json"

            # Resume-safe
            if out_file.exists():
                continue

            result = process_filing(filing_dir)
            if result:
                with open(out_file, "w") as f:
                    json.dump(result, f, indent=2)
                total_success += 1
                total_subsections += result["num_subsections"]
            else:
                log.warning(f"  {filing_dir.name}: no subsections extracted")

        log.info(f"  {ticker}: processed {len(filing_dirs)} filings")

    log.info(f"DONE: {total_success}/{total_filings} filings, {total_subsections} total subsections")


if __name__ == "__main__":
    main()
