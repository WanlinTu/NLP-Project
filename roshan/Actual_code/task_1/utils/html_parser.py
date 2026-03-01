"""
HTML parser utilities for extracting MD&A and Risk Factors from SEC filings.
Handles both iXBRL (2021+) and legacy HTML formats.
"""

import re
import html
from typing import Optional
from pathlib import Path
from dataclasses import dataclass

from bs4 import BeautifulSoup, Tag, NavigableString


@dataclass
class SectionResult:
    """Result of extracting a section from a filing."""
    section_name: str           # "mda" or "risk_factors"
    html_content: str           # minimal HTML
    text_length: int            # character count of plain text
    success: bool
    error: Optional[str] = None


# ── Section title patterns ─────────────────────────────────────────────────────
# Used to match TOC entries to target sections.
# We match on the TITLE text, not item numbers, since TOC formatting varies.

MDA_PATTERNS = [
    re.compile(r"management.{0,5}s?\s+discussion\s+and\s+analysis", re.IGNORECASE),
    re.compile(r"MD&A", re.IGNORECASE),
]

RISK_FACTORS_PATTERNS = [
    re.compile(r"risk\s+factors", re.IGNORECASE),
]

# Patterns for the section that follows each target (used to find end boundary)
MDA_END_PATTERNS_10K = [
    re.compile(r"quantitative\s+and\s+qualitative\s+disclosures?\s+about\s+market\s+risk", re.IGNORECASE),
    re.compile(r"item\s+7a", re.IGNORECASE),
]
MDA_END_PATTERNS_10Q = [
    re.compile(r"quantitative\s+and\s+qualitative\s+disclosures?\s+about\s+market\s+risk", re.IGNORECASE),
    re.compile(r"item\s+3", re.IGNORECASE),
]
RISK_FACTORS_END_PATTERNS_10K = [
    re.compile(r"unresolved\s+staff\s+comments", re.IGNORECASE),
    re.compile(r"item\s+1b", re.IGNORECASE),
    re.compile(r"item\s+1c", re.IGNORECASE),  # newer filings have 1C (Cybersecurity)
]
RISK_FACTORS_END_PATTERNS_10Q = [
    re.compile(r"management.{0,5}s?\s+discussion\s+and\s+analysis", re.IGNORECASE),
    re.compile(r"item\s+2", re.IGNORECASE),
]


def detect_form_type(filepath: Path) -> str:
    """Detect 10-K or 10-Q from the filename."""
    name = filepath.name.upper()
    if "10-K" in name:
        return "10-K"
    elif "10-Q" in name:
        return "10-Q"
    raise ValueError(f"Cannot detect form type from filename: {filepath.name}")


def detect_format(raw_html: str) -> str:
    """Detect whether filing is iXBRL or legacy HTML."""
    if "xmlns:ix=" in raw_html[:5000] or "<ix:" in raw_html[:10000]:
        return "ixbrl"
    return "legacy"


def parse_toc(soup: BeautifulSoup, raw_html: str) -> dict[str, str]:
    """
    Parse the Table of Contents to build a mapping of anchor_id → section_title.

    Returns dict like:
        {"s94F1802926BB903F63F9CAD5FE035898": "Risk Factors",
         "s56F53CB924A2F11EB305CAD5FF70E306": "Management's Discussion and Analysis..."}
    """
    toc_links: dict[str, list[str]] = {}  # anchor_id → list of text fragments

    # Find all <a href="#..."> links in the first 20% of the document
    # (TOC is always near the beginning)
    cutoff = len(raw_html) // 5
    toc_region_html = raw_html[:cutoff]
    toc_soup = BeautifulSoup(toc_region_html, "lxml")

    for a_tag in toc_soup.find_all("a", href=True):
        href = a_tag["href"]
        if not href.startswith("#"):
            continue
        anchor_id = href[1:]  # strip the #
        text = a_tag.get_text(strip=True)
        # Skip empty, page numbers, "Table of Contents"
        if not text or text.isdigit() or "table of contents" in text.lower():
            continue
        if anchor_id not in toc_links:
            toc_links[anchor_id] = []
        toc_links[anchor_id].append(text)

    # Merge text fragments for the same anchor into a single title
    toc_map: dict[str, str] = {}
    for anchor_id, texts in toc_links.items():
        combined = " ".join(texts)
        # Decode HTML entities
        combined = html.unescape(combined)
        toc_map[anchor_id] = combined

    return toc_map


