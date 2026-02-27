#!/usr/bin/env python3
"""
Enhanced SEC MD&A Extractor
- Robust TOC detection and skipping
- Multi-stage extraction with validation
- Clean HTML output with preserved structure
- Sector-aware extraction patterns
- Factor annotation readiness
"""

import re
import os
import csv
import gzip
import json
import argparse
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from collections import defaultdict
import hashlib

import lxml.html as LH
import lxml.etree as etree
from lxml.etree import _Element
from tqdm import tqdm
from bs4 import BeautifulSoup

import warnings
warnings.filterwarnings('ignore')

# -------------------------- Logging --------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("sec_mda_enhanced.log"),
        logging.StreamHandler()
    ],
)
LOG = logging.getLogger("MDA_ENHANCED")

# -------------------------- Enhanced Patterns --------------------------

# MD&A title patterns by filing type
MDA_TITLE_PATTERNS = {
    "10-K": [
        re.compile(r"^\s*item\s*7\.?\s*(?:management['']?s?\s+discussion\s+(?:and|&)\s+analysis|MD&A)", re.I | re.M),
        re.compile(r"management['']?s?\s+discussion\s+(?:and|&)\s+analysis\s+of\s+(?:financial\s+)?(?:condition|results)", re.I),
        re.compile(r"^\s*item\s*7\s*[-–—:\.]\s*(?!item\s*7a)", re.I | re.M),  # Item 7 but not 7A
    ],
    "10-Q": [
        re.compile(r"^\s*item\s*2\.?\s*(?:management['']?s?\s+discussion\s+(?:and|&)\s+analysis|MD&A)", re.I | re.M),
        re.compile(r"^\s*part\s+i+\s*[-–—]\s*item\s*2\b", re.I | re.M),
        re.compile(r"^\s*item\s*2\s*[-–—:\.]\s*(?!item\s*3)", re.I | re.M),
    ]
}

# MD&A subsections for validation and factor extraction
MDA_SUBSECTIONS = {
    "overview": re.compile(r"\b(?:overview|executive\s+summary|introduction|background)\b", re.I),
    "results": re.compile(r"\b(?:results?\s+of\s+operations?|operating\s+results?)\b", re.I),
    "liquidity": re.compile(r"\b(?:liquidity\s+(?:and|&)?\s*(?:capital\s+resources?)?)\b", re.I),
    "cash_flows": re.compile(r"\b(?:cash\s+flows?|sources?\s+and\s+uses?\s+of\s+cash)\b", re.I),
    "critical_accounting": re.compile(r"\b(?:critical\s+accounting\s+(?:policies|estimates)|significant\s+accounting)\b", re.I),
    "revenue": re.compile(r"\b(?:revenue|net\s+sales?|gross\s+sales?)\s+(?:recognition|analysis|discussion)\b", re.I),
    "expenses": re.compile(r"\b(?:operating\s+expenses?|cost\s+of\s+(?:sales?|revenues?)|SG&A)\b", re.I),
    "outlook": re.compile(r"\b(?:outlook|guidance|forward[- ]looking|trends?|expectations?)\b", re.I),
}

# Enhanced TOC detection patterns
TOC_INDICATORS = [
    re.compile(r"table\s+of\s+contents?", re.I),
    re.compile(r"^\s*(?:index|contents?)\s*$", re.I | re.M),
    re.compile(r"\.{3,}.*\d{1,4}\s*$", re.M),  # Dotted leaders with page numbers
    re.compile(r"(?:page|pg)\s*\d{1,4}\s*$", re.I | re.M),
    re.compile(r"^\s*(?:item|part)\s+[\divx]+.*?\d{1,4}\s*$", re.I | re.M),  # Item listings with page numbers
]

# End boundary patterns
END_PATTERNS = {
    "10-K": [
        re.compile(r"^\s*item\s*7a\b", re.I | re.M),
        re.compile(r"^\s*item\s*8\b", re.I | re.M),
        re.compile(r"quantitative\s+and\s+qualitative\s+disclosures?\s+about\s+market\s+risk", re.I),
        re.compile(r"financial\s+statements\s+and\s+supplementary\s+data", re.I),
    ],
    "10-Q": [
        re.compile(r"^\s*item\s*3\b", re.I | re.M),
        re.compile(r"^\s*item\s*4\b", re.I | re.M),
        re.compile(r"controls?\s+and\s+procedures?", re.I),
        re.compile(r"legal\s+proceedings?", re.I),
        re.compile(r"^\s*part\s+ii\b", re.I | re.M),
    ],
}

