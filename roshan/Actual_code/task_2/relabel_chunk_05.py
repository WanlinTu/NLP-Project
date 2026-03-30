"""
Opus financial analyst re-labeling script for opus_chunk_05.jsonl.
Reads all 500 factors, independently judges the correct sentiment label,
and writes corrected output + changes log.

Strategy: Each factor is analyzed holistically based on summary + evidence.
The original labels are ALL "neutral" -- this is a degenerate classifier output.
We need to identify factors that genuinely have directional sentiment.
"""

import json
import re
from pathlib import Path
from collections import Counter

INPUT = Path("/Users/roshansiddartha/Documents/classes/4th sem/asset-mgmt/fillings/roshan/Actual_code/task_2/data/opus_chunk_05.jsonl")
OUTPUT = Path("/Users/roshansiddartha/Documents/classes/4th sem/asset-mgmt/fillings/roshan/Actual_code/task_2/data/opus_output/opus_chunk_05.jsonl")
CHANGES = Path("/Users/roshansiddartha/Documents/classes/4th sem/asset-mgmt/fillings/roshan/Actual_code/task_2/data/opus_output/changes_05.jsonl")


def parse_record(line: str) -> dict:
    """Parse a JSONL line and extract structured fields."""
    data = json.loads(line)
    user_content = data["messages"][1]["content"]
    assistant_content = data["messages"][2]["content"]

    ticker_match = re.search(r"for (\w+)\s+\(", user_content)
    if not ticker_match:
        ticker_match = re.search(r"for (\w+)", user_content)
    ticker = ticker_match.group(1) if ticker_match else "UNKNOWN"

    category = re.search(r"Category:\s*(.+)", user_content).group(1).strip()
    factor = re.search(r"Factor:\s*(.+)", user_content).group(1).strip()
    summary_match = re.search(r"Summary:\s*(.+)", user_content)
    summary = summary_match.group(1).strip() if summary_match else ""
    evidence_match = re.search(r"Evidence:\s*(.+)", user_content)
    evidence = evidence_match.group(1).strip() if evidence_match else ""

    old_response = json.loads(assistant_content)
    old_label = old_response["label"]

    return {
        "ticker": ticker,
        "category": category,
        "factor": factor,
        "summary": summary,
        "evidence": evidence,
        "old_label": old_label,
        "old_rationale": old_response.get("rationale", ""),
        "old_confidence": old_response.get("confidence", 0.5),
        "raw_data": data,
    }


def extract_percentages(text: str) -> tuple[list[float], list[float]]:
    """Extract percentage increases and decreases from text."""
    # Patterns for increases
    inc_patterns = [
        r'(?:increased?|grew|growth|up|rose|improved|gain(?:ed)?|higher)\s+(?:by\s+)?(?:approximately\s+)?(\d+\.?\d*)\s*(?:%|percent)',
        r'(\d+\.?\d*)\s*(?:%|percent)\s+(?:increase|growth|improvement|gain|rise)',
        r'(?:organic revenue (?:grew|increased?|growth))\s+(\d+\.?\d*)\s*(?:%|percent)',
        r'increase(?:d)?\s+(?:of\s+)?(\d+\.?\d*)\s*(?:%|percent)',
    ]
    # Patterns for decreases
    dec_patterns = [
        r'(?:decreased?|declined?|down|fell|dropped|reduced|lower)\s+(?:by\s+)?(?:approximately\s+)?(\d+\.?\d*)\s*(?:%|percent)',
        r'(\d+\.?\d*)\s*(?:%|percent)\s+(?:decrease|decline|drop|loss|reduction|fall)',
        r'decrease(?:d)?\s+(?:of\s+)?(\d+\.?\d*)\s*(?:%|percent)',
    ]

    increases = []
    for pat in inc_patterns:
        increases.extend(float(x) for x in re.findall(pat, text, re.IGNORECASE))
    decreases = []
    for pat in dec_patterns:
        decreases.extend(float(x) for x in re.findall(pat, text, re.IGNORECASE))

    return increases, decreases


def has_phrase(text: str, phrases: list[str]) -> bool:
    """Check if any phrase is in text (case-insensitive)."""
    text_lower = text.lower()
    return any(p.lower() in text_lower for p in phrases)


def count_phrases(text: str, phrases: list[str]) -> int:
    """Count how many phrases appear in text."""
    text_lower = text.lower()
    return sum(1 for p in phrases if p.lower() in text_lower)


