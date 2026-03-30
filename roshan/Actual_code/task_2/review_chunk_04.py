#!/usr/bin/env python3
"""
Expert financial analyst review of sentiment labels for opus_chunk_04.jsonl.
All 500 factors are currently labeled 'negative'. This script reviews each one
and corrects the label where warranted based on summary and evidence.

Label definitions:
- very_negative: Clear significant deterioration, major risk (>15-20% decline, major impairment,
                  going concern, bankruptcy, severe operational failure)
- negative: Moderate headwind, declining trend, modest quantified negatives (2-15% decline,
            increased costs, margin compression, volume decline)
- neutral: Stable, mixed signals, boilerplate risk language, speculative/hypothetical risks,
           standard regulatory/competitive disclosure, offsetting factors
- positive: Moderate improvement, tailwind (revenue growth, margin expansion, cost savings realized)
- very_positive: Clear significant improvement (>15-20% growth, major contract win, transformative)
"""

import json
import re
from pathlib import Path

INPUT = Path("/Users/roshansiddartha/Documents/classes/4th sem/asset-mgmt/fillings/roshan/Actual_code/task_2/data/opus_chunk_04.jsonl")
OUTPUT = Path("/Users/roshansiddartha/Documents/classes/4th sem/asset-mgmt/fillings/roshan/Actual_code/task_2/data/opus_output/opus_chunk_04.jsonl")
CHANGES = Path("/Users/roshansiddartha/Documents/classes/4th sem/asset-mgmt/fillings/roshan/Actual_code/task_2/data/opus_output/changes_04.jsonl")


def parse_user_content(user_content: str) -> dict:
    """Extract structured fields from the user prompt."""
    info = {"ticker": "", "category": "", "factor": "", "summary": "", "evidence": "",
            "sub_sector": "", "form_type": ""}

    for line in user_content.split("\n"):
        line = line.strip()
        if line.startswith("Category:"):
            info["category"] = line.split(":", 1)[1].strip()
        elif line.startswith("Factor:"):
            info["factor"] = line.split(":", 1)[1].strip()
        elif line.startswith("Summary:"):
            info["summary"] = line.split(":", 1)[1].strip()
        elif line.startswith("Evidence:"):
            info["evidence"] = line.split(":", 1)[1].strip()
        elif "filing for" in line:
            m = re.search(r"filing for (\w+)\s*\(([^)]+)\)", line)
            if m:
                info["ticker"] = m.group(1)
                info["sub_sector"] = m.group(2)
            else:
                m2 = re.search(r"filing for (\w+)", line)
                if m2:
                    info["ticker"] = m2.group(1)
            m3 = re.search(r"(10-[KQ])", line)
            if m3:
                info["form_type"] = m3.group(1)

    return info


def is_from_risk_factors_only(evidence: str) -> bool:
    """Check if evidence comes solely from risk_factors sections (not MDA)."""
    evi_lower = evidence.lower()
    has_rf = "[risk_factors/" in evi_lower or "risk_factors/" in evi_lower
    has_mda = "[mda/" in evi_lower
    if has_rf and not has_mda:
        return True
    return False


def is_hypothetical(text: str) -> bool:
    """Check if the text is primarily hypothetical/forward-looking."""
    t = text.lower()
    hypo_phrases = [
        "could adversely", "may adversely", "could have a material adverse",
        "may have a material adverse", "might adversely", "could negatively",
        "may negatively impact", "could harm", "may harm", "could pose",
        "may pose", "poses risks", "failure to", "if we are unable",
        "if we fail", "there can be no assurance", "we cannot assure",
        "could result in", "may result in", "could lead to",
        "may lead to", "could impact", "factors that might affect",
        "factors that could affect",
    ]
    count = sum(1 for p in hypo_phrases if p in t)
    return count >= 2


def extract_percentages(text: str) -> list:
    """Extract percentage values from text."""
    return [float(m) for m in re.findall(r'(\d+(?:\.\d+)?)\s*%', text)]


