"""YouTube Data API v3 search adapter.

Free within the default 10,000 units/day quota. Each search = 100 units, so
5 searches/run × 96 runs/day = 48k/day — too much. We actually keep this to
5 queries total and throttle the run cadence for this source to every 2 hrs
via `MIN_INTERVAL_MIN` checked by the orchestrator.

Returns [] silently if YOUTUBE_API_KEY is not set, so dev/CI runs without
the key still work.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

import requests

log = logging.getLogger(__name__)

API = "https://www.googleapis.com/youtube/v3/search"
TIMEOUT = 15
MIN_INTERVAL_MIN = 120  # orchestrator uses this to skip if last run was recent

QUERIES: list[str] = [
    "data center opposition community",
    "data center moratorium state",
    "city council data center vote",
    "data center protest residents",
    "AI data center cancelled",
]


def fetch(max_results: int = 10, published_after_hours: int = 24) -> list[dict]:
    key = os.environ.get("YOUTUBE_API_KEY")
    if not key:
        log.info("[youtube] YOUTUBE_API_KEY not set; skipping")
        return []

    published_after = (
        datetime.now(timezone.utc) - timedelta(hours=published_after_hours)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    out: list[dict] = []
    session = requests.Session()
    for q in QUERIES:
        params = {
            "part": "snippet",
            "type": "video",
            "q": q,
            "maxResults": max_results,
            "order": "date",
            "publishedAfter": published_after,
            "regionCode": "US",
            "relevanceLanguage": "en",
            "key": key,
        }
        try:
            r = session.get(API, params=params, timeout=TIMEOUT)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            log.warning("[youtube] query failed (%s): %s", q, e)
            continue

        for item in data.get("items", []):
            snip = item.get("snippet") or {}
            vid = (item.get("id") or {}).get("videoId")
            if not vid or not snip.get("title"):
                continue
            out.append({
                "headline":      snip["title"].strip(),
                "snippet":       (snip.get("description") or "").strip()[:400] or None,
                "url":           f"https://www.youtube.com/watch?v={vid}",
                "source":        "youtube",
                "source_tier":   "fast",
                "source_domain": "youtube.com",
                "source_name":   snip.get("channelTitle") or "YouTube",
                "date":          (snip.get("publishedAt") or "")[:10] or None,
                "platform":      "youtube",
                "platform_metadata": {
                    "yt_video_id":    vid,
                    "yt_channel_id":  snip.get("channelId"),
                    "yt_channel":     snip.get("channelTitle"),
                    "yt_query":       q,
                },
            })

    log.info("[youtube] fetched %d videos across %d queries", len(out), len(QUERIES))
    return out
