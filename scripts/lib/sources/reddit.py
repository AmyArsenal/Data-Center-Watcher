"""Reddit public JSON search adapter.

Free (60 req/min unauth). Must send a non-default User-Agent or Reddit 429s.
Docs: https://www.reddit.com/dev/api/
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import requests

log = logging.getLogger(__name__)

USER_AGENT = "DataCenterWatcher/0.2 by /u/anonymous (github.com placeholder)"
TIMEOUT = 15

# (subreddit or None = site-wide, query, time window)
QUERIES: list[tuple[str | None, str, str]] = [
    (None,            '"data center" (moratorium OR banned OR opposition)', "day"),
    (None,            '"data center" (protest OR residents OR "city council")', "day"),
    ("energy",        "data center", "week"),
    ("technology",    '"data center" (moratorium OR cancelled OR delayed)', "week"),
    ("urbanplanning", "data center", "week"),
    ("environment",   "data center opposition", "week"),
    ("PublicFreakout","data center", "month"),
    ("politics",      '"data center" moratorium', "month"),
]


def fetch(limit: int = 25) -> list[dict]:
    out: list[dict] = []
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    for sub, q, t in QUERIES:
        if sub:
            url = f"https://www.reddit.com/r/{sub}/search.json"
            params = {"q": q, "restrict_sr": 1, "sort": "new", "t": t, "limit": limit}
        else:
            url = "https://www.reddit.com/search.json"
            params = {"q": q, "sort": "new", "t": t, "limit": limit}

        try:
            r = session.get(url, params=params, timeout=TIMEOUT)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            log.warning("[reddit] query failed (sub=%s q=%s): %s", sub, q[:40], e)
            time.sleep(1.5)
            continue

        for child in data.get("data", {}).get("children", []):
            d = child.get("data") or {}
            title = d.get("title")
            if not title:
                continue
            created = d.get("created_utc")
            date = (
                datetime.fromtimestamp(created, tz=timezone.utc).strftime("%Y-%m-%d")
                if created else None
            )
            upvotes = int(d.get("ups") or 0)
            comments = int(d.get("num_comments") or 0)
            sub_name = d.get("subreddit")
            out.append({
                "headline":      title.strip(),
                "snippet":       (d.get("selftext") or "").strip()[:500] or None,
                "url":           f"https://www.reddit.com{d.get('permalink')}" if d.get("permalink") else d.get("url"),
                "source":        "reddit",
                "source_tier":   "fast",
                "source_domain": "reddit.com",
                "source_name":   f"r/{sub_name}" if sub_name else "reddit",
                "date":          date,
                "platform":      "reddit",
                "engagement_score": upvotes + comments,
                "upvotes":       upvotes,
                "comments":      comments,
                "platform_metadata": {
                    "reddit_id":        d.get("id"),
                    "reddit_subreddit": sub_name,
                    "reddit_author":    d.get("author"),
                    "reddit_over_18":   d.get("over_18"),
                    "reddit_link_url":  d.get("url"),
                },
            })
        time.sleep(0.8)  # gentle on 60-req/min limit

    log.info("[reddit] fetched %d posts across %d queries", len(out), len(QUERIES))
    return out
