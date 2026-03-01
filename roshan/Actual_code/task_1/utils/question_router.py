"""
Question router: maps subsection titles to relevant question subsets.

Uses keyword matching to determine which questions are most relevant
for a given subsection, reducing noise and improving LLM focus.
"""

import json
import re
from pathlib import Path
from typing import Optional

from config import QUESTIONS_PATH, TICKER_MAPPING_PATH

# ── Keyword → category mapping ────────────────────────────────────────────────
# Maps keywords found in subsection titles to question categories.

SUBSECTION_KEYWORDS: dict[str, list[str]] = {
    # MD&A subsection keywords → question categories
    "demand_revenue": [
        "revenue", "sales", "demand", "booking", "backlog", "order",
        "pricing", "passenger", "yield", "volume", "growth", "customer",
        "operating revenue", "net revenue", "commercial",
    ],
    "cost_margins": [
        "cost", "expense", "margin", "operating expense", "cogs",
        "salaries", "wages", "fuel", "material", "maintenance",
        "restructuring", "efficiency", "operating income", "profitability",
    ],
    "supply_chain_operations": [
        "supply chain", "manufacturing", "production", "capacity",
        "inventory", "logistics", "operations", "quality", "safety",
        "facilities", "utilization",
    ],
    "capital_allocation": [
        "liquidity", "capital", "debt", "cash flow", "financing",
        "credit", "borrowing", "dividend", "buyback", "repurchase",
        "balance sheet", "leverage", "investment", "capex",
        "acquisition", "divestiture",
    ],
    "competitive_position": [
        "competition", "competitive", "market share", "market position",
        "differentiation", "customer",
    ],
    "labor_workforce": [
        "employee", "workforce", "labor", "union", "headcount",
        "talent", "hiring", "personnel", "collective bargaining",
        "pilot", "strike",
    ],
    "regulatory_legal": [
        "regulation", "regulatory", "legal", "litigation",
        "government", "compliance", "environmental", "emission",
        "law", "legislation", "antitrust", "faa", "dot",
    ],
    "macro_external": [
        "economic", "economy", "inflation", "interest rate",
        "foreign exchange", "currency", "geopolitical", "macro",
        "recession", "gdp",
    ],
    "outlook_guidance": [
        "outlook", "guidance", "forward", "future", "expect",
        "forecast", "strategy", "strategic", "plan", "risk",
        "uncertainty", "trend", "catalyst",
    ],
    "technology_innovation": [
        "technology", "innovation", "digital", "automation",
        "r&d", "research", "development", "new product", "launch",
        "modernization",
    ],
    "esg_sustainability": [
        "esg", "sustainability", "climate", "environmental",
        "carbon", "emission", "renewable", "governance",
    ],
    # Sub-sector categories
    "airlines_transport": [
        "fuel", "load factor", "asm", "rpm", "rasm", "casm",
        "fleet", "aircraft", "route", "passenger", "cargo",
        "seat mile", "travel", "airline",
    ],
    "defense_government": [
        "defense", "military", "contract", "backlog", "program",
        "classified", "government", "dod", "pentagon", "f-35",
        "missile", "fighter", "weapon", "radar", "satellite",
        "international sales", "fms",
    ],
    "industrial_infrastructure": [
        "construction", "infrastructure", "equipment", "dealer",
        "aftermarket", "service revenue", "replacement cycle",
        "fleet age", "distributor", "rental",
    ],
}

# Broad fallback categories that apply to most subsections
FALLBACK_CATEGORIES = [
    "demand_revenue",
    "cost_margins",
    "outlook_guidance",
]


def load_questions() -> dict:
    """Load the questions taxonomy."""
    with open(QUESTIONS_PATH) as f:
        return json.load(f)


def load_ticker_subsector(ticker: str) -> str:
    """Get the sub-sector for a ticker."""
    with open(TICKER_MAPPING_PATH) as f:
        mapping = json.load(f)
    for sector, tickers in mapping.items():
        if ticker in tickers:
            return sector
    return "general"


def get_applicable_questions(ticker: str) -> dict[str, dict]:
    """
    Get all questions applicable to a ticker based on its sub-sector.

    Returns: {category_name: {key: question_text, ...}, ...}
    """
    questions = load_questions()
    subsector = load_ticker_subsector(ticker)

    applicable = {}
    for category_name, category_data in questions.items():
        cat_subsector = category_data["subsector"]
        if cat_subsector == "universal" or cat_subsector == subsector:
            applicable[category_name] = category_data["questions"]

    return applicable


def route_questions(
    subsection_name: str,
    subsection_text: str,
    all_questions: dict[str, dict],
) -> list[dict]:
    """
    Route relevant questions to a subsection based on keyword matching.

    Args:
        subsection_name: Title of the subsection
        subsection_text: First ~500 chars of subsection text (for context)
        all_questions: All applicable questions for this ticker

    Returns:
        List of {key, category, question} dicts for questions to ask.
    """
    # Combine subsection name and beginning of text for matching
    search_text = (subsection_name + " " + subsection_text[:500]).lower()

    # Score each category by keyword matches
    category_scores: dict[str, int] = {}
    for category, keywords in SUBSECTION_KEYWORDS.items():
        score = 0
        for kw in keywords:
            if kw.lower() in search_text:
                score += 1
        if score > 0:
            category_scores[category] = score

    # Select categories with matches
    matched_categories = set(category_scores.keys())

    # Always include fallback categories
    matched_categories.update(FALLBACK_CATEGORIES)

    # For risk factor subsections, also include regulatory and outlook
    if "risk" in subsection_name.lower():
        matched_categories.update(["regulatory_legal", "outlook_guidance", "macro_external"])

    # Build the question list from matched categories
    routed: list[dict] = []
    for category_name, questions in all_questions.items():
        if category_name in matched_categories:
            for key, question_text in questions.items():
                routed.append({
                    "key": key,
                    "category": category_name,
                    "question": question_text,
                })

    # If routing produced very few questions (< 10), add all questions
    if len(routed) < 10:
        routed = []
        for category_name, questions in all_questions.items():
            for key, question_text in questions.items():
                routed.append({
                    "key": key,
                    "category": category_name,
                    "question": question_text,
                })

    return routed