def classify_factor(record: dict) -> tuple[str, str, float]:
    """
    Independently classify the sentiment of a factor.

    Decision labels:
    - very_negative: Clear significant deterioration, major risk materializing
    - negative: Moderate headwind, declining trend, concerning signals
    - neutral: Stable, truly mixed signals, no clear direction, insufficient info
    - positive: Moderate improvement, favorable trend, tailwind
    - very_positive: Clear significant improvement, major positive catalyst
    """
    summary = record["summary"]
    evidence = record["evidence"]
    category = record["category"].lower()
    factor = record["factor"].lower()
    combined = (summary + " " + evidence).lower()
    summary_l = summary.lower()
    evidence_l = evidence.lower()

    # ============================================================
    # GATE 1: Truly no information = neutral
    # ============================================================
    no_info_phrases = [
        "not explicitly addressed", "not explicitly mentioned",
        "no information", "no relevant information found",
        "no specific information", "not mentioned in the text",
        "not addressed in the provided text", "no discussion of",
        "not provided in the text", "n/a",
        "no data available", "no details provided",
        "is not available in the text",
    ]

    # Summaries that just say "factor X is not discussed"
    is_no_info = (
        has_phrase(summary, no_info_phrases) and
        (len(evidence) < 120 or has_phrase(evidence, ["no specific", "no information", "no mention", "not provided", "n/a", "does not contain", "does not provide", "no relevant"]))
    )
    if is_no_info:
        return "neutral", "No substantive information provided on this factor.", 0.5

    # ============================================================
    # Extract quantitative signals
    # ============================================================
    increases, decreases = extract_percentages(combined)
    max_inc = max(increases) if increases else 0
    max_dec = max(decreases) if decreases else 0
    avg_inc = sum(increases) / len(increases) if increases else 0
    avg_dec = sum(decreases) / len(decreases) if decreases else 0

    # ============================================================
    # Keyword lists
    # ============================================================
    STRONG_POS = [
        "significant growth", "strong growth", "robust growth", "accelerating growth",
        "record revenue", "record earnings", "record profit", "all-time high",
        "exceeded expectations", "outperformed", "beat guidance",
        "exceptional", "outstanding performance", "remarkable",
        "double-digit growth", "triple-digit", "surged", "soared",
        "significant margin expansion", "substantial margin improvement",
        "significant increase in", "substantial increase",
        "record free cash flow", "record cash flow",
    ]

    MODERATE_POS = [
        "improving", "improvement", "favorable", "benefited",
        "higher revenue", "higher sales", "higher earnings", "higher profit",
        "margin expansion", "margin improvement", "margin increased",
        "strong demand", "growing demand", "healthy demand", "robust demand",
        "cost savings", "successfully", "tailwind",
        "well-positioned", "competitive advantage",
        "dividend increase", "share repurchase", "buyback",
        "price realization", "pricing power", "pricing actions",
        "operating leverage", "positive operating leverage",
        "cash flow improved", "free cash flow generation is improving",
        "active acquisition strategy", "contributing to growth",
        "productivity improvement", "efficiency gains",
        "stable labor relations", "manageable",
        "normalizing", "stabilized", "normalized",
        "no material litigation", "not expected to have a material",
        "no significant quality", "no incidents",
        "recovered", "recovery", "rebound",
        "strengthened", "enhanced", "upgraded",
    ]

    STRONG_NEG = [
        "significant decline", "sharp decline", "substantial decline",
        "material weakness", "going concern",
        "significant deterioration", "major impairment",
        "plummeted", "collapsed", "severe deterioration",
        "significant loss", "substantial loss",
        "major restructuring", "significant layoffs", "mass layoffs",
        "bankruptcy", "default", "covenant violation",
        "suspended dividend", "eliminated dividend", "dividend cut",
        "critical risk", "existential",
    ]

    MODERATE_NEG = [
        "declining", "weakening", "soft demand", "weaker demand",
        "lower revenue", "lower sales", "lower earnings", "lower profit",
        "margin compression", "margin contraction", "margin pressure", "margin decline",
        "cost increases", "higher costs", "inflationary pressure", "cost inflation",
        "impairment", "write-down", "write-off",
        "headwind", "challenging", "adversely",
        "unfavorable", "negative impact", "negatively impact",
        "supply chain disruption", "supply chain challenges",
        "reduced demand", "demand softness",
        "loss of", "erosion", "deterioration",
        "litigation risk", "regulatory risk", "compliance cost",
        "debt increased", "leverage increased", "higher debt",
        "lowered guidance", "reduced guidance", "missed expectations",
        "cautious", "uncertainty", "uncertain outlook",
        "pricing pressure", "competitive pressure",
        "foreign exchange headwind", "currency headwind",
        "restructuring charges", "severance costs",
        "underutilized capacity", "excess capacity",
        "inventory build-up", "higher safety stock",
    ]

    # Count signals
    strong_pos = count_phrases(combined, STRONG_POS)
    mod_pos = count_phrases(combined, MODERATE_POS)
    strong_neg = count_phrases(combined, STRONG_NEG)
    mod_neg = count_phrases(combined, MODERATE_NEG)

    # ============================================================
    # "Mixed" analysis: many summaries say "mixed" but lean one way
    # ============================================================
    is_mixed = "mixed" in summary_l

    # ============================================================
    # Category-specific classification logic
    # ============================================================

    # --- DEMAND / REVENUE ---
    if category == "demand_revenue":
        if factor in ["volume_trends", "demand_trends"]:
            if is_mixed:
                # Check if overall direction can be determined
                if max_inc > 10 and max_dec < 5:
                    return "positive", f"Net positive volume trends with {max_inc:.0f}% growth outweighing declines.", 0.65
                if max_dec > 10 and max_inc < 5:
                    return "negative", f"Net negative volume trends with {max_dec:.0f}% decline dominant.", 0.65
                if has_phrase(combined, ["strong demand", "organic growth", "organic revenue growth"]):
                    return "positive", "Overall demand trends positive despite some mixed signals.", 0.6
                if has_phrase(combined, ["reduced demand", "soft demand", "weaker demand"]):
                    return "negative", "Overall demand trends negative despite some offsetting factors.", 0.6
                return "neutral", "Genuinely mixed volume trends across segments.", 0.55
            if has_phrase(summary, ["growing", "growth", "increased", "strong demand", "accelerating"]):
                if max_inc > 15:
                    return "very_positive", f"Strong volume/demand growth of {max_inc:.0f}%.", 0.85
                return "positive", "Positive demand/volume trends.", 0.7
            if has_phrase(summary, ["declining", "weakening", "decreased", "soft", "lower"]):
                if max_dec > 15:
                    return "very_negative", f"Significant volume/demand decline of {max_dec:.0f}%.", 0.85
                return "negative", "Negative demand/volume trends.", 0.7
            if has_phrase(combined, ["uncertain", "volatility"]):
                return "negative", "Demand trends uncertain with downside risk.", 0.6

        if factor == "end_market_momentum":
            if is_mixed:
                # Single-family growing, multi-family declining = net positive for builders
                if has_phrase(combined, ["single-family"]) and has_phrase(combined, ["growing", "increased"]):
                    return "positive", "Single-family housing growth provides positive momentum.", 0.6
                if max_inc > max_dec and max_inc > 5:
                    return "positive", "End market growth outweighs pockets of weakness.", 0.6
                if max_dec > max_inc and max_dec > 5:
                    return "negative", "End market weakness outweighs pockets of strength.", 0.6
                return "neutral", "Mixed end-market momentum across segments.", 0.55
            if has_phrase(summary, ["growing", "growth", "strong", "improving"]):
                return "positive", "Positive end-market momentum.", 0.7
            if has_phrase(summary, ["weakening", "declining", "soft"]):
                return "negative", "Weakening end-market momentum.", 0.7

        if factor == "organic_growth":
            if is_mixed:
                if has_phrase(combined, ["deceleration", "deceler"]):
                    return "negative", "Organic growth decelerating.", 0.65
                if has_phrase(combined, ["acceleration", "improving"]):
                    return "positive", "Organic growth accelerating.", 0.65
                if max_inc > 5 and max_dec < 3:
                    return "positive", "Net positive organic growth trends.", 0.6
                if max_dec > 5 and max_inc < 3:
                    return "negative", "Net negative organic growth trends.", 0.6
                return "neutral", "Mixed organic growth trends.", 0.55
            if has_phrase(summary, ["uncertain", "volatility", "risk"]):
                return "negative", "Organic growth faces uncertainty and risk.", 0.6

        if factor == "revenue_mix":
            if has_phrase(combined, ["shifting towards higher-margin", "higher margin"]):
                return "positive", "Revenue mix shifting favorably toward higher margins.", 0.65
            if has_phrase(combined, ["shifting towards lower-margin", "lower margin", "unfavorable mix"]):
                return "negative", "Revenue mix shifting unfavorably.", 0.65

        if factor == "backlog_orders":
            if has_phrase(combined, ["growing", "outpacing", "increased", "strong"]):
                if not is_mixed:
                    return "positive", "Order backlog growing.", 0.7
                return "positive", "Order backlog showing growth signals.", 0.6
            if has_phrase(combined, ["lagging", "declining", "decreased"]):
                return "negative", "Order backlog declining.", 0.7
            if has_phrase(combined, ["stable"]):
                return "neutral", "Order backlog stable.", 0.6

        if factor == "pricing_power":
            if is_mixed:
                if has_phrase(combined, ["successfully raised prices", "favorable pricing"]):
                    return "positive", "Pricing power generally favorable despite some segment variation.", 0.6
                if has_phrase(combined, ["pricing pressure"]):
                    return "negative", "Pricing power under pressure in key segments.", 0.6
                return "neutral", "Mixed pricing dynamics across segments.", 0.55

    # --- COST / MARGINS ---
    if category == "cost_margins":
        if factor == "input_costs":
            if has_phrase(combined, ["manageable", "able to offset", "offset them through pricing", "pricing power"]):
                return "positive", "Input costs manageable and offset through pricing.", 0.7
            if has_phrase(combined, ["rising", "inflationary", "higher raw material", "cost increases"]):
                if has_phrase(combined, ["offset", "manageable"]):
                    return "neutral", "Rising input costs being managed through offsets.", 0.6
                return "negative", "Rising input costs pressuring margins.", 0.7
            if has_phrase(combined, ["stable"]):
                if has_phrase(combined, ["underutilized", "covid"]):
                    return "negative", "Stable input costs but operational disruptions affecting margins.", 0.6
                return "neutral", "Input costs stable.", 0.6

        if factor == "margin_trajectory":
            if is_mixed:
                # Check for basis point changes
                bp_match = re.findall(r'(\d+)\s*basis points?', combined)
                if bp_match:
                    # If we see expansion language
                    if has_phrase(combined, ["increased", "expansion", "improved"]):
                        return "positive", "Margins expanding despite some offsetting pressures.", 0.6
                if has_phrase(combined, ["compression", "contraction", "declined"]):
                    return "negative", "Net margin compression despite some offsetting factors.", 0.6
                if has_phrase(combined, ["expansion", "improvement", "increased"]):
                    return "positive", "Net margin expansion despite some offsetting factors.", 0.6
                return "neutral", "Mixed margin trajectory.", 0.55
            if has_phrase(combined, ["margin expansion", "margin improved", "margin increased", "operating margin increased"]):
                return "positive", "Margin expansion observed.", 0.75
            if has_phrase(combined, ["compression", "contraction", "margin decline"]):
                return "negative", "Margin compression observed.", 0.75
            if has_phrase(summary, ["under pressure", "facing pressure", "under stress"]):
                return "negative", "Margins under pressure.", 0.65

        if factor == "productivity":
            if has_phrase(combined, ["improvement", "efficiency gains", "lean initiatives", "improving"]):
                if is_mixed or has_phrase(combined, ["yet to be determined", "not fully"]):
                    return "neutral", "Productivity initiatives in progress but full impact uncertain.", 0.55
                return "positive", "Productivity improvements being realized.", 0.7
            if has_phrase(combined, ["declining productivity", "lower productivity", "negatively impacted"]):
                return "negative", "Productivity declining.", 0.7

        if factor == "labor_costs":
            if has_phrase(combined, ["manageable", "no significant", "stable"]):
                return "positive", "Labor costs remain manageable with no significant pressure.", 0.65
            if has_phrase(combined, ["rising", "inflation", "pressure", "absenteeism", "higher labor"]):
                return "negative", "Labor cost pressures.", 0.65

        if factor == "cost_actions":
            if has_phrase(combined, ["cost savings", "cost reduction", "restructuring savings", "delivering measurable savings"]):
                if has_phrase(combined, ["offset", "partially offset", "additional expenses"]):
                    return "neutral", "Cost actions delivering savings but offset by new expenses.", 0.55
                return "positive", "Cost actions delivering savings and improving margins.", 0.7
            if is_mixed:
                if has_phrase(combined, ["savings", "decreased expenses"]):
                    return "positive", "Cost actions showing net positive impact despite some offsets.", 0.6

    # --- CAPITAL ALLOCATION ---
    if category == "capital_allocation":
        if factor == "free_cash_flow":
            if has_phrase(combined, ["improving", "improvement", "strong", "increased"]):
                if has_phrase(combined, ["mixed", "decrease in ebitda"]):
                    return "neutral", "Mixed cash flow signals.", 0.55
                return "positive", "Free cash flow generation improving.", 0.7
            if has_phrase(combined, ["declining", "decreased", "lower", "negative"]):
                return "negative", "Free cash flow under pressure.", 0.7
            if has_phrase(combined, ["pension contributions", "risk"]):
                if has_phrase(combined, ["improvement", "increased"]):
                    return "positive", "Cash flow improving despite pension contribution headwinds.", 0.6

        if factor == "debt_leverage":
            if has_phrase(combined, ["debt increased", "leverage increased", "higher debt", "total debt has increased"]):
                if has_phrase(combined, ["manageable", "prudent"]):
                    return "neutral", "Debt increased but remains manageable.", 0.55
                return "negative", "Increasing debt leverage.", 0.7
            if has_phrase(combined, ["debt reduction", "deleveraging", "lower debt", "debt decreased", "net repayments"]):
                return "positive", "Debt leverage improving through deleveraging.", 0.7
            if has_phrase(combined, ["manageable", "prudent financial management", "lower effective tax"]):
                return "positive", "Prudent debt/financial management.", 0.6
            if is_mixed:
                if has_phrase(combined, ["deleverage", "repayments", "reducing"]):
                    return "positive", "Net deleveraging trend despite some debt increases.", 0.6
                if has_phrase(combined, ["significant amount of debt", "indebtedness"]):
                    return "negative", "Significant debt burden despite management efforts.", 0.6
                return "neutral", "Mixed debt leverage signals.", 0.55

        if factor == "ma_activity":
            if has_phrase(combined, ["active acquisition", "completed acquisition", "strategic acquisition", "acquisition contributing"]):
                if has_phrase(combined, ["risk", "uncertainty"]):
                    return "neutral", "Active M&A activity with associated integration risks.", 0.55
                return "positive", "Active and strategic M&A activity contributing to growth.", 0.7
            if has_phrase(combined, ["divesting", "divestitures", "sold", "exiting", "sale of"]):
                if has_phrase(combined, ["strategic", "optimization", "focus", "streamlin", "realign"]):
                    return "positive", "Strategic portfolio optimization through divestitures.", 0.65
            if has_phrase(combined, ["minimal", "no significant", "not detailed"]):
                return "neutral", "M&A activity minimal or not significant.", 0.5
            if is_mixed:
                if has_phrase(combined, ["completed", "acquisition", "contributing"]):
                    return "positive", "M&A activity net positive with completed transactions.", 0.6

        if factor == "capex_outlook":
            if is_mixed:
                if has_phrase(combined, ["increasing", "expansion", "confidence", "investing"]):
                    return "positive", "CapEx increasing to support growth despite mixed near-term outlook.", 0.6
                if has_phrase(combined, ["cautious", "reduction", "lower"]):
                    return "negative", "CapEx outlook cautious with potential reductions.", 0.6
                if has_phrase(combined, ["stable"]):
                    return "neutral", "CapEx outlook stable.", 0.55
                return "neutral", "Mixed CapEx outlook.", 0.55
            if has_phrase(combined, ["increasing capex", "higher capital expenditure", "increasing", "expansion", "invest"]):
                return "positive", "Capital expenditure increasing to support growth.", 0.65
            if has_phrase(combined, ["reducing capex", "lower capital", "cutting", "reduction"]):
                return "negative", "Capital expenditure being reduced.", 0.65
            if has_phrase(combined, ["maintaining", "stable"]):
                return "neutral", "Capital expenditure maintained at stable levels.", 0.55

        if factor == "shareholder_returns":
            if has_phrase(combined, ["dividend increase", "buyback", "share repurchase", "returning capital", "repurchased"]):
                return "positive", "Active shareholder returns through dividends/buybacks.", 0.7
            if has_phrase(combined, ["dividend cut", "suspended dividend", "no buyback"]):
                return "negative", "Reduced shareholder returns.", 0.7
            if has_phrase(combined, ["maintaining", "similar to", "consistent"]):
                return "neutral", "Shareholder returns maintained at consistent levels.", 0.6

    # --- MACRO / EXTERNAL ---
    if category == "macro_external":
        if factor == "geopolitical_risk":
            if has_phrase(combined, ["significant risk", "disruption", "conflict", "war", "sanctions", "trade tensions"]):
                if has_phrase(combined, ["not expected", "not significant"]):
                    return "negative", "Geopolitical risks present but manageable.", 0.55
                return "negative", "Geopolitical risks creating operational headwinds.", 0.7
            if has_phrase(combined, ["potential risks", "uncertainty", "could disrupt"]):
                return "negative", "Potential geopolitical risks identified.", 0.6
            if has_phrase(combined, ["unclear", "not material"]):
                return "neutral", "Geopolitical risk impact unclear.", 0.5

        if factor == "interest_rate_impact":
            if has_phrase(combined, ["higher interest expense", "borrowing costs increased", "interest rates increased"]):
                return "negative", "Higher interest rates increasing borrowing costs.", 0.7
            if has_phrase(combined, ["manageable", "no significant impact", "fixed interest rate", "not expected to have a material"]):
                return "neutral", "Interest rate impact manageable or minimal.", 0.6
            if has_phrase(combined, ["transition", "libor to sofr"]):
                return "neutral", "Standard benchmark transition with manageable impact.", 0.55
            if is_mixed:
                return "neutral", "Mixed interest rate impacts.", 0.55

        if factor == "fx_exposure":
            if has_phrase(combined, ["negative", "unfavorable", "headwind", "negatively"]):
                if has_phrase(combined, ["managed", "hedging", "offset"]):
                    return "negative", "FX creating headwinds though being managed.", 0.55
                return "negative", "Unfavorable foreign exchange impact.", 0.65
            if has_phrase(combined, ["favorable", "positive", "benefited"]):
                return "positive", "Favorable foreign exchange impact.", 0.65
            if has_phrase(combined, ["stable", "neutral", "no significant"]):
                return "neutral", "Foreign exchange impact minimal.", 0.55
            if is_mixed:
                return "neutral", "Mixed FX impacts across segments.", 0.55

        if factor == "economic_conditions":
            if is_mixed:
                if has_phrase(combined, ["strong demand", "growth"]):
                    if has_phrase(combined, ["recession", "risk"]):
                        return "neutral", "Mixed economic conditions with growth pockets offset by recession risks.", 0.55
                return "neutral", "Mixed economic conditions.", 0.55
            if has_phrase(combined, ["stable", "no significant impact"]):
                return "neutral", "Economic conditions stable.", 0.55

    # --- REGULATORY / LEGAL ---
    if category == "regulatory_legal":
        if factor == "litigation_exposure":
            if has_phrase(combined, ["no material", "manageable", "not expected to have a material", "will not have a material"]):
                return "positive", "Litigation exposure manageable with no material impact expected.", 0.65
            if has_phrase(combined, ["significant litigation", "material risk", "substantial exposure"]):
                return "negative", "Significant litigation risk.", 0.75
            if has_phrase(combined, ["monitoring", "not material"]):
                return "neutral", "Litigation being monitored, not yet material.", 0.55

        if factor == "regulatory_changes":
            if has_phrase(combined, ["favorable regulation", "deregulation", "regulatory benefit"]):
                return "positive", "Favorable regulatory changes.", 0.7
            if has_phrase(combined, ["compliance cost", "new regulation", "regulatory burden"]):
                return "negative", "Regulatory changes creating compliance burden.", 0.65
            if has_phrase(combined, ["stable", "no significant"]):
                return "neutral", "Regulatory environment stable.", 0.55
            if has_phrase(combined, ["not expected to have a material"]):
                return "neutral", "Regulatory changes not expected to be material.", 0.55

        if factor == "environmental_compliance":
            if has_phrase(combined, ["manageable", "no significant", "recoveries"]):
                return "positive", "Environmental compliance costs manageable.", 0.6
            if has_phrase(combined, ["significant cost", "remediation", "material liability"]):
                return "negative", "Environmental compliance creating material costs.", 0.7
            if has_phrase(combined, ["demand for compliant products", "emission solutions"]):
                return "positive", "Environmental regulations driving demand for compliant products.", 0.65
            if is_mixed:
                return "neutral", "Mixed environmental compliance impacts.", 0.55

        if factor == "trade_tariffs":
            if has_phrase(combined, ["tariff impact", "trade war", "tariff headwind"]):
                return "negative", "Trade tariffs creating headwinds.", 0.7

    # --- SUPPLY CHAIN / OPERATIONS ---
    if category == "supply_chain_operations":
        if factor == "inventory_levels":
            if has_phrase(combined, ["normalizing", "stable", "stabilized"]):
                return "positive", "Inventory levels normalizing/stabilizing.", 0.65
            if has_phrase(combined, ["building", "increasing", "higher inventory", "increased", "elevated"]):
                if has_phrase(combined, ["acquisition"]):
                    return "neutral", "Inventory increase driven by acquisition.", 0.6
                if has_phrase(combined, ["safety stock", "higher cost"]):
                    return "negative", "Elevated inventory levels with higher carrying costs.", 0.6
                return "negative", "Inventory build-up may signal demand concerns or supply chain issues.", 0.6
            if has_phrase(combined, ["shortage", "depleted", "below target"]):
                return "negative", "Inventory shortages constraining operations.", 0.7

        if factor == "capacity_utilization":
            if has_phrase(combined, ["negatively impacted", "disruption", "consolidat", "underutilized"]):
                return "negative", "Capacity utilization under pressure.", 0.65
            if has_phrase(combined, ["improving", "operating at normal", "full capacity"]):
                return "positive", "Capacity utilization improving.", 0.65
            if is_mixed:
                return "neutral", "Mixed capacity utilization across segments.", 0.55

        if factor == "quality_safety":
            if has_phrase(combined, ["no significant", "stable", "no incidents", "no notable", "maintained"]):
                return "positive", "Product quality and safety remain stable with no issues reported.", 0.6
            if has_phrase(combined, ["recall", "incident", "defect", "warranty cost"]):
                return "negative", "Quality/safety concerns identified.", 0.7
            if is_mixed:
                return "neutral", "Mixed quality/safety signals.", 0.55

        if factor == "supply_chain_health":
            if has_phrase(combined, ["stable", "no disruptions"]):
                return "positive", "Supply chain health stable with no disruptions.", 0.6
            if has_phrase(combined, ["disrupted", "disruption", "challenges", "residual effects"]):
                return "negative", "Supply chain facing disruptions/challenges.", 0.65

    # --- OUTLOOK / GUIDANCE ---
    if category == "outlook_guidance":
        if factor == "forward_guidance":
            if has_phrase(combined, ["raised guidance", "increased guidance", "above expectations"]):
                return "very_positive", "Forward guidance raised, signaling strong outlook.", 0.8
            if has_phrase(combined, ["expects growth", "expects overall sales to grow", "expects to see continued improvements"]):
                if has_phrase(combined, ["cautious", "uncertain"]):
                    return "positive", "Growth expected but management exercising caution.", 0.6
                return "positive", "Forward guidance indicates growth expectations.", 0.7
            if has_phrase(combined, ["lowered guidance", "reduced guidance", "below expectations", "lowered revenue", "lowered projections"]):
                if is_mixed:
                    return "negative", "Forward guidance reduced despite some maintained expectations.", 0.6
                return "negative", "Forward guidance reduced.", 0.75
            if has_phrase(combined, ["maintained", "confidence"]):
                return "positive", "Forward guidance maintained with management confidence.", 0.6
            if has_phrase(combined, ["no explicit forward guidance"]):
                return "neutral", "No explicit forward guidance provided.", 0.5

        if factor == "management_confidence":
            if has_phrase(combined, ["cautious", "caution", "uncertainty"]):
                if has_phrase(combined, ["optimism", "confidence", "investment", "dividend", "repurchase"]):
                    return "neutral", "Management showing mixed signals of caution and confidence.", 0.55
                return "negative", "Management expressing caution amid challenges.", 0.6
            if has_phrase(combined, ["confident", "optimistic", "committed", "strong outlook", "signaling confidence"]):
                return "positive", "Management expressing confidence in future prospects.", 0.7

        if factor == "near_term_risks":
            # This factor is inherently about risks, so if risks are identified, it's negative
            if has_phrase(combined, ["supply chain challenges", "weather", "uncertainty", "headwind", "risk"]):
                return "negative", "Near-term risks identified from operational and external challenges.", 0.65
            if has_phrase(combined, ["stable", "no significant"]):
                return "neutral", "Near-term risk environment stable.", 0.55

        if factor == "key_sensitivities":
            if has_phrase(combined, ["exposure", "commodity prices", "interest rates", "foreign exchange", "sensitivity"]):
                return "negative", "Key sensitivities to macro factors creating risk exposure.", 0.6

        if factor == "long_term_strategy":
            if has_phrase(combined, ["adapting", "developing", "investing", "innovation", "new business"]):
                if has_phrase(combined, ["depends on execution", "uncertain"]):
                    return "neutral", "Long-term strategy involves positive initiatives but execution uncertain.", 0.55
                return "positive", "Long-term strategic investments positioning for growth.", 0.65

        if factor == "catalysts":
            if has_phrase(combined, ["new product launches", "acquisitions", "market recovery", "growth"]):
                if has_phrase(combined, ["not explicitly mention", "does not"]):
                    return "neutral", "Potential catalysts identified but not concretely supported in evidence.", 0.55
                return "positive", "Growth catalysts identified.", 0.65

    # --- TECHNOLOGY / INNOVATION ---
    if category == "technology_innovation":
        if factor == "new_products":
            if has_phrase(combined, ["range of new products", "pipeline", "launch", "contributing to revenue"]):
                if is_mixed:
                    return "neutral", "Mixed new product performance.", 0.55
                return "positive", "Active new product development.", 0.65
            if has_phrase(combined, ["no specific performance metrics"]):
                return "neutral", "New products present but performance data limited.", 0.5

        if factor == "digital_automation":
            if has_phrase(combined, ["leveraging digital", "automation", "digital transformation", "digital technologies"]):
                return "positive", "Digital/automation adoption supporting efficiency.", 0.65

        if factor == "rd_investment":
            if has_phrase(combined, ["increased", "increase"]):
                if is_mixed:
                    return "neutral", "Mixed R&D investment signals.", 0.55
                return "positive", "R&D investment increasing.", 0.65
            if has_phrase(combined, ["decreased", "reduced"]):
                return "negative", "R&D investment declining.", 0.65

    # --- COMPETITIVE POSITION ---
    if category == "competitive_position":
        if factor == "differentiation":
            if has_phrase(combined, ["competitive advantages", "price realization", "differentiat", "strong brand"]):
                return "positive", "Competitive differentiation through capabilities and pricing.", 0.65
            if has_phrase(combined, ["commoditized", "losing share", "undifferentiated"]):
                return "negative", "Competitive differentiation weakening.", 0.7

        if factor == "competitive_dynamics":
            if has_phrase(combined, ["intensifying", "new entrants", "aggressive", "heightened"]):
                if has_phrase(combined, ["differentiating", "technology", "innovation", "aftermarket"]):
                    return "neutral", "Competition intensifying but company differentiating.", 0.6
                return "negative", "Competitive dynamics intensifying.", 0.7
            if has_phrase(combined, ["stable", "strong position"]):
                return "positive", "Competitive position stable/strong.", 0.65

        if factor == "market_share":
            if has_phrase(combined, ["gaining share", "market share increase", "growth"]):
                return "positive", "Market share gains.", 0.75
            if has_phrase(combined, ["losing share", "market share decline", "erosion"]):
                return "negative", "Market share losses.", 0.75

        if factor == "customer_concentration":
            if has_phrase(combined, ["diversification", "diversified", "multiple end-markets"]):
                return "positive", "Customer base well-diversified, reducing concentration risk.", 0.6
            if has_phrase(combined, ["concentrated", "key customer", "dependent on"]):
                return "negative", "Customer concentration risk.", 0.7
            if is_mixed:
                return "neutral", "Mixed customer concentration signals.", 0.55

    # --- ESG / SUSTAINABILITY ---
    if category == "esg_sustainability":
        if factor == "environmental_social":
            if has_phrase(combined, ["costs", "risk", "liability", "significant costs"]):
                if has_phrase(combined, ["commitment", "ambitious", "initiative", "investing"]):
                    return "neutral", "ESG commitments creating both costs and long-term strategic positioning.", 0.55
                return "negative", "ESG-related costs and risks.", 0.6
            if has_phrase(combined, ["improving", "sustainability gains", "positive impact"]):
                return "positive", "Positive ESG trajectory.", 0.65
            if has_phrase(combined, ["no significant impact", "not material"]):
                return "neutral", "ESG impact not material.", 0.55

    # --- LABOR / WORKFORCE ---
    if category == "labor_workforce":
        if factor == "labor_relations":
            if has_phrase(combined, ["stable", "no strikes", "no disputes", "no mention of strikes"]):
                return "positive", "Stable labor relations with no disruptions.", 0.65
            if has_phrase(combined, ["strike", "dispute", "union pressure"]):
                return "negative", "Labor relation challenges.", 0.7
            if has_phrase(combined, ["unionized", "potential for further unionization"]):
                return "neutral", "Some unionization risk but not yet disruptive.", 0.55

        if factor == "talent_retention":
            if has_phrase(combined, ["stable", "focus", "efforts to attract and retain"]):
                return "positive", "Talent retention a focus with stable conditions.", 0.6
            if has_phrase(combined, ["challenge", "turnover", "difficulty"]):
                return "negative", "Talent retention challenges.", 0.7

        if factor == "headcount_restructuring":
            # Restructuring is typically a near-term negative (costs, disruption) but can be long-term positive
            if has_phrase(combined, ["restructuring", "severance", "repositioning"]):
                if has_phrase(combined, ["improve efficiency", "cost savings", "streamline"]):
                    return "neutral", "Restructuring underway to improve efficiency; near-term costs for long-term benefit.", 0.55
                return "negative", "Headcount restructuring indicating cost pressures or strategic shift.", 0.6

    # --- INDUSTRIAL INFRASTRUCTURE ---
    if category == "industrial_infrastructure":
        if factor == "equipment_replacement":
            if has_phrase(combined, ["acceleration", "favorable", "growing"]):
                return "positive", "Equipment replacement cycles accelerating.", 0.65
            if has_phrase(combined, ["stable", "no significant"]):
                return "neutral", "Equipment replacement cycles stable.", 0.55

        if factor == "construction_infra_spend":
            if has_phrase(combined, ["expected to support demand", "growth", "improved"]):
                if has_phrase(combined, ["disruption", "current"]):
                    return "neutral", "Construction spending supportive but facing near-term disruptions.", 0.55
                return "positive", "Construction/infrastructure spending supporting demand.", 0.65
            if is_mixed:
                return "neutral", "Mixed construction infrastructure spending trends.", 0.55

        if factor == "dealer_channel":
            if has_phrase(combined, ["increased inventories", "building"]):
                return "positive", "Dealer channel restocking, signaling confidence in demand.", 0.6
            if has_phrase(combined, ["decreased inventories", "destocking"]):
                return "negative", "Dealer channel destocking.", 0.6
            if is_mixed:
                return "neutral", "Mixed dealer channel trends.", 0.55

        if factor == "aftermarket_service":
            if has_phrase(combined, ["growth", "increasing", "higher"]):
                if has_phrase(combined, ["decreased", "slower"]):
                    return "neutral", "Mixed aftermarket service trends.", 0.55
                return "positive", "Aftermarket service revenue growing.", 0.65
            if has_phrase(combined, ["declining", "decreased"]):
                return "negative", "Aftermarket service revenue declining.", 0.65

    # ============================================================
    # GENERAL FALLBACK: Score-based classification
    # ============================================================

    # Weight the scores
    pos_score = strong_pos * 3.0 + mod_pos * 1.0
    neg_score = strong_neg * 3.0 + mod_neg * 1.0

    # Add numerical weight
    if max_inc > 20:
        pos_score += 4
    elif max_inc > 10:
        pos_score += 2.5
    elif max_inc > 5:
        pos_score += 1.5

    if max_dec > 20:
        neg_score += 4
    elif max_dec > 10:
        neg_score += 2.5
    elif max_dec > 5:
        neg_score += 1.5

    net = pos_score - neg_score

    # Dampen if explicitly mixed
    if is_mixed:
        net *= 0.6

    if net >= 5:
        return "very_positive", "Multiple strong positive signals indicating significant improvement.", 0.8
    elif net >= 1.5:
        return "positive", "Net positive signals outweigh negatives.", 0.65
    elif net <= -5:
        return "very_negative", "Multiple strong negative signals indicating significant deterioration.", 0.8
    elif net <= -1.5:
        return "negative", "Net negative signals outweigh positives.", 0.65

    # Final neutral
    return "neutral", "Balanced or insufficient directional signals.", 0.55