# -------------------------- Utilities --------------------------

def clean_xml_declarations(html: str) -> str:
    """Remove XML declarations and problematic content"""
    html = re.sub(r'<\?xml[^>]*\?>', '', html)
    html = re.sub(r'<!DOCTYPE[^>]*>', '', html, flags=re.I)
    html = html.replace('\ufeff', '').replace('\x00', '')
    return html

def safe_parse_html(html: str) -> Optional[_Element]:
    """Safely parse HTML with fallbacks"""
    html = clean_xml_declarations(html)
    
    try:
        return LH.fromstring(html)
    except:
        try:
            parser = etree.HTMLParser(encoding='utf-8', recover=True, remove_blank_text=True)
            return etree.HTML(html.encode('utf-8'), parser)
        except:
            LOG.error("Failed to parse HTML")
            return None

def get_text(el: _Element, sep=" ") -> str:
    """Extract clean text from element"""
    if el is None:
        return ""
    try:
        text = sep.join(el.itertext()).strip()
        # Clean whitespace
        text = re.sub(r'\s+', ' ', text)
        text = text.replace('\xa0', ' ')
        return text
    except:
        return ""

def detect_filing_type(filename: str, text_head: str) -> str:
    """Detect filing type from filename and content"""
    fn = filename.lower()
    if "10-k" in fn or "10k" in fn:
        return "10-K"
    if "10-q" in fn or "10q" in fn:
        return "10-Q"
    
    h = text_head.lower()
    if "annual report" in h or re.search(r"\byear ended\b|\bfiscal year\b", h):
        return "10-K"
    if "quarterly report" in h or re.search(r"\b(?:three|six|nine) months ended\b", h):
        return "10-Q"
    
    return "10-K"

# -------------------------- Data Classes --------------------------

@dataclass
class ExtractResult:
    method: str
    html: str
    text_len: int
    confidence: float = 1.0
    subsections: Dict[str, bool] = field(default_factory=dict)
    metadata: Dict[str, any] = field(default_factory=dict)

@dataclass
class FileJob:
    path: Path
    ticker: str
    sector: Optional[str] = None

# -------------------------- Enhanced TOC Detection --------------------------

class TOCDetector:
    """Advanced TOC detection to avoid false starts"""
    
    @staticmethod
    def is_toc_element(el: _Element, text: Optional[str] = None) -> bool:
        """Check if element is part of TOC"""
        if el is None:
            return False
        
        if text is None:
            text = get_text(el)
        
        if not text or len(text) > 2000:  # Too long for TOC entry
            return False
        
        text_lower = text.lower()
        
        # Check for explicit TOC markers
        for pattern in TOC_INDICATORS[:2]:  # "table of contents" or "index"
            if pattern.search(text):
                return True
        
        # Check for TOC-like structure
        lines = text.split('\n')
        if len(lines) > 5:  # Multiple lines suggesting TOC
            toc_score = 0
            for line in lines[:10]:
                line = line.strip()
                # Check for page numbers, dotted leaders, item listings
                for pattern in TOC_INDICATORS[2:]:
                    if pattern.search(line):
                        toc_score += 1
            
            if toc_score >= 3:  # Multiple TOC-like lines
                return True
        
        # Single line checks
        if len(text) < 200:  # Short enough for TOC entry
            # Check for item + page number pattern
            if re.search(r'\bitem\s+\d+[a-z]?\b.*\d{1,4}\s*$', text_lower):
                # But not if it's followed by substantial text
                next_el = el.getnext()
                if next_el is not None:
                    next_text = get_text(next_el)
                    if len(next_text) < 100:  # Next element is also short
                        return True
        
        return False
    
    @staticmethod
    def skip_toc_section(tree: _Element, start_candidates: List[_Element]) -> List[_Element]:
        """Filter out TOC entries from candidates"""
        filtered = []
        
        for el in start_candidates:
            if not TOCDetector.is_toc_element(el):
                filtered.append(el)
            else:
                LOG.debug(f"Skipping TOC element: {get_text(el)[:100]}")
        
        return filtered