def find_section_anchor(
    toc_map: dict[str, str],
    patterns: list[re.Pattern],
) -> Optional[str]:
    """Find the anchor ID for a section by matching TOC titles against patterns."""
    for anchor_id, title in toc_map.items():
        for pat in patterns:
            if pat.search(title):
                return anchor_id
    return None


def find_anchor_position(raw_html: str, anchor_id: str, html_format: str) -> Optional[int]:
    """
    Find the byte position of an anchor in the raw HTML.

    iXBRL: <div id="ANCHOR_ID">
    Legacy: <a name="ANCHOR_ID"> or <A NAME="ANCHOR_ID">

    Uses case-insensitive regex to handle mixed-case HTML attributes.
    """
    # Case-insensitive search for name="ID" or id="ID"
    patterns = [
        re.compile(re.escape(f'name="{anchor_id}"'), re.IGNORECASE),
        re.compile(re.escape(f"name='{anchor_id}'"), re.IGNORECASE),
        re.compile(re.escape(f'id="{anchor_id}"'), re.IGNORECASE),
        re.compile(re.escape(f"id='{anchor_id}'"), re.IGNORECASE),
    ]

    for pat in patterns:
        m = pat.search(raw_html)
        if m:
            return m.start()

    return None


def find_end_boundary(
    raw_html: str,
    start_pos: int,
    toc_map: dict[str, str],
    end_patterns: list[re.Pattern],
    html_format: str,
) -> int:
    """
    Find the end boundary of a section.

    Strategy:
    1. Look for the next section's anchor ID via TOC matching
    2. If that fails, search for the next section heading directly in text
    3. If all else fails, use a generous chunk (500KB from start)
    """
    # Strategy 1: Find the next section via TOC
    next_anchor = find_section_anchor(toc_map, end_patterns)
    if next_anchor:
        pos = find_anchor_position(raw_html, next_anchor, html_format)
        if pos and pos > start_pos:
            return pos

    # Strategy 2: Search for heading text directly after start_pos
    search_region = raw_html[start_pos:]
    for pat in end_patterns:
        # Find all matches and pick the SECOND one (first might be in the TOC reference)
        matches = list(pat.finditer(search_region))
        # Skip matches that are too close to start (likely within the section header itself)
        for m in matches:
            if m.start() > 500:  # at least 500 chars into the section
                return start_pos + m.start()

    # Strategy 3: Fallback — take 500KB from start
    return min(start_pos + 500_000, len(raw_html))


def extract_section_html(
    raw_html: str,
    start_pos: int,
    end_pos: int,
) -> str:
    """Extract the HTML between two positions and return as a string."""
    return raw_html[start_pos:end_pos]


def clean_section_html(section_html: str) -> str:
    """
    Clean extracted section HTML into minimal HTML.

    Preserves:
    - Heading structure (bold text → <b> tags)
    - Paragraph breaks
    - Tables (simplified)

    Strips:
    - All iXBRL tags (ix:*)
    - Inline styles
    - Classes, IDs
    - Hidden elements
    - Images, scripts
    - Empty elements
    """
    soup = BeautifulSoup(section_html, "lxml")

    # Remove hidden elements
    for el in soup.find_all(style=re.compile(r"display\s*:\s*none")):
        el.decompose()

    # Remove script, style, img tags
    for tag_name in ["script", "style", "img", "link", "meta"]:
        for el in soup.find_all(tag_name):
            el.decompose()

    # Unwrap all iXBRL tags (keep their text content)
    for el in soup.find_all(re.compile(r"^ix:")):
        el.unwrap()

    # Also unwrap <xbrli:*>, <link:*>, etc.
    for el in soup.find_all(re.compile(r":")):
        if el.name and ":" in el.name:
            el.unwrap()

    # Now convert to minimal HTML
    output_parts: list[str] = []
    _walk_and_convert(soup.body or soup, output_parts)

    result = "\n".join(output_parts)

    # Clean up excessive whitespace
    result = re.sub(r"\n{3,}", "\n\n", result)
    result = result.strip()

    return result