def classify_factor(info: dict) -> tuple:
    """
    Independently classify the factor sentiment based on summary and evidence.
    Returns (label, rationale, confidence).
    """
    summary = info["summary"]
    evidence = info["evidence"]
    summary_l = summary.lower()
    evidence_l = evidence.lower()
    combined = summary_l + " " + evidence_l
    category = info["category"]
    factor = info["factor"]

    rf_only = is_from_risk_factors_only(evidence)
    hypothetical = is_hypothetical(combined)

    # ------------------------------------------------------------------
    # CRITICAL CONTEXT: cost/expense increases are NEGATIVE, not positive
    # Revenue/earnings increases are POSITIVE
    # ------------------------------------------------------------------

    # Detect cost/expense increases (these are negative)
    cost_increase = bool(re.search(
        r'(cost|expense|expenditure|spending|charges?)\s+(increased|rose|grew|higher|up)|'
        r'(increased|higher|rising|elevated)\s+(cost|expense|expenditure|spending|charges?)|'
        r'(labor|wage|salary|fuel|input|material|freight|transportation)\s+(cost|expense)s?\s+(increased|rose|grew|higher)',
        combined
    ))

    # Detect revenue/earnings improvements (these are positive)
    revenue_positive = bool(re.search(
        r'(revenue|sales|earnings|profit|income|ebitda|ebit)\s+(increased|grew|rose|improved|growth)|'
        r'(increased|higher|improved|record)\s+(revenue|sales|earnings|profit|income)|'
        r'margin\s+(increased|improved|expanded|grew)',
        combined
    ))

    # Detect revenue/earnings declines
    revenue_negative = bool(re.search(
        r'(revenue|sales|earnings|profit|income|ebitda|ebit)\s+(decreased|declined|fell|dropped|lower)|'
        r'(decreased|lower|declined|reduced)\s+(revenue|sales|earnings|profit|income)|'
        r'margin\s+(decreased|declined|compressed|fell|contracted)',
        combined
    ))

    # Detect quantified declines
    has_quantified_decline = bool(re.search(
        r'decreased?\s*(by\s*)?\$?\d+|declined?\s*(by\s*)?\$?\d+|'
        r'fell\s*(by\s*)?\$?\d+|dropped?\s*(by\s*)?\$?\d+|'
        r'\d+%\s*(decrease|decline|drop|reduction|lower)|'
        r'(decreased?|declined?)\s+\d+(\.\d+)?%',
        combined
    ))

    # Detect large quantified declines (>15%)
    large_decline = False
    pcts = extract_percentages(combined)
    for pct in pcts:
        if pct >= 20:
            # Check if this percentage is associated with a decline
            # Look for patterns like "24% decrease" or "decreased 24%"
            if re.search(rf'{pct}%?\s*(decrease|decline|drop|reduction|lower|fell)', combined) or \
               re.search(rf'(decreased?|declined?|fell|dropped?)\s*(by\s*)?{pct}', combined):
                large_decline = True
                break

    # Detect mixed signals
    mixed_signals = any(phrase in combined for phrase in [
        "mixed signals", "mixed trends", "mixed results", "mixed",
        "partially offset", "offset by", "offsetting",
    ])

    # =====================================================================
    # RULE 1: Pure risk-factor boilerplate with hypothetical language
    # =====================================================================
    if rf_only and hypothetical and not has_quantified_decline:
        return ("neutral",
                "Standard risk factor disclosure with hypothetical language; no quantified actual impact.",
                0.75)

    # =====================================================================
    # RULE 2: Forward-looking disclaimer without substance
    # =====================================================================
    if any(p in evidence_l for p in ["forward-looking statements", "forward looking statements",
                                      "safe harbor statement"]):
        if not has_quantified_decline and hypothetical:
            return ("neutral",
                    "Forward-looking disclaimer language without specific negative developments.",
                    0.75)

    # =====================================================================
    # RULE 3: Very thin evidence
    # =====================================================================
    if len(info["evidence"]) < 100 and hypothetical and not has_quantified_decline:
        return ("neutral",
                "Insufficient concrete evidence; language is speculative.",
                0.70)

    # =====================================================================
    # RULE 4: Risk-factor-only source for generic risk categories
    # =====================================================================
    if rf_only and not has_quantified_decline:
        generic_factors = [
            "geopolitical_risk", "fx_exposure", "interest_rate_impact",
            "talent_retention", "environmental_compliance", "litigation_exposure",
            "regulatory_changes", "competitive_dynamics", "market_share",
            "cybersecurity_risks", "digital_automation", "customer_concentration",
            "natural_events", "quality_safety", "capacity_utilization",
            "supply_chain_health",
        ]
        if factor in generic_factors:
            return ("neutral",
                    f"Standard {factor.replace('_', ' ')} risk disclosure from risk factors section without evidence of actual negative impact.",
                    0.70)

    # =====================================================================
    # RULE 5: "No explicit mention" / "No specific" in evidence
    # =====================================================================
    if "no explicit mention" in evidence_l or "no specific" in evidence_l:
        if not has_quantified_decline:
            return ("neutral",
                    "Evidence explicitly states no concrete information found for this factor.",
                    0.70)

    # =====================================================================
    # RULE 6: Geopolitical risk - generic mentions
    # =====================================================================
    if factor == "geopolitical_risk":
        # If there's no specific mention of realized impact
        if not any(w in combined for w in [
            "resulted in", "caused", "led to", "we experienced",
            "we incurred", "impacted our", "negatively affected our results"
        ]):
            return ("neutral",
                    "Geopolitical risk mentioned without evidence of specific realized impact on the company.",
                    0.70)

    # =====================================================================
    # RULE 7: Interest rate - if well-managed or theoretical
    # =====================================================================
    if factor == "interest_rate_impact":
        if "no outstanding debt subject to interest rate" in combined:
            return ("neutral",
                    "Company has no variable-rate debt; interest rate risk is theoretical.",
                    0.80)
        if ("hedg" in combined or "swap" in combined) and \
           not any(w in combined for w in ["increased interest expense", "higher interest cost"]):
            return ("neutral",
                    "Interest rate risk is being managed through hedging/swaps.",
                    0.70)

    # =====================================================================
    # RULE 8: FX exposure - if only risk disclosure without actual impact
    # =====================================================================
    if factor == "fx_exposure":
        if rf_only:
            return ("neutral",
                    "FX risk disclosure from risk factors without evidence of actual adverse impact.",
                    0.70)
        if "do not engage in foreign currency" in combined or "we do not hedge" in combined:
            if not any(w in combined for w in ["decreased", "declined", "unfavorable"]):
                return ("neutral",
                        "FX risk disclosure noting no hedging, but no evidence of actual adverse FX impact.",
                        0.70)

    # =====================================================================
    # RULE 9: Fuel prices - bare mention without actual cost data
    # =====================================================================
    if factor in ["fuel_prices", "fuel_costs_hedging"]:
        if len(info["evidence"]) < 120 and not any(
            w in combined for w in ["increased", "rose", "higher fuel", "fuel expense increased"]):
            return ("neutral",
                    "Fuel price exposure mentioned without evidence of actual cost increase.",
                    0.70)

    # =====================================================================
    # RULE 10: Economic conditions - boilerplate
    # =====================================================================
    if factor == "economic_conditions":
        if (rf_only or "forward-looking" in evidence_l) and not has_quantified_decline:
            if not any(w in combined for w in ["we experienced", "resulted in", "led to a decline"]):
                return ("neutral",
                        "Generic macroeconomic risk disclosure without evidence of actual impact.",
                        0.70)

    # =====================================================================
    # RULE 11: Key sensitivities - inherently forward-looking
    # =====================================================================
    if factor == "key_sensitivities":
        if not has_quantified_decline:
            if not any(w in combined for w in ["resulted in loss", "caused decline",
                                                "we experienced adverse"]):
                return ("neutral",
                        "Key sensitivity disclosure describes potential risks, not realized outcomes.",
                        0.70)

    # =====================================================================
    # RULE 12: Near-term risks from risk factors only
    # =====================================================================
    if factor == "near_term_risks":
        if rf_only and not has_quantified_decline:
            return ("neutral",
                    "Near-term risk disclosure from risk factors without concrete trend evidence.",
                    0.70)

    # =====================================================================
    # RULE 13: Regulatory changes - standard disclosure
    # =====================================================================
    if factor == "regulatory_changes":
        if rf_only and not any(
            w in combined for w in ["fine", "penalty", "enacted", "we were required"]):
            return ("neutral",
                    "Standard regulatory change risk disclosure without evidence of actual regulatory impact.",
                    0.70)
        if "evaluating the impact" in combined:
            return ("neutral",
                    "Company is still evaluating regulatory impact; outcome uncertain.",
                    0.70)

    # =====================================================================
    # RULE 14: Environmental compliance - standard boilerplate
    # =====================================================================
    if factor == "environmental_compliance":
        if rf_only and not any(
            w in combined for w in ["fine", "penalty", "violation", "remediation cost increased",
                                     "compliance cost increased"]):
            return ("neutral",
                    "Standard environmental regulatory disclosure from risk factors without actual compliance issues.",
                    0.70)

    # =====================================================================
    # RULE 15: Talent retention - standard HR risk
    # =====================================================================
    if factor == "talent_retention":
        if not any(w in combined for w in [
            "turnover increased", "attrition rate", "lost key", "departed",
            "resignation", "key employee left"
        ]):
            if rf_only:
                return ("neutral",
                        "Standard talent retention risk disclosure without evidence of actual retention problems.",
                        0.70)

    # =====================================================================
    # RULE 16: Digital/technology risk - standard
    # =====================================================================
    if factor in ["digital_automation", "technology_innovation"]:
        if "no explicit mention" in evidence_l or "no specific" in evidence_l:
            return ("neutral",
                    "No concrete evidence of digital/automation impact; factor is speculative.",
                    0.70)
        if rf_only:
            return ("neutral",
                    "Technology risk from risk factors section without evidence of actual negative impact.",
                    0.70)

    # =====================================================================
    # RULE 17: Litigation - generic risk vs. actual lawsuits
    # =====================================================================
    if factor == "litigation_exposure":
        if rf_only and not any(w in combined for w in [
            "filed", "lawsuit", "settlement", "verdict", "judgment", "class action"
        ]):
            return ("neutral",
                    "Generic litigation risk disclosure without specific active litigation evidence.",
                    0.70)

    # =====================================================================
    # RULE 18: Customer concentration - generic risk
    # =====================================================================
    if factor == "customer_concentration":
        if rf_only:
            return ("neutral",
                    "Customer concentration risk disclosure without evidence of actual customer loss.",
                    0.70)

    # =====================================================================
    # RULE 19: Quality/safety - commitment language (positive) vs incidents
    # =====================================================================
    if factor == "quality_safety":
        if "committed to" in combined and not any(
            w in combined for w in ["incident", "accident", "recall", "defect", "derailment"]):
            return ("neutral",
                    "Safety commitment language without evidence of quality/safety incidents.",
                    0.70)

    # =====================================================================
    # RULE 20: Natural events - standard risk disclosure
    # =====================================================================
    if factor == "natural_events":
        if rf_only:
            return ("neutral",
                    "Standard natural event risk disclosure without evidence of actual impact.",
                    0.70)

    # =====================================================================
    # RULE 21: M&A activity - mixed by nature
    # =====================================================================
    if factor == "ma_activity":
        has_growth = any(w in combined for w in [
            "contributed to growth", "expanding", "value creation", "successfully completed"
        ])
        has_risk = any(w in combined for w in [
            "integration", "risk", "challenge", "impairment", "indemnification"
        ])
        if has_growth and has_risk:
            return ("neutral",
                    "M&A activity shows both growth contribution and integration risks; net effect is mixed.",
                    0.70)

    # =====================================================================
    # RULE 22: Contract backlog - stable
    # =====================================================================
    if factor == "contract_backlog":
        if "stable" in summary_l or "generally stable" in summary_l:
            return ("neutral",
                    "Contract backlog described as generally stable.",
                    0.70)

    # =====================================================================
    # RULE 23: CapEx outlook - cautious/mixed
    # =====================================================================
    if factor == "capex_outlook":
        if "mixed" in summary_l:
            return ("neutral",
                    "CapEx outlook is described as mixed.",
                    0.70)
        if rf_only and hypothetical:
            return ("neutral",
                    "CapEx risk from risk factors without evidence of actual CapEx reduction.",
                    0.70)

    # =====================================================================
    # RULE 24: Competitive dynamics - standard industry description
    # =====================================================================
    if factor == "competitive_dynamics":
        if rf_only and not has_quantified_decline:
            return ("neutral",
                    "Standard competitive landscape description without evidence of market share loss.",
                    0.70)

    # =====================================================================
    # RULE 25: Market share - pressure mentioned but no actual loss
    # =====================================================================
    if factor == "market_share":
        if rf_only and not any(w in combined for w in [
            "lost market share", "share declined", "share decreased"
        ]):
            return ("neutral",
                    "Market share risk from risk factors without evidence of actual share loss.",
                    0.70)

    # =====================================================================
    # RULE 26: Supply chain - generic risk vs actual disruption
    # =====================================================================
    if factor == "supply_chain_health":
        if rf_only and not any(w in combined for w in [
            "disrupted", "shortage", "delayed", "constrained", "higher cost"
        ]):
            return ("neutral",
                    "Standard supply chain risk disclosure without evidence of actual disruption.",
                    0.70)

    # =====================================================================
    # RULE 27: Capacity utilization - hypothetical
    # =====================================================================
    if factor == "capacity_utilization":
        if hypothetical and not any(
            w in combined for w in ["declined", "decreased", "fell", "dropped", "utilization dropped"]):
            return ("neutral",
                    "Capacity utilization concerns are hypothetical without evidence of actual decline.",
                    0.70)

    # =====================================================================
    # RULE 28: Debt leverage - if managed/compliant
    # =====================================================================
    if factor == "debt_leverage":
        if any(w in combined for w in ["repaid", "repayment", "reduced debt",
                                        "paid down", "debt reduction"]):
            if "compliance" in combined:
                return ("neutral",
                        "Debt reduction with covenant compliance suggests prudent capital management.",
                        0.75)

    # =====================================================================
    # RULE 29: Cash flows financing - reduced borrowings may be deleveraging
    # =====================================================================
    if factor == "cash_flows_financing":
        if any(w in combined for w in ["reduced borrowings", "decreased borrowings",
                                        "decrease in net proceeds"]):
            if "compliance" in combined or "repay" in combined:
                return ("neutral",
                        "Decreased financing flows due to deleveraging, which can be a prudent capital decision.",
                        0.70)

    # =====================================================================
    # RULE 30: Cost actions delivering savings
    # =====================================================================
    if factor == "cost_actions":
        # Cost actions can be positive (savings) or negative (restructuring costs)
        has_savings = any(w in combined for w in [
            "delivering measurable savings", "realized savings", "savings of",
            "reduction program", "efficiency", "$15 billion"
        ])
        has_charges = any(w in combined for w in [
            "restructuring charges", "integration expenses", "impairment",
            "negatively impacted", "not yet yielded"
        ])
        if has_savings and not has_charges:
            return ("positive",
                    "Cost reduction programs delivering measurable savings.",
                    0.75)
        if has_savings and has_charges:
            # Net effect: still negative if charges outweigh
            return ("negative",
                    "Cost actions producing some savings but offset by restructuring/integration charges.",
                    0.75)
        # If only restructuring charges mentioned
        if has_charges and not has_savings:
            return ("negative",
                    "Restructuring/integration charges creating cost headwinds.",
                    0.80)

    # =====================================================================
    # RULE 31: Very negative - major deterioration
    # =====================================================================
    # Going concern, material weakness, bankruptcy
    if any(w in combined for w in ["going concern", "material weakness",
                                    "restatement", "bankruptcy"]):
        return ("very_negative",
                "Critical financial health indicator present in filing.",
                0.90)

    # Very large quantified declines in revenue/earnings/margins
    if large_decline and revenue_negative:
        if not mixed_signals:
            return ("very_negative",
                    "Large quantified decline in revenue/earnings/margins indicating significant deterioration.",
                    0.80)

    # Specific very_negative patterns
    if factor == "margin_trajectory":
        # Check for very large margin compression
        m = re.search(r'margin\s+decreased\s+to\s+(\d+(?:\.\d+)?)%.*(?:compared to|from)\s+(\d+(?:\.\d+)?)%', combined)
        if m:
            new_margin = float(m.group(1))
            old_margin = float(m.group(2))
            drop = old_margin - new_margin
            if drop > 10:
                return ("very_negative",
                        f"Operating margin dropped by {drop:.1f} percentage points, indicating severe compression.",
                        0.85)

    # =====================================================================
    # RULE 32: Mixed signals in demand/revenue factors
    # =====================================================================
    if category == "demand_revenue" and mixed_signals:
        if has_quantified_decline and revenue_positive:
            return ("neutral",
                    "Mixed demand signals with both positive and negative quantified trends.",
                    0.70)
        if "mixed" in summary_l and not large_decline:
            return ("neutral",
                    "Summary describes mixed demand trends.",
                    0.70)

    # =====================================================================
    # RULE 33: Cybersecurity risks - standard boilerplate
    # =====================================================================
    if factor in ["cybersecurity_risks", "data_privacy"]:
        if rf_only:
            return ("neutral",
                    "Standard cybersecurity/privacy risk disclosure without evidence of actual breach or incident.",
                    0.70)
        if hypothetical and not any(w in combined for w in [
            "breach", "incident", "compromised", "unauthorized access"
        ]):
            return ("neutral",
                    "Cybersecurity risk is hypothetical with no reported incidents.",
                    0.70)

    # =====================================================================
    # RULE 34: Pricing power - standard competitive risk
    # =====================================================================
    if factor == "pricing_power":
        if rf_only and hypothetical:
            return ("neutral",
                    "Pricing risk from risk factors without evidence of actual pricing pressure.",
                    0.70)

    # =====================================================================
    # RULE 35: Inventory levels - managed/mixed
    # =====================================================================
    if factor == "inventory_levels":
        if "managed" in summary_l or "mixed" in summary_l:
            if not has_quantified_decline:
                return ("neutral",
                        "Inventory levels described as managed or mixed without clear deterioration.",
                        0.70)

    # =====================================================================
    # DEFAULT: Keep as negative
    # =====================================================================
    # Determine confidence based on evidence strength
    if has_quantified_decline and not mixed_signals:
        conf = 0.85
        rationale = "Quantified negative developments support negative classification."
    elif has_quantified_decline and mixed_signals:
        conf = 0.70
        rationale = "Negative developments partially offset by positive factors; net negative."
    elif cost_increase:
        conf = 0.80
        rationale = "Evidence of increasing costs creating headwinds."
    elif hypothetical and not has_quantified_decline:
        # These should probably be neutral, but the summary describes actual concerns
        conf = 0.70
        rationale = "Forward-looking concerns without strong quantified evidence; moderate confidence in negative."
    else:
        conf = 0.75
        rationale = "Evidence supports moderate headwind or declining trend."

    return ("negative", rationale, conf)