# -------------------------- Content Validator --------------------------

class ContentValidator:
    """Validate MD&A content quality"""
    
    @staticmethod
    def validate_mda_content(el: _Element, lookahead: int = 5) -> Tuple[bool, float, Dict[str, bool]]:
        """Validate and score MD&A content"""
        if el is None:
            return False, 0.0, {}
        
        # Collect text from element and following siblings
        text_blocks = []
        current = el
        for _ in range(lookahead):
            if current is None:
                break
            text = get_text(current)
            if text:
                text_blocks.append(text)
            current = current.getnext()
        
        combined_text = " ".join(text_blocks)
        combined_lower = combined_text.lower()
        
        # Check for subsections
        subsections_found = {}
        for name, pattern in MDA_SUBSECTIONS.items():
            subsections_found[name] = bool(pattern.search(combined_text))
        
        # Calculate confidence score
        subsection_count = sum(subsections_found.values())
        
        # Check for financial terms
        financial_terms = [
            "revenue", "expense", "income", "profit", "loss", "margin",
            "cash", "liquidity", "capital", "assets", "liabilities",
            "fiscal", "quarter", "year", "compared to", "versus",
            "increase", "decrease", "growth", "decline"
        ]
        financial_count = sum(1 for term in financial_terms if term in combined_lower)
        
        # Score calculation
        confidence = 0.0
        
        if subsection_count >= 3:
            confidence = 0.9
        elif subsection_count >= 2:
            confidence = 0.7
        elif subsection_count >= 1:
            confidence = 0.5
        
        if financial_count >= 10:
            confidence = min(1.0, confidence + 0.2)
        elif financial_count >= 5:
            confidence = min(1.0, confidence + 0.1)
        
        # Length check
        if len(combined_text) < 500:
            confidence *= 0.5
        
        # Check if still looks like TOC
        if TOCDetector.is_toc_element(el, combined_text):
            confidence *= 0.3
        
        is_valid = confidence >= 0.5 and len(combined_text) >= 300
        
        return is_valid, confidence, subsections_found

# -------------------------- Enhanced Extractor --------------------------