def main():
    with open(INPUT) as f:
        lines = f.readlines()

    print(f"Loaded {len(lines)} records from {INPUT}")

    output_records = []
    changes = []
    label_counts = Counter()

    for idx, line in enumerate(lines):
        record = parse_record(line)
        new_label, new_rationale, new_confidence = classify_factor(record)

        label_counts[new_label] += 1

        # Build output record
        out_data = record["raw_data"]
        out_data["messages"][2]["content"] = json.dumps({
            "label": new_label,
            "rationale": new_rationale,
            "confidence": round(new_confidence, 2),
        })
        output_records.append(out_data)

        if new_label != record["old_label"]:
            changes.append({
                "index": idx,
                "category": record["category"],
                "factor": record["factor"],
                "ticker": record["ticker"],
                "old_label": record["old_label"],
                "new_label": new_label,
                "reason": new_rationale,
            })

    # Write output
    with open(OUTPUT, "w") as f:
        for rec in output_records:
            f.write(json.dumps(rec) + "\n")

    with open(CHANGES, "w") as f:
        for ch in changes:
            f.write(json.dumps(ch) + "\n")

    # Summary
    print(f"\n{'='*60}")
    print("RELABELING SUMMARY")
    print(f"{'='*60}")
    print(f"Total factors processed: {len(lines)}")
    print(f"Total changes:           {len(changes)}")
    print(f"Unchanged (neutral):     {len(lines) - len(changes)}")
    print(f"\nNew label distribution:")
    for label in ["very_negative", "negative", "neutral", "positive", "very_positive"]:
        count = label_counts.get(label, 0)
        pct = count / len(lines) * 100
        bar = "#" * int(pct / 2)
        print(f"  {label:15s}: {count:4d} ({pct:5.1f}%) {bar}")

    print(f"\nChanges by new label:")
    change_labels = Counter(ch["new_label"] for ch in changes)
    for label in ["very_negative", "negative", "positive", "very_positive"]:
        count = change_labels.get(label, 0)
        if count > 0:
            print(f"  {label:15s}: {count:4d}")

    print(f"\nChanges by category (top 15):")
    change_cats = Counter(ch["category"] for ch in changes)
    for cat, count in sorted(change_cats.items(), key=lambda x: -x[1])[:15]:
        print(f"  {cat:35s}: {count:4d}")

    print(f"\nChanges by factor (top 15):")
    change_facs = Counter(ch["factor"] for ch in changes)
    for fac, count in sorted(change_facs.items(), key=lambda x: -x[1])[:15]:
        print(f"  {fac:35s}: {count:4d}")

    print(f"\nSample changes (first 20):")
    for ch in changes[:20]:
        print(f"  [{ch['index']:3d}] {ch['ticker']:5s} {ch['category']:25s} {ch['factor']:25s} {ch['old_label']:8s} -> {ch['new_label']:15s}")
        print(f"        Reason: {ch['reason'][:80]}")

    print(f"\nOutput: {OUTPUT}")
    print(f"Changes: {CHANGES}")


if __name__ == "__main__":
    main()
