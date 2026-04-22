"""GDELT DOC 2.0 Article List API adapter.

Free, unauthenticated, ~15-min update cycle. Docs:
  https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlencode

import requests

log = logging.getLogger(__name__)

API = "https://api.gdeltproject.org/api/v2/doc/doc"
USER_AGENT = "DataCenterWatcher/0.2 (+https://github.com/)"
TIMEOUT = 12

# US-scoped DC opposition queries. Each returns up to `maxrecords` articles
# within the timespan window. Keep <= 6 queries per run (~1s each).
QUERIES: list[str] = [
    '"data center" (moratorium OR ban OR opposition OR protest) sourcecountry:US',
    '"data center" ("city council" OR "county commission" OR "zoning") sourcecountry:US',
    '"data center" (lawsuit OR "court ruling" OR appeal) sourcecountry:US',
    '"data center" (cancelled OR canceled OR withdrawn OR rejected) sourcecountry:US',
    '"AI data center" (community OR residents OR NIMBY) sourcecountry:US',
    '(hyperscaler OR "AI campus") (opposition OR protest OR pause) sourcecountry:US',
]


def _run_query(q: str, timespan: str, maxrecords: int) -> list[dict]:
    params = {
        "query": q,
        "mode": "artlist",
        "format": "json",
        "sort": "datedesc",
        "maxrecords": maxrecords,
        "timespan": timespan,
    }
    url = f"{API}?{urlencode(params)}"
    try:
        r = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT})
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        log.warning("[gdelt] query failed (%s): %s", q[:40], e)
        return []

    out: list[dict] = []
    for art in data.get("articles", []):
        title = art.get("title") or ""
        if not title:
            continue
        out.append({
            "headline":      title.strip(),
            "url":           art.get("url"),
            "source":        "gdelt",
            "source_tier":   "fast",
            "source_domain": art.get("domain"),
            "source_name":   art.get("sourcename") or art.get("domain"),
            "date":          _gdelt_date(art.get("seendate")),
            "platform":      "news",
            "snippet":       None,
            "platform_metadata": {
                "gdelt_query":         q,
                "gdelt_language":      art.get("language"),
                "gdelt_sourcecountry": art.get("sourcecountry"),
                "gdelt_tone":          art.get("tone"),
            },
        })
    return out


def fetch(timespan: str = "6h", maxrecords: int = 75, max_workers: int = 4) -> list[dict]:
    """Parallelize across queries so one slow endpoint doesn't stall the run.

    `timespan`: '1h' | '6h' | '1d'. At 15-min cadence, 6h gives enough overlap
    to catch what a prior-run miss left behind.
    """
    out: list[dict] = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = [ex.submit(_run_query, q, timespan, maxrecords) for q in QUERIES]
        for fut in as_completed(futs):
            try:
                out.extend(fut.result())
            except Exception as e:
                log.warning("[gdelt] worker failed: %s", e)
    log.info("[gdelt] fetched %d raw articles across %d queries", len(out), len(QUERIES))
    return out


def _gdelt_date(seendate: str | None) -> str | None:
    """GDELT seendate is YYYYMMDDThhmmssZ. Normalize to ISO date."""
    if not seendate or len(seendate) < 8:
        return None
    return f"{seendate[0:4]}-{seendate[4:6]}-{seendate[6:8]}"