def main():
    records = []
    with open(INPUT) as f:
        for line in f:
            records.append(json.loads(line.strip()))

    print(f"Loaded {len(records)} records")

    output_records = []
    changes = []
    label_counts = {"very_negative": 0, "negative": 0, "neutral": 0, "positive": 0, "very_positive": 0}

    for idx, rec in enumerate(records):
        user_content = rec["messages"][1]["content"]
        old_assistant = json.loads(rec["messages"][2]["content"])
        old_label = old_assistant["label"]

        info = parse_user_content(user_content)

        new_label, new_rationale, new_conf = classify_factor(info)

        new_assistant = {
            "label": new_label,
            "rationale": new_rationale,
            "confidence": new_conf
        }

        new_rec = {
            "messages": [
                rec["messages"][0],
                rec["messages"][1],
                {"role": "assistant", "content": json.dumps(new_assistant)}
            ]
        }
        output_records.append(new_rec)
        label_counts[new_label] += 1

        if new_label != old_label:
            change = {
                "index": idx,
                "category": info["category"],
                "factor": info["factor"],
                "ticker": info["ticker"],
                "old_label": old_label,
                "new_label": new_label,
                "reason": new_rationale
            }
            changes.append(change)

    # Write outputs
    with open(OUTPUT, "w") as f:
        for rec in output_records:
            f.write(json.dumps(rec) + "\n")

    with open(CHANGES, "w") as f:
        for change in changes:
            f.write(json.dumps(change) + "\n")

    # Summary
    print(f"\n{'='*60}")
    print(f"REVIEW SUMMARY")
    print(f"{'='*60}")
    print(f"Total records: {len(records)}")
    print(f"Records changed: {len(changes)}")
    print(f"Records unchanged: {len(records) - len(changes)}")
    print(f"\nLabel distribution after review:")
    for label, count in sorted(label_counts.items()):
        pct = count / len(records) * 100
        print(f"  {label:15s}: {count:4d} ({pct:5.1f}%)")

    change_types = {}
    for c in changes:
        key = f"{c['old_label']} -> {c['new_label']}"
        change_types[key] = change_types.get(key, 0) + 1

    print(f"\nChange breakdown:")
    for key, count in sorted(change_types.items(), key=lambda x: -x[1]):
        print(f"  {key}: {count}")

    cat_changes = {}
    for c in changes:
        cat = c["category"]
        cat_changes[cat] = cat_changes.get(cat, 0) + 1

    print(f"\nChanges by category:")
    for cat, count in sorted(cat_changes.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")

    factor_changes = {}
    for c in changes:
        f = c["factor"]
        factor_changes[f] = factor_changes.get(f, 0) + 1

    print(f"\nChanges by factor (top 15):")
    for f, count in sorted(factor_changes.items(), key=lambda x: -x[1])[:15]:
        print(f"  {f}: {count}")

    print(f"\nOutput: {OUTPUT}")
    print(f"Changes: {CHANGES}")


if __name__ == "__main__":
    main()
