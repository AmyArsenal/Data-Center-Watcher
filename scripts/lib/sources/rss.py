"""Generic RSS / Atom adapter (outlet news, FERC filings, CourtListener dockets).

Uses feedparser which tolerates malformed XML, redirects, and Atom variants.
Each feed entry gets a `source` tag (e.g. "rss-dcd") and platform label.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any

import feedparser

log = logging.getLogger(__name__)

USER_AGENT = "DataCenterWatcher/0.2 (+https://github.com/)"
TIMEOUT = 15

# Each feed: (id, url, platform, needs_dc_filter)
# `needs_dc_filter=True` means the feed is broad and we'll drop entries that
# don't mention "data center" via the relevance score.
FEEDS: list[tuple[str, str, str, bool]] = [
    ("rss-dcd",          "https://www.datacenterdynamics.com/en/rss/",                 "news",  False),
    ("rss-dck",          "https://www.datacenterknowledge.com/rss.xml",                "news",  False),
    ("rss-utilitydive",  "https://www.utilitydive.com/feeds/news/",                    "news",  True),
    ("rss-arstechnica",  "https://feeds.arstechnica.com/arstechnica/index/",           "news",  True),
    ("rss-rto-insider",  "https://www.rtoinsider.com/feed/",                           "news",  True),
    ("rss-latitude",     "https://www.latitudemedia.com/feed",                         "news",  True),
    ("rss-canary",       "https://www.canarymedia.com/feed",                           "news",  True),
    ("rss-court-dc",
        "https://www.courtlistener.com/feed/search/?q=%22data+center%22&type=o",
        "legal", False),
]


def _parse(feed_id: str, url: str, platform: str, needs_filter: bool) -> list[dict]:
    parsed = feedparser.parse(url, agent=USER_AGENT, request_headers={"User-Agent": USER_AGENT})
    if parsed.bozo and not parsed.entries:
        log.warning("[%s] parse error, 0 entries: %s", feed_id, parsed.get("bozo_exception"))
        return []

    feed_meta = parsed.get("feed") or {}
    source_name = feed_meta.get("title") or feed_id
    out: list[dict] = []

    for e in parsed.entries[:50]:  # most feeds are smaller; cap as a floor
        title = (e.get("title") or "").strip()
        link  = e.get("link") or ""
        if not title or not link:
            continue

        date = _entry_date(e)
        snippet = _clean_snippet(e.get("summary") or "")

        out.append({
            "headline":      title,
            "snippet":       snippet[:500] or None,
            "url":           link,
            "source":        feed_id,
            "source_tier":   "fast",
            "source_domain": _extract_domain(link),
            "source_name":   source_name,
            "date":          date,
            "platform":      platform,
            "platform_metadata": {
                "rss_id":     e.get("id") or link,
                "rss_author": e.get("author"),
                "rss_needs_dc_filter": needs_filter,
            },
        })
    log.info("[%s] %d entries", feed_id, len(out))
    return out


def fetch(max_workers: int = 6) -> list[dict]:
    out: list[dict] = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {
            ex.submit(_parse, fid, url, plat, nf): fid
            for fid, url, plat, nf in FEEDS
        }
        for fut in as_completed(futs):
            try:
                out.extend(fut.result())
            except Exception as e:
                log.warning("[%s] unhandled: %s", futs[fut], e)
    return out


def _entry_date(e: Any) -> str | None:
    """feedparser normalizes dates into `published_parsed` / `updated_parsed`."""
    for key in ("published_parsed", "updated_parsed"):
        t = e.get(key)
        if t:
            try:
                return datetime(*t[:6]).strftime("%Y-%m-%d")
            except Exception:
                pass
    return None


def _clean_snippet(html: str) -> str:
    """Strip tags without pulling in BeautifulSoup. Cheap and good enough."""
    import re
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extract_domain(url: str) -> str | None:
    try:
        from urllib.parse import urlparse
        host = urlparse(url).hostname or ""
        if host.startswith("www."):
            host = host[4:]
        return host or None
    except Exception:
        return None
