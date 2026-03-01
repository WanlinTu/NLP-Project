"""
Pipeline orchestrator: runs Steps 1-4 end-to-end.

Usage:
    python3 run_pipeline.py                          # run all steps, all tickers
    python3 run_pipeline.py --tickers AAL LMT        # specific tickers
    python3 run_pipeline.py --steps 1 2              # only steps 1 and 2
    python3 run_pipeline.py --steps 3 4 --tickers AAL --max-filings 3  # test LLM on 3 filings
"""

import argparse
import logging
import subprocess
import sys
import time
from pathlib import Path

from config import OUTPUT_ROOT

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

ACTUAL_CODE_DIR = Path(__file__).resolve().parent


def run_step(step_num: int, tickers: list[str] | None, max_filings: int, workers: int, batch_size: int) -> bool:
    """
    Run a single pipeline step as a subprocess.

    Returns True on success, False on failure.
    """
    scripts = {
        1: "01_extract_sections.py",
        2: "02_parse_subsections.py",
        3: "03_factor_extraction.py",
        4: "04_sentiment_scoring.py",
    }

    script = scripts.get(step_num)
    if not script:
        log.error(f"Unknown step: {step_num}")
        return False

    script_path = ACTUAL_CODE_DIR / script
    if not script_path.exists():
        log.error(f"Script not found: {script_path}")
        return False

    cmd = [sys.executable, str(script_path)]

    if tickers:
        cmd.extend(["--tickers"] + tickers)

    # Step-specific args
    if step_num in (1,) and workers > 1:
        cmd.extend(["--workers", str(workers)])
    if step_num == 3:
        if max_filings > 0:
            cmd.extend(["--max-filings", str(max_filings)])
        if workers > 1:
            cmd.extend(["--workers", str(workers)])
    if step_num == 4:
        cmd.extend(["--batch-size", str(batch_size)])

    log.info(f"{'='*60}")
    log.info(f"STEP {step_num}: {script}")
    log.info(f"Command: {' '.join(cmd)}")
    log.info(f"{'='*60}")

    start = time.time()

    try:
        result = subprocess.run(
            cmd,
            cwd=str(ACTUAL_CODE_DIR),
            check=False,
        )
        elapsed = time.time() - start

        if result.returncode == 0:
            log.info(f"STEP {step_num} completed in {elapsed:.1f}s")
            return True
        else:
            log.error(f"STEP {step_num} failed with return code {result.returncode} after {elapsed:.1f}s")
            return False

    except Exception as e:
        elapsed = time.time() - start
        log.error(f"STEP {step_num} crashed after {elapsed:.1f}s: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Run the factor extraction pipeline end-to-end",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Steps:
  1  Extract MD&A and Risk Factors from raw SEC filing HTMLs
  2  Parse extracted sections into subsections
  3  Factor extraction via LLM (requires GPU / vLLM running)
  4  Sentiment scoring via LLM (requires GPU / vLLM running)

Examples:
  python3 run_pipeline.py                          # all steps, all tickers
  python3 run_pipeline.py --steps 1 2              # extraction only (no LLM)
  python3 run_pipeline.py --steps 3 --tickers AAL --max-filings 2  # quick LLM test
        """,
    )
    parser.add_argument(
        "--steps", nargs="+", type=int, default=[1, 2, 3, 4],
        help="Which steps to run (default: 1 2 3 4)",
    )
    parser.add_argument("--tickers", nargs="+", help="Process specific tickers (default: all)")
    parser.add_argument("--max-filings", type=int, default=0, help="Max filings per ticker for step 3 (0=all)")
    parser.add_argument("--workers", type=int, default=1, help="Parallel workers for steps 1 and 3")
    parser.add_argument("--batch-size", type=int, default=8, help="Factors per LLM call in step 4")
    parser.add_argument("--stop-on-error", action="store_true", help="Stop pipeline if any step fails")
    args = parser.parse_args()

    # Ensure output root exists
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    log.info(f"Pipeline starting: steps={args.steps}, tickers={args.tickers or 'all'}")

    tickers = [t.upper() for t in args.tickers] if args.tickers else None

    results = {}
    for step_num in sorted(args.steps):
        success = run_step(
            step_num,
            tickers=tickers,
            max_filings=args.max_filings,
            workers=args.workers,
            batch_size=args.batch_size,
        )
        results[step_num] = success

        if not success and args.stop_on_error:
            log.error(f"Stopping pipeline due to step {step_num} failure")
            break

    # Summary
    log.info("=" * 60)
    log.info("PIPELINE SUMMARY")
    for step_num, success in results.items():
        status = "OK" if success else "FAILED"
        log.info(f"  Step {step_num}: {status}")

    all_ok = all(results.values())
    if all_ok:
        log.info("Pipeline completed successfully")
    else:
        log.warning("Pipeline completed with errors")
        sys.exit(1)


if __name__ == "__main__":
    main()
