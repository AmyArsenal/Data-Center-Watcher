#!/usr/bin/env python3
"""Backfill existing data into the new `actions` table.

Sources we can convert RIGHT NOW (no new APIs / no new keys):
  - events  (events table)  → actions with origin='news' / 'social' / etc.
  - bills   (bills  table)  → actions with origin='openstates'

The richer fields (project economics, opposition groups, petition data)
stay null for now — those come from the future research agent + manual
form submissions. We're populating the *structure* and the *taxonomy*
density today.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from lib.actions import (   # noqa: E402
    classify_action_type, classify_issues, derive_community_outcome,
    derive_tier, infer_authority, infer_scope, upsert,
)
from lib.schema import migrate     # noqa: E402

DB_PATH = ROOT / "data" / "news.db"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("migrate")


def _slugify_id(prefix: str, *parts: str) -> str:
    raw = "-".join(p for p in parts if p)
    raw = re.sub(r"[^a-zA-Z0-9_-]+", "-", raw).strip("-").lower()
    return f"{prefix}:{raw}"[:160]


def _origin_for_event(e: dict) -> str:
    """Map the event's source/platform to a coarser 'origin' for the actions
    table. Mirrors datacentertracker.org's data_source field semantics."""
    src      = (e.get("source")   or "").lower()
    platform = (e.get("platform") or "").lower()
    if src in ("seed", "manual"):                            return "manual"
    if src == "x" or platform == "x":                        return "social"
    if src == "polymarket" or platform == "polymarket":      return "market"
    if src == "youtube"    or platform == "youtube":         return "social"
    if src in ("tiktok", "instagram", "threads"):            return "social"
    if src == "reddit"     or platform == "reddit":          return "social"
    if src.startswith("rss-court") or platform == "legal":   return "court"
    if src.startswith("rss-")      or platform == "news":    return "news"
    if src == "gdelt":                                       return "news"
    return "news"


def _convert_event(e: dict) -> dict:
    """Map an `events` row to an `actions` row."""
    title    = e.get("headline") or ""
    summary  = e.get("snippet") or e.get("headline") or ""
    state    = e.get("state") or "US"
    city     = e.get("city")
    category = e.get("category")

    issues       = classify_issues(title, summary)
    action_types = classify_action_type(title, summary)
    authority    = infer_authority(title, summary)
    scope        = infer_scope(state, authority, jurisdiction=city)
    outcome      = derive_community_outcome(category, status=None)
    tier, reason = derive_tier(category, summary)
    origin       = _origin_for_event(e)

    # Sources column: prefer the event URL if present, else build from source_name
    sources = []
    if e.get("url"): sources.append(e["url"])

    return {
        "id":                _slugify_id(origin, e.get("id") or "", state),
        "origin":            origin,
        "state":             state,
        "county":            None,        # we don't have this on events yet
        "jurisdiction":      city or (e.get("source_name") or origin.title()),
        "lat":               None,
        "lng":               None,

        "scope":             scope,
        "action_type":       action_types,
        "authority_level":   authority,
        "date":              e.get("date") or e.get("first_seen", "")[:10],
        "status":            (category or "").replace("protested", "active"),
        "community_outcome": outcome,

        "issue_category":    issues,

        "company":           None,
        "hyperscaler":       None,
        "project_name":      None,
        "investment_million_usd":      None,
        "megawatts":                   None,
        "acreage":                     None,
        "building_sq_ft":              None,
        "water_usage_gallons_per_day": None,
        "jobs_promised":               None,

        "opposition_groups":   None,
        "opposition_website":  None,
        "opposition_facebook": None,
        "opposition_instagram":None,
        "opposition_twitter":  None,
        "petition_url":        None,
        "petition_signatures": None,

        "summary":             title if title == summary else f"{title}. {summary}".strip(". "),
        "sources":             sources,
        "data_source":         origin,
        "last_updated":        e.get("last_seen") or e.get("first_seen") or e.get("date"),

        "bill_number":         None,
        "bill_session":        None,

        "tier":                tier,
        "tier_reason":         reason,
    }


