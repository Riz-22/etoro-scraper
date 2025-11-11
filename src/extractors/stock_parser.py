from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

def _guess_ticker_from_title(title: str) -> Optional[str]:
    """
    Guess a stock ticker from a page title.

    Very simple heuristic:
    - Look for a pattern like "TSLA" or "AAPL" in the first part of the title.
    - Restrict to 1–5 uppercase letters.
    """
    if not title:
        return None

    # Remove anything in parentheses/brackets to avoid ISINs etc.
    cleaned = re.split(r"[\(\|\-\–]", title)[0]
    candidates = re.findall(r"\b[A-Z]{1,5}\b", cleaned)
    return candidates[0] if candidates else None

def _extract_category(soup: BeautifulSoup) -> Optional[str]:
    """
    Try to infer a category from meta tags or breadcrumb-like elements.
    """
    # meta tags like <meta name="etoro:category" content="Automotive">
    meta_category = soup.find("meta", attrs={"name": "etoro:category"})
    if meta_category and meta_category.get("content"):
        return meta_category["content"].strip()

    # Breadcrumbs like: Stocks / Automotive / TSLA
    for crumb in soup.select("nav.breadcrumb, .breadcrumb, .breadcrumbs"):
        text = " ".join(crumb.get_text(separator=" ").split())
        parts = [p for p in text.split("/") if p.strip()]
        if len(parts) >= 2:
            return parts[-2].strip()

    return None

def parse_stock_page(
    html: str,
    source_url: str,
    category: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Parse a stock/discovery page and return a list of stock-level records.

    Each record includes:
    - stock_name
    - ticker
    - category (if found)
    - source_url
    """
    soup = BeautifulSoup(html, "lxml")

    # Guess stock name: try Open Graph, then H1, then title
    stock_name = None

    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        stock_name = og_title["content"].strip()

    if not stock_name:
        h1 = soup.find("h1")
        if h1 and h1.get_text(strip=True):
            stock_name = h1.get_text(strip=True)

    if not stock_name and soup.title and soup.title.string:
        stock_name = soup.title.string.strip()

    ticker = _guess_ticker_from_title(stock_name or "")

    if category is None:
        inferred_category = _extract_category(soup)
        if inferred_category:
            category = inferred_category

    if not stock_name and not ticker:
        # This page doesn't look like a stock page, quietly return nothing.
        logging.debug("No stock signal detected on %s.", source_url)
        return []

    logging.debug(
        "Parsed stock page %s -> name=%r ticker=%r category=%r",
        source_url,
        stock_name,
        ticker,
        category,
    )

    record: Dict[str, Any] = {
        "stock_name": stock_name,
        "ticker": ticker,
        "investor_name": None,
        "investor_stats": None,
        "post_content": None,
        "comment_text": None,
        "likes_count": None,
        "post_date": None,
        "category": category,
        "source_url": source_url,
    }

    return [record]