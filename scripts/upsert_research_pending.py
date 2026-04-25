#!/usr/bin/env python3
"""Upsert findings from data/research_pending.json into the actions table.

Each record from the research agent (or hand-curated batch) is normalized,
given a stable origin-prefixed slug ID, and inserted via lib.actions.upsert.

This is the human-review-then-merge step in the weekly research workflow:

    1. Run scripts/research_agent.py (or do it manually with Claude Code)
    2. Review data/research_pending.json
    3. Drop any false positives by editing the file
    4. Run this script — upserts into news.db `actions` table
    5. refresh_fast.py exports actions.json + dossiers next time it runs
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from lib.actions import upsert     # noqa: E402
from lib.schema import migrate     # noqa: E402

DB_PATH      = ROOT / "data" / "news.db"
PENDING_JSON = ROOT / "data" / "research_pending.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("upsert-research")


def _slugify(*parts: str) -> str:
    raw = "-".join(p for p in parts if p)
    raw = re.sub(r"[^a-zA-Z0-9_-]+", "-", raw).strip("-").lower()
    return raw[:140] or "rec"


def _make_id(rec: dict) -> str:
    state = rec.get("state") or "us"
    juris = rec.get("jurisdiction") or rec.get("county") or "unknown"
    date  = (rec.get("date") or "").replace("-", "")[:8]
    title = (rec.get("summary") or "")[:50]
    return f"research:{_slugify(state, juris, date, title)}"


def main() -> int:
    if not PENDING_JSON.exists():
        log.error("file not found: %s", PENDING_JSON)
        return 1
    data = json.loads(PENDING_JSON.read_text())
    log.info("loaded %d candidate records", len(data))

    conn = sqlite3.connect(DB_PATH)
    migrate(conn)

    inserted = updated = noops = errors = 0
    for rec in data:
        try:
            rec.setdefault("origin", "research_agent")
            rec.setdefault("data_source", "agent_research")
            rec.setdefault("last_updated", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
            rec["id"] = _make_id(rec)

            r = upsert(conn, rec)
            if r == "inserted": inserted += 1
            elif r == "updated": updated += 1
            else: noops += 1
        except Exception as e:
            log.warning("record failed (%s): %s", rec.get("state"), e)
            errors += 1

    conn.commit()

    total = conn.execute("SELECT COUNT(*) FROM actions").fetchone()[0]
    by_state = conn.execute(
        "SELECT COUNT(DISTINCT state) FROM actions WHERE state IS NOT NULL AND state != 'US'"
    ).fetchone()[0]
    by_origin = dict(conn.execute(
        "SELECT origin, COUNT(*) FROM actions GROUP BY origin ORDER BY 2 DESC"
    ).fetchall())
    conn.close()

    log.info("✓ inserted=%d updated=%d noop=%d errors=%d", inserted, updated, noops, errors)
    log.info("✓ total actions: %d  | %d states", total, by_state)
    log.info("✓ by origin: %s", by_origin)
    return 0


if __name__ == "__main__":
    sys.exit(main())
