"""
Configuration for the factor extraction pipeline.
"""

from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent          # fillings/
DATA_ROOT = PROJECT_ROOT / "Data"                              # raw SEC HTMLs
ACTUAL_CODE_ROOT = Path(__file__).resolve().parent              # Actual_code/
OUTPUT_ROOT = ACTUAL_CODE_ROOT / "output"

EXTRACTED_SECTIONS_DIR = OUTPUT_ROOT / "extracted_sections"
SUBSECTIONS_DIR = OUTPUT_ROOT / "subsections"
FACTORS_DIR = OUTPUT_ROOT / "factors"
FACTORS_SCORED_DIR = OUTPUT_ROOT / "factors_scored"

QUESTIONS_PATH = ACTUAL_CODE_ROOT / "questions.json"
TICKER_MAPPING_PATH = ACTUAL_CODE_ROOT / "ticker_mapping.json"

# ── LLM Provider ──────────────────────────────────────────────────────────────
# "accre" → Qwen via vLLM on ACCRE
# "openai" → OpenAI API (for local testing)
PROVIDER = "accre"

# ACCRE (vLLM) settings
ACCRE_BASE_URL = "http://127.0.0.1:8000/v1"
ACCRE_API_KEY = "local"
ACCRE_MODEL = "Qwen/Qwen3-30B-A3B-Instruct"

# OpenAI settings (fallback for local testing)
OPENAI_BASE_URL = "https://api.openai.com/v1"
OPENAI_API_KEY = None  # set via OPENAI_API_KEY env var
OPENAI_MODEL = "gpt-4o-2024-08-06"

# ── LLM Parameters ────────────────────────────────────────────────────────────
TEMPERATURE = 0.0
MAX_RETRIES = 5
RETRY_BASE_DELAY = 2.0        # seconds, exponential backoff base
REQUEST_TIMEOUT = 120          # seconds per LLM call

# ── Concurrency ───────────────────────────────────────────────────────────────
MAX_WORKERS_FILINGS = 4        # parallel filings being processed
MAX_IN_FLIGHT_LLM = 3          # max concurrent LLM calls (global semaphore)

# ── Extraction ─────────────────────────────────────────────────────────────────
# 10-K section mapping
SECTIONS_10K = {
    "mda": "Item 7",
    "risk_factors": "Item 1A",
}
# 10-Q section mapping
SECTIONS_10Q = {
    "mda": "Item 2",
    "risk_factors": "Item 1A",
}

# Section that follows each target (used to find end boundary)
NEXT_SECTION_10K = {
    "Item 7": "Item 7A",
    "Item 1A": "Item 1B",
}
NEXT_SECTION_10Q = {
    "Item 2": "Item 3",
    "Item 1A": "Item 2",
}
