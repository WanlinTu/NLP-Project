"""
Step 1: Extract MD&A and Risk Factors sections from raw SEC filing HTMLs.

Usage:
    python 01_extract_sections.py                     # process all tickers
    python 01_extract_sections.py --tickers AAL LMT   # process specific tickers
    python 01_extract_sections.py --dry-run            # show what would be processed
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import DATA_ROOT, EXTRACTED_SECTIONS_DIR, TICKER_MAPPING_PATH
from utils.html_parser import extract_sections, detect_form_type

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(EXTRACTED_SECTIONS_DIR.parent / "extraction.log", mode="a"),
    ],
)
log = logging.getLogger(__name__)


def get_all_tickers() -> list[str]:
    """Get all tickers from the ticker mapping."""
    with open(TICKER_MAPPING_PATH) as f:
        mapping = json.load(f)
    tickers = []
    for sector_tickers in mapping.values():
        tickers.extend(sector_tickers)
    return sorted(tickers)


def find_filings(ticker: str) -> list[Path]:
    """Find all filing HTML files for a ticker."""
    ticker_dir = DATA_ROOT / ticker
    if not ticker_dir.exists():
        return []

    filings = []
    for form_dir in ["10-K", "10-Q"]:
        form_path = ticker_dir / form_dir
        if form_path.exists():
            filings.extend(sorted(form_path.glob("*.html")))
    return filings


def output_path_for_filing(filepath: Path) -> Path:
    """
    Compute output directory for a filing.

    Input:  Data/AAL/10-K/AAL_10-K_2024-02-21.html
    Output: output/extracted_sections/AAL/AAL_10-K_2024-02-21/
    """
    stem = filepath.stem  # e.g., AAL_10-K_2024-02-21
    ticker = stem.split("_")[0]
    return EXTRACTED_SECTIONS_DIR / ticker / stem


def is_already_extracted(output_dir: Path) -> bool:
    """Check if both sections have already been extracted (resume-safe)."""
    mda = output_dir / "mda.html"
    rf = output_dir / "risk_factors.html"
    # Consider extracted if at least mda exists (risk_factors may legitimately be missing)
    return mda.exists()


def process_filing(filepath: Path) -> dict:
    """
    Process a single filing: extract MD&A and Risk Factors.

    Returns a status dict for logging.
    """
    stem = filepath.stem
    output_dir = output_path_for_filing(filepath)

    # Resume check
    if is_already_extracted(output_dir):
        return {"file": stem, "status": "skipped", "reason": "already extracted"}

    try:
        results = extract_sections(filepath)
    except Exception as e:
        log.error(f"  CRASH {stem}: {e}")
        return {"file": stem, "status": "error", "reason": str(e)}

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    status = {"file": stem, "status": "ok", "sections": {}}

    for section_name, result in results.items():
        out_file = output_dir / f"{section_name}.html"

        if result.success:
            out_file.write_text(result.html_content, encoding="utf-8")
            status["sections"][section_name] = {
                "success": True,
                "text_length": result.text_length,
            }
        else:
            # Write an empty file with error comment so we know we tried
            out_file.write_text(
                f"<!-- EXTRACTION FAILED: {result.error} -->",
                encoding="utf-8",
            )
            status["sections"][section_name] = {
                "success": False,
                "error": result.error,
            }

    return status


def process_ticker(ticker: str, dry_run: bool = False) -> dict:
    """Process all filings for a single ticker."""
    filings = find_filings(ticker)

    if not filings:
        log.warning(f"  {ticker}: no filings found")
        return {"ticker": ticker, "total": 0, "processed": 0, "skipped": 0, "errors": 0}

    if dry_run:
        already = sum(1 for f in filings if is_already_extracted(output_path_for_filing(f)))
        log.info(f"  {ticker}: {len(filings)} filings ({already} already extracted)")
        return {"ticker": ticker, "total": len(filings), "would_process": len(filings) - already}

    processed = 0
    skipped = 0
    errors = 0
    mda_ok = 0
    rf_ok = 0

    for filepath in filings:
        result = process_filing(filepath)

        if result["status"] == "skipped":
            skipped += 1
        elif result["status"] == "error":
            errors += 1
            log.error(f"  {ticker} | {result['file']}: {result['reason']}")
        else:
            processed += 1
            sections = result.get("sections", {})
            if sections.get("mda", {}).get("success"):
                mda_ok += 1
            else:
                err = sections.get("mda", {}).get("error", "unknown")
                log.warning(f"  {ticker} | {result['file']}: MD&A failed — {err}")
            if sections.get("risk_factors", {}).get("success"):
                rf_ok += 1

    return {
        "ticker": ticker,
        "total": len(filings),
        "processed": processed,
        "skipped": skipped,
        "errors": errors,
        "mda_ok": mda_ok,
        "rf_ok": rf_ok,
    }


def main():
    parser = argparse.ArgumentParser(description="Extract MD&A and Risk Factors from SEC filings")
    parser.add_argument("--tickers", nargs="+", help="Process specific tickers (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be processed")
    parser.add_argument("--workers", type=int, default=1, help="Parallel ticker processing")
    args = parser.parse_args()

    # Ensure output directory exists
    EXTRACTED_SECTIONS_DIR.mkdir(parents=True, exist_ok=True)

    # Get tickers to process
    if args.tickers:
        tickers = [t.upper() for t in args.tickers]
    else:
        tickers = get_all_tickers()

    log.info(f"Processing {len(tickers)} tickers (dry_run={args.dry_run})")

    # Process tickers
    all_stats = []

    if args.workers > 1 and not args.dry_run:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {
                pool.submit(process_ticker, ticker, args.dry_run): ticker
                for ticker in tickers
            }
            for future in as_completed(futures):
                ticker = futures[future]
                try:
                    stats = future.result()
                    all_stats.append(stats)
                    log.info(
                        f"  {ticker}: {stats.get('processed', 0)} processed, "
                        f"{stats.get('skipped', 0)} skipped, {stats.get('errors', 0)} errors"
                    )
                except Exception as e:
                    log.error(f"  {ticker}: CRASHED — {e}")
    else:
        for ticker in tickers:
            log.info(f"Processing {ticker}...")
            stats = process_ticker(ticker, args.dry_run)
            all_stats.append(stats)
            if not args.dry_run:
                log.info(
                    f"  {ticker}: {stats.get('processed', 0)} processed, "
                    f"{stats.get('skipped', 0)} skipped, {stats.get('errors', 0)} errors | "
                    f"MD&A: {stats.get('mda_ok', 0)}, RF: {stats.get('rf_ok', 0)}"
                )

    # Summary
    if not args.dry_run:
        total_filings = sum(s["total"] for s in all_stats)
        total_processed = sum(s.get("processed", 0) for s in all_stats)
        total_skipped = sum(s.get("skipped", 0) for s in all_stats)
        total_errors = sum(s.get("errors", 0) for s in all_stats)
        total_mda = sum(s.get("mda_ok", 0) for s in all_stats)
        total_rf = sum(s.get("rf_ok", 0) for s in all_stats)

        log.info("=" * 60)
        log.info(f"DONE: {total_filings} filings across {len(tickers)} tickers")
        log.info(f"  Processed: {total_processed}")
        log.info(f"  Skipped:   {total_skipped}")
        log.info(f"  Errors:    {total_errors}")
        log.info(f"  MD&A OK:   {total_mda}")
        log.info(f"  Risk OK:   {total_rf}")

    # Write summary JSON
    summary_path = EXTRACTED_SECTIONS_DIR / "extraction_summary.json"
    with open(summary_path, "w") as f:
        json.dump({"tickers": all_stats}, f, indent=2)
    log.info(f"Summary written to {summary_path}")


if __name__ == "__main__":
    main()
