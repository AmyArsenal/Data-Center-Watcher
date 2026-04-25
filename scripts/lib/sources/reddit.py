"""Reddit search adapter — OAuth when configured, public JSON otherwise.

GitHub Actions runners share egress IPs with bots that get aggressively
rate-limited (429s) on `reddit.com/search.json`. The fix is OAuth: when
REDDIT_CLIENT_ID + REDDIT_CLIENT_SECRET are set, we use the official API
at oauth.reddit.com which gives us 100 QPM per app instead of 60 QPM
shared with every other unauthenticated client on AWS/GitHub IPs.

Setup (one-time):
  1. https://www.reddit.com/prefs/apps  →  Create app  →  type "script"
  2. Note the client ID (under app name) + secret
  3. Set env vars locally and as GitHub Actions secrets:
       REDDIT_CLIENT_ID=...
       REDDIT_CLIENT_SECRET=...
  4. (Optional) REDDIT_USER_AGENT="datacenterwatcher/0.4 by /u/yourhandle"

Without those secrets, falls back to public JSON. Public JSON works
locally (laptop residential IP) but returns 0 in CI.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone

import requests

log = logging.getLogger(__name__)

USER_AGENT = os.environ.get(
    "REDDIT_USER_AGENT",
    "DataCenterWatcher/0.4 (+https://github.com/AmyArsenal/Data-Center-Watcher)",
)
TIMEOUT = 15
_OAUTH_TOKEN_CACHE: dict[str, object] = {}   # {token, expires_at}


def _get_oauth_token() -> str | None:
    """Fetch an app-only OAuth token if REDDIT_CLIENT_ID/SECRET are set.
    Cached for the token's lifetime (typically 1 hour)."""
    now = time.time()
    cached = _OAUTH_TOKEN_CACHE.get("token")
    expires = _OAUTH_TOKEN_CACHE.get("expires_at", 0)
    if cached and now < expires:
        return cached  # type: ignore[return-value]

    cid    = os.environ.get("REDDIT_CLIENT_ID")
    secret = os.environ.get("REDDIT_CLIENT_SECRET")
    if not (cid and secret):
        return None

    try:
        r = requests.post(
            "https://www.reddit.com/api/v1/access_token",
            auth=(cid, secret),
            data={"grant_type": "client_credentials"},
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        log.warning("[reddit] OAuth token fetch failed: %s — falling back to public JSON", e)
        return None

    token = data.get("access_token")
    if not token:
        return None
    _OAUTH_TOKEN_CACHE["token"]      = token
    _OAUTH_TOKEN_CACHE["expires_at"] = now + max(60, int(data.get("expires_in", 3600)) - 60)
    log.info("[reddit] OAuth token acquired (expires in %ds)", int(data.get("expires_in", 3600)))
    return token

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
    """Hits oauth.reddit.com when REDDIT_CLIENT_ID/SECRET are set, falls back
    to public reddit.com JSON otherwise. OAuth path works in CI; public path
    is reliable only on residential IPs."""
    out: list[dict] = []
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    token = _get_oauth_token()
    if token:
        host = "https://oauth.reddit.com"
        session.headers["Authorization"] = f"bearer {token}"
        log.info("[reddit] using OAuth (CI-safe)")
    else:
        host = "https://www.reddit.com"
        log.info("[reddit] using public JSON (will return 0 in CI — set REDDIT_CLIENT_ID/SECRET)")

    for sub, q, t in QUERIES:
        if sub:
            url = f"{host}/r/{sub}/search{'' if token else '.json'}"
            params = {"q": q, "restrict_sr": 1, "sort": "new", "t": t, "limit": limit}
        else:
            url = f"{host}/search{'' if token else '.json'}"
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