def _is_bold(tag: Tag) -> bool:
    """Check if a tag or its children have bold styling."""
    if tag.name in ("b", "strong"):
        return True
    style = tag.get("style", "")
    if "font-weight:700" in style or "font-weight:bold" in style or "font-weight: bold" in style:
        return True
    # Check <font> tags (legacy format)
    if tag.name == "font":
        style = tag.get("style", "")
        if "font-weight:bold" in style or "font-weight:700" in style:
            return True
    return False


def _is_italic(tag: Tag) -> bool:
    """Check if a tag has italic styling."""
    if tag.name in ("i", "em"):
        return True
    style = tag.get("style", "")
    return "font-style:italic" in style


def _get_text_content(tag) -> str:
    """Get clean text content from a tag, handling HTML entities."""
    text = tag.get_text(separator=" ", strip=False)
    text = html.unescape(text)
    # Normalize whitespace (but preserve newlines for now)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return text.strip()


def _walk_and_convert(element, parts: list[str], depth: int = 0) -> None:
    """
    Recursively walk the DOM and convert to minimal HTML.

    Rules:
    - Bold text in a div/span that looks like a heading → <b>text</b>
    - Regular paragraphs → <p>text</p>
    - Tables → simplified <table>
    - Everything else → just extract text
    """
    if isinstance(element, NavigableString):
        return

    if not isinstance(element, Tag):
        return

    tag = element

    # Skip hidden elements
    style = tag.get("style", "")
    if "display:none" in style or "display: none" in style:
        return

    # Handle tables specially
    if tag.name == "table":
        table_html = _convert_table(tag)
        if table_html:
            parts.append(table_html)
        return

    # Handle <hr> as section break
    if tag.name == "hr":
        parts.append("<hr>")
        return

    # Check if this is a "block" element (div, p, etc.)
    block_tags = {"div", "p", "section", "article", "blockquote", "li", "td", "th"}

    if tag.name in block_tags:
        text = _get_text_content(tag)
        if not text:
            # Still recurse into children — there might be nested content
            for child in tag.children:
                _walk_and_convert(child, parts, depth + 1)
            return

        # Determine if this is a heading (bold, short text)
        is_heading = False
        if len(text) < 200:
            # Check if the tag itself is bold
            if _is_bold(tag):
                is_heading = True
            else:
                # Check if ALL meaningful children are bold
                bold_children = tag.find_all(
                    lambda t: isinstance(t, Tag) and _is_bold(t)
                )
                if bold_children:
                    bold_text = " ".join(_get_text_content(b) for b in bold_children).strip()
                    if bold_text and len(bold_text) > len(text) * 0.7:
                        is_heading = True

        if is_heading and text:
            italic = _is_italic(tag) or any(
                _is_italic(c) for c in tag.find_all(True) if isinstance(c, Tag)
            )
            if italic:
                parts.append(f"<b><i>{text}</i></b>")
            else:
                parts.append(f"<b>{text}</b>")
        elif text:
            parts.append(f"<p>{text}</p>")

        return

    # For non-block elements (span, font, a, etc.), recurse into children
    for child in tag.children:
        _walk_and_convert(child, parts, depth + 1)


def _convert_table(table_tag: Tag) -> Optional[str]:
    """Convert a table to simplified HTML, preserving structure."""
    rows = table_tag.find_all("tr")
    if not rows:
        return None

    # Check if the table has meaningful content (not just spacing/layout)
    all_text = _get_text_content(table_tag)
    if len(all_text.strip()) < 20:
        return None

    out = ["<table>"]
    for row in rows:
        cells = row.find_all(["td", "th"])
        if not cells:
            continue
        cell_texts = []
        for cell in cells:
            text = _get_text_content(cell)
            tag_name = "th" if cell.name == "th" or _is_bold(cell) else "td"
            cell_texts.append(f"<{tag_name}>{text}</{tag_name}>")
        if any(_get_text_content(c) for c in cells):
            out.append(f"<tr>{''.join(cell_texts)}</tr>")

    out.append("</table>")

    # Don't return tables that ended up with no rows
    if len(out) <= 2:
        return None

    return "\n".join(out)


