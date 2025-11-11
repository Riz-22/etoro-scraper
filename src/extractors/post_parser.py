from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

def _parse_likes(text: str) -> Optional[int]:
    """
    Try to parse a likes count from a string like '153 likes' or '♥ 42'.
    """
    text = text.strip()
    if not text:
        return None

    num = ""
    for ch in text:
        if ch.isdigit():
            num += ch
        elif num:
            break

    if not num:
        return None

    try:
        return int(num)
    except ValueError:
        return None

def _parse_timestamp(element: Any) -> Optional[str]:
    """
    Attempt to extract an ISO timestamp from datetime attributes or text.
    """
    if not element:
        return None

    # <time datetime="2025-03-22T14:30:00Z">...</time>
    if element.has_attr("datetime"):
        val = element.get("datetime")
        if isinstance(val, str) and val.strip():
            try:
                # Validate it's at least parseable
                datetime.fromisoformat(val.replace("Z", "+00:00"))
                return val
            except ValueError:
                pass

    text = element.get_text(strip=True)
    if not text:
        return None

    # If it's already an ISO-ish string, trust it
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(text, fmt)
            if fmt == "%Y-%m-%d":
                dt = datetime(dt.year, dt.month, dt.day)
            return dt.isoformat() + "Z"
        except ValueError:
            continue

    return None

def parse_posts_page(
    html: str,
    source_url: str,
    category: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Parse posts and associated comments from a page.

    A "post" is loosely defined as any element with a class containing 'post',
    'feed-item', or 'status'. Comments are nested elements with 'comment' in their class.
    """
    soup = BeautifulSoup(html, "lxml")
    records: List[Dict[str, Any]] = []

    post_selectors = [
        "[class*='post']",
        "[class*='feed-item']",
        "[class*='status']",
    ]
    post_elements = []
    for sel in post_selectors:
        post_elements.extend(soup.select(sel))

    # Remove duplicates while preserving order
    seen_ids = set()
    uniq_posts = []
    for elem in post_elements:
        key = id(elem)
        if key in seen_ids:
            continue
        seen_ids.add(key)
        uniq_posts.append(elem)

    for post in uniq_posts:
        post_text = post.get_text(separator=" ", strip=True)
        if not post_text:
            continue

        # Post headline/body - prefer dedicated elements if present
        body_elem = (
            post.find(attrs={"class": lambda c: c and "content" in c})
            or post.find("p")
            or post
        )
        post_body = body_elem.get_text(separator=" ", strip=True)

        # Likes
        likes_elem = post.find(
            attrs={"class": lambda c: c and ("like" in c or "reaction" in c)}
        )
        likes_count = _parse_likes(likes_elem.get_text()) if likes_elem else None

        # Timestamp
        time_elem = post.find("time") or post.find(
            attrs={"class": lambda c: c and "time" in c}
        )
        timestamp = _parse_timestamp(time_elem) if time_elem else None

        logging.debug(
            "Parsed post on %s -> text=%r likes=%r date=%r",
            source_url,
            post_body[:80] + ("..." if len(post_body) > 80 else ""),
            likes_count,
            timestamp,
        )

        # Base record for the post itself (no comment_text)
        base_record: Dict[str, Any] = {
            "stock_name": None,
            "ticker": None,
            "investor_name": None,
            "investor_stats": None,
            "post_content": post_body,
            "comment_text": None,
            "likes_count": likes_count,
            "post_date": timestamp,
            "category": category,
            "source_url": source_url,
        }
        records.append(base_record)

        # Comments nested under the post
        comment_elems = post.select("[class*='comment']")
        for comment_elem in comment_elems:
            comment_text = comment_elem.get_text(separator=" ", strip=True)
            if not comment_text or comment_text == post_body:
                continue

            comment_likes_elem = comment_elem.find(
                attrs={"class": lambda c: c and ("like" in c or "reaction" in c)}
            )
            comment_likes = (
                _parse_likes(comment_likes_elem.get_text())
                if comment_likes_elem
                else None
            )

            comment_time_elem = comment_elem.find("time")
            comment_time = (
                _parse_timestamp(comment_time_elem) if comment_time_elem else timestamp
            )

            comment_record: Dict[str, Any] = {
                "stock_name": None,
                "ticker": None,
                "investor_name": None,
                "investor_stats": None,
                "post_content": post_body,
                "comment_text": comment_text,
                "likes_count": comment_likes,
                "post_date": comment_time,
                "category": category,
                "source_url": source_url,
            }
            records.append(comment_record)

    if not records:
        logging.debug("No posts detected on %s.", source_url)

    return records