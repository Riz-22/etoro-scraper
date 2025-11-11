from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

def _parse_risk_score(block_text: str) -> Optional[int]:
    """
    Heuristic to extract a risk score like 'Risk score 4' or 'Risk: 7/10'.
    """
    if not block_text:
        return None

    match = re.search(r"risk\s*score\s*(\d+)", block_text, flags=re.IGNORECASE)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None

    match = re.search(r"risk[^0-9]*(\d+)\s*/\s*10", block_text, flags=re.IGNORECASE)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None

    return None

def _parse_return_12m(block_text: str) -> Optional[float]:
    """
    Heuristic to extract a 12 month return like 'Return (12M) 24.6%' or '12m: +14%'.
    """
    if not block_text:
        return None

    match = re.search(
        r"(?:12m|12\s*months|1y)[^0-9\-+]*([\-+]?\d+(?:\.\d+)?)\s*%",
        block_text,
        flags=re.IGNORECASE,
    )
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None

def _build_stats(block_text: str) -> Optional[Dict[str, Any]]:
    risk = _parse_risk_score(block_text)
    ret = _parse_return_12m(block_text)

    stats: Dict[str, Any] = {}
    if ret is not None:
        stats["return_12m"] = ret
    if risk is not None:
        stats["risk_score"] = risk
    return stats or None

def parse_investor_page(
    html: str,
    source_url: str,
    category: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Parse investor profile cards on a page.

    Investor cards are loosely defined as:
    - An element with a class containing 'user' or 'investor'
    - With a nested element containing the name
    - And some statistics text
    """
    soup = BeautifulSoup(html, "lxml")
    records: List[Dict[str, Any]] = []

    # Common structures: cards with user info
    possible_cards = soup.select(
        "[class*='user'], [class*='investor'], [data-etoro-user], [data-user-card]"
    )

    for card in possible_cards:
        text = card.get_text(separator=" ", strip=True)
        if not text:
            continue

        # Name heuristics: look for bold or strong or header inside card
        name_elem = (
            card.find("strong")
            or card.find("b")
            or card.find("h2")
            or card.find("h3")
            or card.find("span", attrs={"class": lambda c: c and "name" in c})
        )

        investor_name = name_elem.get_text(strip=True) if name_elem else None
        if not investor_name:
            # fallback: first 'wordish' segment of the card
            investor_name = text.split("  ")[0].strip().split(" ")[0].strip()

        stats = _build_stats(text)

        logging.debug(
            "Parsed investor card on %s -> name=%r stats=%s",
            source_url,
            investor_name,
            json.dumps(stats or {}, ensure_ascii=False),
        )

        record: Dict[str, Any] = {
            "stock_name": None,
            "ticker": None,
            "investor_name": investor_name,
            "investor_stats": stats,
            "post_content": None,
            "comment_text": None,
            "likes_count": None,
            "post_date": None,
            "category": category,
            "source_url": source_url,
        }
        records.append(record)

    if not records:
        logging.debug("No investor cards detected on %s.", source_url)

    return records