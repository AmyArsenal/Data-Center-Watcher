#!/usr/bin/env python3
"""Hourly bills refresh: OpenStates → classification → data/bills.json.

Pipeline:
  1. Pull bills updated since last successful run (incremental)
  2. Classify each (restrictive | protective | supportive | unclear)
  3. Upsert into data/news.db `bills` table
  4. Export data/bills.json (items + per-state aggregate for the map)
  5. Update data/meta.json with bills-tier timestamp

Safe to run repeatedly. Without OPENSTATES_API_KEY, exits 0 with no-op
(so CI doesn't fail in forks / dev environments).
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from lib.bills  import aggregate_by_state, upsert   # noqa: E402
from lib.export import read_meta, write_meta        # noqa: E402
from lib.schema import migrate                      # noqa: E402
from lib.sources import openstates                  # noqa: E402

DB_PATH   = ROOT / "data" / "news.db"
BILLS_JSON = ROOT / "data" / "bills.json"
META_JSON  = ROOT / "data" / "meta.json"


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _incremental_window(meta: dict) -> str | None:
    """Return ISO timestamp to use for OpenStates `updated_since`.

    If we've run before, ask only for bills changed since ~30 min before the
    last run (slight overlap = belt-and-suspenders). If it's the first run,
    return None so we get a full catalog dump.
    """
    prev = (meta.get("tier_timestamps") or {}).get("bills")
    if not prev:
        return None
    try:
        dt = datetime.fromisoformat(prev.replace("Z", "+00:00"))
    except ValueError:
        return None
    window_start = dt - timedelta(minutes=30)
    return window_start.strftime("%Y-%m-%dT%H:%M:%SZ")


def _export_bills_json(conn: sqlite3.Connection, out_path: Path) -> dict:
    """Write the full bills.json the frontend consumes. Returns summary stats."""
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT * FROM bills
           WHERE status != 'dead' AND tier IS NOT NULL
           ORDER BY
             CASE tier
               WHEN 'restrictive' THEN 1
               WHEN 'protective'  THEN 2
               WHEN 'supportive'  THEN 3
               ELSE 4 END,
             CASE status
               WHEN 'enacted'          THEN 1
               WHEN 'passed-both'      THEN 2
               WHEN 'passed-upper'     THEN 3
               WHEN 'passed-lower'     THEN 3
               WHEN 'passed-committee' THEN 4
               WHEN 'in-committee'     THEN 5
               WHEN 'introduced'       THEN 6
               ELSE 7 END,
             status_date DESC"""
    ).fetchall()

    def _parse_json(s):
        if not s: return []
        try: return json.loads(s)
        except json.JSONDecodeError: return []

    items = []
    for r in rows:
        d = dict(r)
        d["sponsors"] = _parse_json(d.get("sponsors"))
        d["subjects"] = _parse_json(d.get("subjects"))
        d["keywords"] = _parse_json(d.get("keywords"))
        items.append(d)

    by_state = aggregate_by_state(conn)

    payload = {
        "generated_at": _utcnow_iso(),
        "count":        len(items),
        "items":        items,
        "by_state":     by_state,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    return {"count": len(items), "states_with_bills": len(by_state)}


def run(full: bool = False, states: list[str] | None = None) -> int:
    t0 = time.time()
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    logging.info("refreshing bills via OpenStates")
    conn = sqlite3.connect(DB_PATH)
    migrate(conn)

    prev_meta = read_meta(META_JSON)
    updated_since = None if full else _incremental_window(prev_meta)
    if updated_since:
        logging.info("incremental since %s", updated_since)
    else:
        logging.info("full refresh (no prior bills tier timestamp)")

    raw = openstates.fetch(states=states, updated_since=updated_since)

    inserted = updated = noops = 0
    for bill in raw:
        try:
            r = upsert(conn, bill)
        except Exception as e:
            logging.warning("upsert failed for %s: %s", bill.get("id"), e)
            continue
        if r == "inserted":   inserted += 1
        elif r == "updated":  updated += 1
        else:                 noops += 1
    conn.commit()

    stats = _export_bills_json(conn, BILLS_JSON)

    tier_ts = dict(prev_meta.get("tier_timestamps") or {})
    tier_ts["bills"] = _utcnow_iso()
    write_meta(META_JSON, tier_ts, prev_meta.get("counts_by_source") or {}, {
        **((prev_meta.get("run_stats") or {})),  # preserve other-tier stats
        "bills_last_run_seconds": round(time.time() - t0, 2),
        "bills_raw_fetched":       len(raw),
        "bills_inserted":          inserted,
        "bills_updated":           updated,
        "bills_noop":              noops,
        "bills_total_in_json":     stats["count"],
        "bills_states_with_bills": stats["states_with_bills"],
    })

    conn.close()
    logging.info(
        "done in %.1fs | raw=%d inserted=%d updated=%d noop=%d | bills.json items=%d states=%d",
        time.time() - t0, len(raw), inserted, updated, noops,
        stats["count"], stats["states_with_bills"],
    )
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--full", action="store_true", help="ignore incremental window; full refresh")
    p.add_argument("--state", action="append", dest="states", help="restrict to state(s); repeat flag")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()
    _setup_logging(args.verbose)
    return run(full=args.full, states=args.states)


if __name__ == "__main__":
    sys.exit(main())