def _convert_bill(b: dict) -> dict:
    title   = b.get("title") or b.get("bill_number") or ""
    summary = b.get("summary") or title
    state   = b.get("state")
    status  = b.get("status")

    issues       = classify_issues(title, summary)
    # Bills always include the 'legislation' action type at minimum
    types = classify_action_type(title, summary)
    if "legislation" not in types: types.insert(0, "legislation")
    if "moratorium" in (b.get("tier_reason") or "") and "moratorium" not in types:
        types.insert(0, "moratorium")
    authority    = "state_legislature"
    scope        = "statewide"
    outcome      = derive_community_outcome(category=None, status=status)
    tier         = b.get("tier") or "unclear"
    tier_reason  = b.get("tier_reason") or ""

    sources = []
    if b.get("url_source"):     sources.append(b["url_source"])
    if b.get("url_openstates"): sources.append(b["url_openstates"])

    return {
        "id":                _slugify_id("openstates", b["id"].replace("openstates:", ""), state or ""),
        "origin":            "openstates",
        "state":             state,
        "county":            None,
        "jurisdiction":      f"{state} Legislature" if state else None,
        "lat":               None,
        "lng":               None,

        "scope":             scope,
        "action_type":       types,
        "authority_level":   authority,
        "date":              b.get("introduced_date") or b.get("status_date") or b.get("last_action_date"),
        "status":            status,
        "community_outcome": outcome,

        "issue_category":    issues,

        "company":           None,
        "hyperscaler":       None,
        "project_name":      None,
        "investment_million_usd":      None,
        "megawatts":                   None,
        "acreage":                     None,
        "building_sq_ft":              None,
        "water_usage_gallons_per_day": None,
        "jobs_promised":               None,

        "opposition_groups":   None,
        "opposition_website":  None,
        "opposition_facebook": None,
        "opposition_instagram":None,
        "opposition_twitter":  None,
        "petition_url":        None,
        "petition_signatures": None,

        "summary":             summary,
        "sources":             sources,
        "data_source":         "openstates",
        "last_updated":        b.get("last_seen") or b.get("status_date"),

        "bill_number":         b.get("bill_number"),
        "bill_session":        b.get("session"),

        "tier":                tier,
        "tier_reason":         tier_reason,
    }


def main() -> int:
    if not DB_PATH.exists():
        log.error("DB not found at %s", DB_PATH)
        return 1

    conn = sqlite3.connect(DB_PATH)
    migrate(conn)
    conn.row_factory = sqlite3.Row

    inserted = updated = noops = 0

    # --- Events → actions ----------------------------------------------
    rows = conn.execute("SELECT * FROM events").fetchall()
    log.info("converting %d events → actions", len(rows))
    for r in rows:
        d = dict(r)
        # Decode the JSON list fields the events table stores as strings
        for col in ("companies", "sources_seen"):
            if d.get(col):
                try: d[col] = json.loads(d[col])
                except json.JSONDecodeError: pass
        try:
            res = upsert(conn, _convert_event(d))
        except Exception as e:
            log.warning("event %s: %s", d.get("id"), e)
            continue
        if res == "inserted": inserted += 1
        elif res == "updated": updated += 1
        else: noops += 1
    conn.commit()

    # --- Bills → actions -----------------------------------------------
    rows = conn.execute("SELECT * FROM bills").fetchall()
    log.info("converting %d bills → actions", len(rows))
    for r in rows:
        d = dict(r)
        try:
            res = upsert(conn, _convert_bill(d))
        except Exception as e:
            log.warning("bill %s: %s", d.get("id"), e)
            continue
        if res == "inserted": inserted += 1
        elif res == "updated": updated += 1
        else: noops += 1
    conn.commit()

    total = conn.execute("SELECT COUNT(*) FROM actions").fetchone()[0]
    by_origin = dict(conn.execute(
        "SELECT origin, COUNT(*) FROM actions GROUP BY origin ORDER BY 2 DESC"
    ).fetchall())
    by_outcome = dict(conn.execute(
        "SELECT community_outcome, COUNT(*) FROM actions GROUP BY community_outcome"
    ).fetchall())
    by_state_count = conn.execute(
        "SELECT COUNT(DISTINCT state) FROM actions WHERE state IS NOT NULL AND state != 'US'"
    ).fetchone()[0]

    conn.close()

    log.info("✓ inserted=%d updated=%d noop=%d", inserted, updated, noops)
    log.info("✓ total actions: %d  | %d states", total, by_state_count)
    log.info("✓ by origin: %s", by_origin)
    log.info("✓ by community_outcome: %s", by_outcome)
    return 0


if __name__ == "__main__":
    sys.exit(main())