def extract_sections(
    filepath: Path,
) -> dict[str, SectionResult]:
    """
    Extract MD&A and Risk Factors sections from a SEC filing HTML.

    Args:
        filepath: Path to the raw SEC filing HTML.

    Returns:
        Dict with keys "mda" and "risk_factors", each a SectionResult.
    """
    form_type = detect_form_type(filepath)

    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        raw_html = f.read()

    html_format = detect_format(raw_html)

    # Parse TOC
    toc_map = parse_toc(BeautifulSoup(raw_html[:len(raw_html)//5], "lxml"), raw_html)

    results: dict[str, SectionResult] = {}

    # Define what to extract based on form type
    if form_type == "10-K":
        sections = {
            "mda": {
                "start_patterns": MDA_PATTERNS,
                "end_patterns": MDA_END_PATTERNS_10K,
            },
            "risk_factors": {
                "start_patterns": RISK_FACTORS_PATTERNS,
                "end_patterns": RISK_FACTORS_END_PATTERNS_10K,
            },
        }
    else:  # 10-Q
        sections = {
            "mda": {
                "start_patterns": MDA_PATTERNS,
                "end_patterns": MDA_END_PATTERNS_10Q,
            },
            "risk_factors": {
                "start_patterns": RISK_FACTORS_PATTERNS,
                "end_patterns": RISK_FACTORS_END_PATTERNS_10Q,
            },
        }

    for section_name, config in sections.items():
        try:
            # Find section start via TOC
            anchor_id = find_section_anchor(toc_map, config["start_patterns"])

            if not anchor_id:
                # Fallback: search for section heading directly in the document
                start_pos = _fallback_find_section_start(
                    raw_html, section_name, form_type
                )
                if start_pos is None:
                    results[section_name] = SectionResult(
                        section_name=section_name,
                        html_content="",
                        text_length=0,
                        success=False,
                        error=f"Could not find {section_name} section in TOC or document",
                    )
                    continue
            else:
                start_pos = find_anchor_position(raw_html, anchor_id, html_format)
                if start_pos is None:
                    results[section_name] = SectionResult(
                        section_name=section_name,
                        html_content="",
                        text_length=0,
                        success=False,
                        error=f"Found TOC anchor {anchor_id} but could not locate it in document",
                    )
                    continue

            # Find section end
            end_pos = find_end_boundary(
                raw_html, start_pos, toc_map, config["end_patterns"], html_format
            )

            # Extract raw section HTML
            section_html = extract_section_html(raw_html, start_pos, end_pos)

            # Clean into minimal HTML
            clean_html = clean_section_html(section_html)

            # Get plain text length for validation
            text_only = re.sub(r"<[^>]+>", "", clean_html)
            text_length = len(text_only.strip())

            # Sanity check: section should have meaningful content
            if text_length < 100:
                results[section_name] = SectionResult(
                    section_name=section_name,
                    html_content=clean_html,
                    text_length=text_length,
                    success=False,
                    error=f"Extracted section too short ({text_length} chars). Likely extraction error.",
                )
            else:
                results[section_name] = SectionResult(
                    section_name=section_name,
                    html_content=clean_html,
                    text_length=text_length,
                    success=True,
                )

        except Exception as e:
            results[section_name] = SectionResult(
                section_name=section_name,
                html_content="",
                text_length=0,
                success=False,
                error=str(e),
            )

    return results


def _fallback_find_section_start(
    raw_html: str,
    section_name: str,
    form_type: str,
) -> Optional[int]:
    """
    Fallback: find a section start by searching for the heading directly in the HTML.
    Used when TOC parsing fails.
    """
    if section_name == "mda":
        if form_type == "10-K":
            patterns = [
                re.compile(
                    r"item\s*7\.?\s*[-–—.]?\s*management.{0,5}s?\s+discussion",
                    re.IGNORECASE,
                ),
            ]
        else:
            patterns = [
                re.compile(
                    r"item\s*2\.?\s*[-–—.]?\s*management.{0,5}s?\s+discussion",
                    re.IGNORECASE,
                ),
            ]
    elif section_name == "risk_factors":
        patterns = [
            re.compile(
                r"item\s*1a\.?\s*[-–—.]?\s*risk\s+factors",
                re.IGNORECASE,
            ),
        ]
    else:
        return None

    # Search from 10% into the document (skip cover page / TOC)
    search_start = len(raw_html) // 10
    search_region = raw_html[search_start:]

    for pat in patterns:
        m = pat.search(search_region)
        if m:
            return search_start + m.start()

    return None
