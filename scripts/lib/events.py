"""Cross-source dedup + upsert for the events table.

Callers hand us a plain dict. We compute url_hash/content_hash, look for a
matching row, and either INSERT a new row or merge into the existing one
(union sources_seen, max engagement, fill-null for geo/entity fields).
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from typing import Any

from .hashing import canonicalize_url, content_hash, url_hash

# Ordering: strongest wins on tier bump during merge. `manual` is human-curated
# seed data and should never be demoted by an automated source.
_TIER_RANK = {"live": 1, "fast": 2, "deep": 3, "manual": 4}

# Fields we'll accept from callers, with their default for INSERT.
_INSERT_COLUMNS = [
    "id", "state", "city", "category", "headline",
    "source_domain", "source_name", "url", "date", "platform",
    "engagement_score", "upvotes", "comments", "views", "likes",
    "sentiment", "companies",
    "url_hash", "content_hash", "source", "source_tier", "sources_seen",
    "snippet", "last_seen", "counties", "dollars_mentioned",
    "relevance_score", "topics", "ferc_dockets", "platform_metadata",
]


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _as_json(value: Any) -> str | None:
    """Pass through strings; JSON-encode dicts/lists; treat None as None."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def _slugify(text: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return text[:60] or "event"


def _generate_id(event: dict) -> str:
    """Stable ID: prefer `{source}-{url_hash}`, else slug+date+content_hash."""
    src = event.get("source") or event.get("platform") or "evt"
    if event.get("url_hash"):
        return f"{src}-{event['url_hash']}"
    date = (event.get("date") or event.get("published_at") or "").replace("-", "")[:8]
    slug = _slugify(event.get("headline") or "")
    ch = event.get("content_hash") or ""
    return f"{src}-{slug}-{date}-{ch}"[:120]


def prepare(event: dict) -> dict:
    """Fill in url_hash/content_hash/last_seen/sources_seen/id. Pure."""
    e = dict(event)
    if e.get("url"):
        e["url"] = canonicalize_url(e["url"])
        e.setdefault("url_hash", url_hash(e["url"]))
    e.setdefault("content_hash", content_hash(e.get("headline") or "", e.get("snippet")))
    e.setdefault("last_seen", _utcnow_iso())
    e.setdefault("source_tier", "fast")
    source = e.get("source") or e.get("platform") or "unknown"
    e["source"] = source
    if "sources_seen" not in e or e["sources_seen"] is None:
        e["sources_seen"] = [source]
    e.setdefault("id", _generate_id(e))
    return e


def _find_existing(conn: sqlite3.Connection, e: dict) -> sqlite3.Row | None:
    prev = conn.row_factory
    conn.row_factory = sqlite3.Row
    try:
        if e.get("url_hash"):
            row = conn.execute(
                "SELECT * FROM events WHERE url_hash = ? LIMIT 1", (e["url_hash"],)
            ).fetchone()
            if row:
                return row
        if e.get("content_hash"):
            row = conn.execute(
                "SELECT * FROM events WHERE content_hash = ? LIMIT 1", (e["content_hash"],)
            ).fetchone()
            if row:
                return row
        return None
    finally:
        conn.row_factory = prev


def _merge_sources(existing_json: str | None, new_source: str) -> str:
    existing = json.loads(existing_json) if existing_json else []
    if new_source and new_source not in existing:
        existing.append(new_source)
    return json.dumps(existing, separators=(",", ":"))


def _merge_list(existing_json: str | None, incoming: Any) -> str | None:
    """Union for JSON-list fields (companies, counties, topics). Preserves order."""
    existing = json.loads(existing_json) if existing_json else []
    if isinstance(incoming, str):
        try:
            incoming_list = json.loads(incoming)
        except json.JSONDecodeError:
            incoming_list = [incoming]
    else:
        incoming_list = list(incoming or [])
    out = list(existing)
    for v in incoming_list:
        if v and v not in out:
            out.append(v)
    return json.dumps(out, separators=(",", ":")) if out else None


def upsert(conn: sqlite3.Connection, event: dict) -> str:
    """Insert a new event or merge into an existing dedup target.

    Returns: 'inserted' | 'updated'.
    """
    e = prepare(event)
    existing = _find_existing(conn, e)

    if existing is None:
        row = {col: None for col in _INSERT_COLUMNS}
        for col in _INSERT_COLUMNS:
            if col in e:
                row[col] = e[col]
        row["companies"]         = _as_json(row["companies"] or [])
        row["sources_seen"]      = _as_json(row["sources_seen"])
        row["counties"]          = _as_json(row["counties"])
        row["topics"]            = _as_json(row["topics"])
        row["ferc_dockets"]      = _as_json(row["ferc_dockets"])
        row["platform_metadata"] = _as_json(row["platform_metadata"])
        # Required NOT NULL defaults
        row.setdefault("state", "US")
        row["state"]    = row["state"] or "US"
        row["category"] = row["category"] or "protested"
        row["headline"] = row["headline"] or ""
        row["date"]     = row["date"] or _utcnow_iso()[:10]
        row["platform"] = row["platform"] or row["source"] or "news"
        row["engagement_score"] = int(row["engagement_score"] or 0)

        placeholders = ",".join("?" * len(_INSERT_COLUMNS))
        cols = ",".join(_INSERT_COLUMNS)
        conn.execute(
            f"INSERT INTO events ({cols}) VALUES ({placeholders})",
            [row[c] for c in _INSERT_COLUMNS],
        )
        return "inserted"

    # --- merge path ------------------------------------------------------
    updates: dict[str, Any] = {"last_seen": e["last_seen"]}

    updates["sources_seen"] = _merge_sources(existing["sources_seen"], e["source"])

    old_tier = existing["source_tier"] or "fast"
    new_tier = e["source_tier"] or "fast"
    if _TIER_RANK.get(new_tier, 0) > _TIER_RANK.get(old_tier, 0):
        updates["source_tier"] = new_tier

    incoming_eng = int(e.get("engagement_score") or 0)
    if incoming_eng > int(existing["engagement_score"] or 0):
        updates["engagement_score"] = incoming_eng

    # Fill nulls: only set if the existing row doesn't already have a value.
    for col in ("state", "city", "category", "snippet", "source_domain",
                "source_name", "sentiment", "dollars_mentioned", "url"):
        if e.get(col) and not existing[col]:
            updates[col] = e[col]

    for col in ("companies", "counties", "topics", "ferc_dockets"):
        if e.get(col):
            merged = _merge_list(existing[col], e[col])
            if merged != existing[col]:
                updates[col] = merged

    # Engagement sub-fields: take max
    for col in ("upvotes", "comments", "views", "likes"):
        incoming = e.get(col)
        if incoming is None:
            continue
        if existing[col] is None or int(incoming) > int(existing[col]):
            updates[col] = int(incoming)

    if updates:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(
            f"UPDATE events SET {set_clause} WHERE id = ?",
            [*updates.values(), existing["id"]],
        )
    return "updated"