class EnhancedMDAExtractor:
    """Main MD&A extraction engine with multiple strategies"""
    
    def __init__(self, mode: str = "accurate", min_content: int = 3000):
        self.mode = mode
        self.min_content = min_content
        self.stats = defaultdict(int)
    
    def extract(self, html: str, filename: str, sector: Optional[str] = None) -> Optional[ExtractResult]:
        """Extract MD&A with enhanced techniques"""
        
        # Parse HTML
        tree = safe_parse_html(html)
        if tree is None:
            self.stats["parse_failed"] += 1
            return None
        
        # Clean irrelevant elements
        etree.strip_elements(tree, "script", "style", "noscript", "meta", "link", with_tail=False)
        
        # Detect filing type
        head_text = get_text(tree)[:15000]
        file_type = detect_filing_type(filename, head_text)
        
        LOG.debug(f"Processing {filename} as {file_type}")
        
        # Try extraction strategies in order
        result = None
        
        if self.mode in ["balanced", "accurate"]:
            # Strategy 1: DOM-based extraction
            result = self._extract_dom(tree, file_type)
            
            if result is None and self.mode == "accurate":
                # Strategy 2: Table-based extraction
                result = self._extract_table(tree, file_type)
        
        if result is None:
            # Strategy 3: Text-based extraction (fallback)
            result = self._extract_text(tree, file_type)
        
        if result:
            self.stats[result.method] += 1
            # Add metadata
            result.metadata['filing_type'] = file_type
            result.metadata['sector'] = sector
            result.metadata['filename'] = filename
        else:
            self.stats["failed"] += 1
        
        return result
    
    def _extract_dom(self, tree: _Element, file_type: str) -> Optional[ExtractResult]:
        """DOM-based extraction with TOC avoidance"""
        
        # Find candidate start elements
        xpath_query = "//h1 | //h2 | //h3 | //h4 | //b | //strong | //p | //div | //td"
        candidates = tree.xpath(xpath_query)
        
        # Filter out TOC entries
        candidates = TOCDetector.skip_toc_section(tree, candidates)
        
        # Find MD&A start
        patterns = MDA_TITLE_PATTERNS[file_type]
        start_el = None
        confidence = 0.0
        subsections = {}
        
        for el in candidates:
            text = get_text(el)
            if not text or len(text) > 2000:
                continue
            
            # Check for MD&A pattern
            for pattern in patterns:
                if pattern.search(text):
                    # Validate content
                    is_valid, conf, subs = ContentValidator.validate_mda_content(el, lookahead=7)
                    if is_valid and conf > confidence:
                        start_el = el
                        confidence = conf
                        subsections = subs
                        break
        
        if start_el is None:
            return None
        
        # Find end boundary
        end_el = self._find_end_boundary(start_el, file_type)
        
        # Extract content
        html_content = self._extract_content_between(start_el, end_el)
        
        # Clean and structure the HTML
        clean_html = self._clean_extracted_html(html_content)
        
        text_len = len(get_text(safe_parse_html(clean_html)))
        
        if text_len < 300:
            return None
        
        return ExtractResult(
            method="dom",
            html=clean_html,
            text_len=text_len,
            confidence=confidence,
            subsections=subsections
        )
    
    def _extract_table(self, tree: _Element, file_type: str) -> Optional[ExtractResult]:
        """Table-based extraction for table-heavy filings"""
        
        patterns = MDA_TITLE_PATTERNS[file_type]
        
        for table in tree.xpath("//table"):
            table_text = get_text(table)
            if not table_text or TOCDetector.is_toc_element(table, table_text):
                continue
            
            for pattern in patterns:
                if pattern.search(table_text):
                    # Found MD&A in table
                    end_el = self._find_end_boundary(table, file_type)
                    html_content = self._extract_content_between(table, end_el)
                    clean_html = self._clean_extracted_html(html_content)
                    
                    text_len = len(get_text(safe_parse_html(clean_html)))
                    
                    if text_len >= 300:
                        return ExtractResult(
                            method="table",
                            html=clean_html,
                            text_len=text_len,
                            confidence=0.7
                        )
        
        return None
    
    def _extract_text(self, tree: _Element, file_type: str) -> Optional[ExtractResult]:
        """Text-based extraction as fallback"""
        
        full_text = get_text(tree, sep="\n")
        patterns = MDA_TITLE_PATTERNS[file_type]
        
        # Find start position
        start_pos = None
        for pattern in patterns:
            match = pattern.search(full_text)
            if match:
                # Check it's not in TOC
                context = full_text[max(0, match.start()-500):match.end()+1000]
                if not any(p.search(context) for p in TOC_INDICATORS):
                    start_pos = match.start()
                    break
        
        if start_pos is None:
            return None
        
        # Find end position
        end_pos = len(full_text)
        search_text = full_text[start_pos + self.min_content:]
        
        for pattern in END_PATTERNS[file_type]:
            match = pattern.search(search_text)
            if match:
                end_pos = min(end_pos, start_pos + self.min_content + match.start())
                break
        
        # Extract text
        mda_text = full_text[start_pos:end_pos].strip()
        
        if len(mda_text) < 300:
            return None
        
        # Convert to simple HTML
        html_content = self._text_to_html(mda_text)
        
        return ExtractResult(
            method="text",
            html=html_content,
            text_len=len(mda_text),
            confidence=0.5
        )
    
    def _find_end_boundary(self, start_el: _Element, file_type: str) -> Optional[_Element]:
        """Find where MD&A ends"""
        
        patterns = END_PATTERNS[file_type]
        
        current = start_el.getnext()
        chars_collected = 0
        max_iterations = 5000
        iterations = 0
        
        while current is not None and iterations < max_iterations:
            iterations += 1
            
            text = get_text(current)
            chars_collected += len(text)
            
            # Only check for end after minimum content
            if chars_collected >= self.min_content:
                for pattern in patterns:
                    if pattern.search(text[:500]):  # Check beginning of text
                        return current
            
            # Navigate to next element
            next_el = current.getnext()
            if next_el is None and current.getparent() is not None:
                # Try parent's next sibling
                next_el = current.getparent().getnext()
            current = next_el
        
        return None
    
    def _extract_content_between(self, start: _Element, end: Optional[_Element]) -> str:
        """Extract HTML content between start and end elements"""
        
        parts = []
        current = start
        max_elements = 5000
        count = 0
        
        while current is not None and count < max_elements:
            if current is end:
                break
            
            try:
                # Clone element to avoid modifying original
                html_str = LH.tostring(current, encoding="unicode", method="html")
                parts.append(html_str)
            except:
                # Fallback to text if serialization fails
                text = get_text(current)
                if text:
                    parts.append(f"<p>{text}</p>")
            
            count += 1
            current = current.getnext()
        
        return "".join(parts)
    
    def _clean_extracted_html(self, html: str) -> str:
        """Clean and structure extracted HTML"""
        
        # Parse with BeautifulSoup for better cleaning
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove empty elements
        for tag in soup.find_all():
            if not tag.get_text(strip=True) and tag.name not in ['br', 'hr']:
                tag.decompose()
        
        # Remove excessive nested divs
        for div in soup.find_all('div'):
            if len(div.find_all('div')) > 10:  # Deeply nested
                # Flatten structure
                for child in div.find_all('div'):
                    child.unwrap()
        
        # Clean attributes (remove style, class, etc. for cleaner output)
        for tag in soup.find_all():
            # Keep only essential attributes
            allowed_attrs = ['href', 'src', 'colspan', 'rowspan']
            for attr in list(tag.attrs.keys()):
                if attr not in allowed_attrs:
                    del tag.attrs[attr]
        
        # Wrap in proper HTML structure
        clean_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>MD&A Extract</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        h1, h2, h3, h4 {{ color: #333; margin-top: 20px; }}
        p {{ margin: 10px 0; }}
    </style>
</head>
<body>
    <div class="mda-content">
        {str(soup)}
    </div>
</body>
</html>"""
        
        return clean_html
    
    def _text_to_html(self, text: str) -> str:
        """Convert plain text to structured HTML"""
        
        # Escape HTML characters
        import html
        text = html.escape(text)
        
        # Convert line breaks to paragraphs
        paragraphs = text.split('\n\n')
        html_paragraphs = [f"<p>{p.strip()}</p>" for p in paragraphs if p.strip()]
        
        content = "\n".join(html_paragraphs)
        
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>MD&A Extract</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
        p {{ margin: 10px 0; }}
    </style>
</head>
<body>
    <div class="mda-content">
        <h2>Management's Discussion and Analysis</h2>
        {content}
    </div>
</body>
</html>"""

# -------------------------- Output Writer --------------------------

class OutputWriter:
    """Handle output writing with metadata"""
    
    def __init__(self, out_root: Path):
        self.dir_html = out_root / "mda_clean"
        self.dir_structured = out_root / "mda_structured"
        self.dir_meta = out_root / "mda_metadata"
        self.dir_factors = out_root / "mda_factors"
        
        for d in [self.dir_html, self.dir_structured, self.dir_meta, self.dir_factors]:
            d.mkdir(parents=True, exist_ok=True)
    
    def write_result(self, job: FileJob, result: ExtractResult) -> Dict:
        """Write extraction results with metadata"""
        
        stem = job.path.stem
        
        # Write clean HTML
        clean_file = self.dir_html / f"{stem}_mda.html"
        clean_file.write_text(result.html, encoding="utf-8")
        
        # Write structured version with metadata
        structured_html = self._add_metadata_to_html(result.html, job, result)
        struct_file = self.dir_structured / f"{stem}_mda_structured.html"
        struct_file.write_text(structured_html, encoding="utf-8")
        
        # Extract and save factors if subsections were found
        if result.subsections:
            factors = self._extract_factors(result)
            factor_file = self.dir_factors / f"{stem}_factors.json"
            with open(factor_file, 'w') as f:
                json.dump(factors, f, indent=2)
        
        # Return metadata
        metadata = {
            "file": job.path.name,
            "ticker": job.ticker,
            "sector": job.sector,
            "method": result.method,
            "confidence": result.confidence,
            "text_length": result.text_len,
            "subsections_found": list(k for k, v in result.subsections.items() if v),
            "output_files": {
                "clean": str(clean_file),
                "structured": str(struct_file)
            },
            "status": "success",
            "extracted_at": datetime.now().isoformat()
        }
        
        return metadata
    
    def _add_metadata_to_html(self, html: str, job: FileJob, result: ExtractResult) -> str:
        """Add metadata tags to HTML for downstream processing"""
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Add metadata to head
        head = soup.find('head')
        if head:
            # Add metadata tags
            meta_tags = [
                ('ticker', job.ticker),
                ('sector', job.sector or 'unknown'),
                ('extraction-method', result.method),
                ('confidence', str(result.confidence)),
                ('filing-type', result.metadata.get('filing_type', 'unknown')),
                ('extracted-at', datetime.now().isoformat())
            ]
            
            for name, content in meta_tags:
                meta = soup.new_tag('meta')
                meta.attrs['name'] = name
                meta.attrs['content'] = content
                head.append(meta)
            
            # Add subsection markers if found
            if result.subsections:
                subsections_meta = soup.new_tag('meta')
                subsections_meta.attrs['name'] = 'subsections'
                subsections_meta.attrs['content'] = ','.join(
                    k for k, v in result.subsections.items() if v
                )
                head.append(subsections_meta)
        
        return str(soup)
    
    def _extract_factors(self, result: ExtractResult) -> Dict:
        """Extract factors for Phase 2 processing"""
        
        factors = {
            "extraction_metadata": {
                "method": result.method,
                "confidence": result.confidence,
                "filing_type": result.metadata.get('filing_type', 'unknown')
            },
            "subsections": result.subsections,
            "text_statistics": {
                "total_length": result.text_len,
                "estimated_words": result.text_len // 5  # Rough estimate
            }
        }
        
        # Parse HTML to extract more detailed factors
        soup = BeautifulSoup(result.html, 'html.parser')
        
        # Count tables (often contain key metrics)
        factors["structure"] = {
            "tables": len(soup.find_all('table')),
            "headers": len(soup.find_all(['h1', 'h2', 'h3', 'h4'])),
            "paragraphs": len(soup.find_all('p'))
        }
        
        return factors

# -------------------------- Main Processing --------------------------

def find_sec_files(in_root: Path, tickers_filter: Optional[List[str]] = None) -> List[FileJob]:
    """
    Find all SEC filing files. Supports two layouts:
    - Nested: {in_root}/{TICKER}/10-K/*.html and .../10-Q/*.html (plain HTML)
    - Flat:    {in_root}/{TICKER}/*.html.gz (gzipped, original)

    If tickers_filter is provided (e.g. ["AAL"]), only those ticker folders are processed.
    """
    jobs: List[FileJob] = []

    sector_map: Dict[str, str] = {}
    sector_file = in_root / "ticker_sectors.json"
    if sector_file.exists():
        with open(sector_file, encoding="utf-8") as f:
            sector_map = json.load(f)

    ticker_set = {t.strip().upper() for t in tickers_filter} if tickers_filter else None

    for ticker_dir in sorted(in_root.iterdir()):
        if not ticker_dir.is_dir() or ticker_dir.name.startswith("."):
            continue

        ticker = ticker_dir.name
        if ticker_set and ticker.upper() not in ticker_set:
            continue
        sector = sector_map.get(ticker)

        # Prefer nested layout: Data/{TICKER}/10-K/*.html, 10-Q/*.html
        has_nested = (ticker_dir / "10-K").is_dir() or (ticker_dir / "10-Q").is_dir()
        if has_nested:
            for subdir in ("10-K", "10-Q"):
                form_dir = ticker_dir / subdir
                if form_dir.is_dir():
                    for file_path in sorted(form_dir.glob("*.html")):
                        jobs.append(FileJob(path=file_path, ticker=ticker, sector=sector))
        else:
            # Fallback: flat layout with gzipped files
            for pattern in ["*10-K*.html.gz", "*10-Q*.html.gz", "*10K*.html.gz", "*10Q*.html.gz"]:
                for file_path in ticker_dir.glob(pattern):
                    jobs.append(FileJob(path=file_path, ticker=ticker, sector=sector))

    return jobs

def process_file(job: FileJob, extractor: EnhancedMDAExtractor, writer: OutputWriter, overwrite: bool = False) -> Dict:
    """Process single filing"""
    
    try:
        # Check if already processed
        stem = job.path.stem
        clean_file = writer.dir_html / f"{stem}_mda.html"
        
        if clean_file.exists() and not overwrite:
            return {"file": job.path.name, "ticker": job.ticker, "status": "skipped"}

        # Read HTML (plain .html or gzipped .html.gz)
        if job.path.suffix == ".gz" or str(job.path).endswith(".html.gz"):
            with gzip.open(job.path, "rt", encoding="utf-8", errors="ignore") as f:
                html = f.read()
        else:
            with open(job.path, "rt", encoding="utf-8", errors="ignore") as f:
                html = f.read()
        
        # Extract MD&A
        result = extractor.extract(html, job.path.name, job.sector)
        
        if result:
            # Write results
            metadata = writer.write_result(job, result)
            return metadata
        else:
            return {
                "file": job.path.name,
                "ticker": job.ticker,
                "status": "extraction_failed"
            }
    
    except Exception as e:
        LOG.error(f"Error processing {job.path}: {e}")
        return {
            "file": job.path.name,
            "ticker": job.ticker,
            "status": "error",
            "error": str(e)
        }

def main():
    parser = argparse.ArgumentParser(description="Enhanced SEC MD&A Extractor")
    parser.add_argument("--in_root", type=str, default="sec_data", help="Input directory")
    parser.add_argument("--out_root", type=str, default="sec_data/mda_output", help="Output directory")
    parser.add_argument("--mode", choices=["fast", "balanced", "accurate"], default="accurate",
                       help="Extraction mode")
    parser.add_argument("--workers", type=int, default=16, help="Number of parallel workers")
    parser.add_argument("--min_content", type=int, default=3000,
                       help="Minimum characters before checking end patterns")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing files")
    parser.add_argument("--limit", type=int, help="Limit number of files to process")
    parser.add_argument("--tickers", type=str, help="Comma-separated tickers to process only (e.g. AAL or AAL,ALK,CAT). Default: all")
    
    args = parser.parse_args()
    
    # Setup
    in_root = Path(args.in_root)
    out_root = Path(args.out_root)
    writer = OutputWriter(out_root)
    extractor = EnhancedMDAExtractor(mode=args.mode, min_content=args.min_content)
    
    # Find files
    tickers_filter = [t.strip() for t in args.tickers.split(",") if t.strip()] if args.tickers else None
    jobs = find_sec_files(in_root, tickers_filter=tickers_filter)
    if not jobs:
        LOG.warning("No SEC files found")
        return
    
    if args.limit:
        jobs = jobs[:args.limit]
    
    LOG.info(f"Found {len(jobs)} files to process")
    LOG.info(f"Mode: {args.mode}, Workers: {args.workers}")
    
    # Process files
    results = []
    stats = defaultdict(int)
    
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(process_file, job, extractor, writer, args.overwrite): job
            for job in jobs
        }
        
        with tqdm(total=len(jobs), desc="Extracting MD&A") as pbar:
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                
                status = result.get("status", "unknown")
                stats[status] += 1
                
                pbar.update(1)
                pbar.set_postfix(**stats)
    
    # Save metadata
    metadata_file = writer.dir_meta / f"extraction_metadata_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
    with open(metadata_file, "w") as f:
        for result in results:
            f.write(json.dumps(result) + "\n")
    
    # Save summary statistics
    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_files": len(results),
        "statistics": dict(stats),
        "extraction_methods": dict(extractor.stats),
        "success_rate": stats["success"] / len(results) * 100 if results else 0
    }
    
    summary_file = writer.dir_meta / f"extraction_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2)
    
    # Print summary
    total = len(results)
    if total > 0:
        LOG.info("="*60)
        LOG.info("EXTRACTION COMPLETE")
        LOG.info("="*60)
        LOG.info(f"Total files: {total}")
        LOG.info(f"Success: {stats['success']} ({stats['success']/total*100:.1f}%)")
        LOG.info(f"Failed: {stats['extraction_failed']}")
        LOG.info(f"Skipped: {stats['skipped']}")
        LOG.info(f"Errors: {stats['error']}")
        LOG.info(f"Extraction methods used: {dict(extractor.stats)}")
        LOG.info(f"Metadata saved to: {metadata_file}")
        LOG.info(f"Summary saved to: {summary_file}")

if __name__ == "__main__":
    main()