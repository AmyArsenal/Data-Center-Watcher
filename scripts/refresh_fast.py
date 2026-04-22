#!/usr/bin/env python3
"""Fast-tier refresh: runs every ~15 min via GitHub Actions.

Pipeline:
  1. Fetch in parallel from GDELT / Reddit / RSS (and YouTube if keyed)
  2. Enrich each event: state, category, companies, relevance
  3. Drop sub-threshold relevance
  4. Upsert into data/news.db (cross-source dedup + sources_seen union)
  5. Export data/news.json + data/meta.json

Safe to run repeatedly. Errors in one source don't block the others.
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from lib.classify import (                # noqa: E402
    classify_category, detect_state, extract_companies, relevance_score,
)
from lib.events import upsert              # noqa: E402
from lib.export import export_news, read_meta, write_meta  # noqa: E402
from lib.schema import migrate             # noqa: E402
from lib.sources import gdelt, reddit, rss, youtube  # noqa: E402

DB_PATH = ROOT / "data" / "news.db"
NEWS_JSON = ROOT / "data" / "news.json"
META_JSON = ROOT / "data" / "meta.json"

MIN_RELEVANCE = 0.30


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fetch_all(skip_youtube: bool) -> dict[str, list[dict]]:
    """Fan out across sources in parallel threads; return {source: [events]}."""
    jobs: dict[str, callable] = {
        "gdelt":   gdelt.fetch,
        "reddit":  reddit.fetch,
        "rss":     rss.fetch,
    }
    if not skip_youtube:
        jobs["youtube"] = youtube.fetch

    results: dict[str, list[dict]] = {}
    with ThreadPoolExecutor(max_workers=len(jobs)) as ex:
        futs = {ex.submit(fn): name for name, fn in jobs.items()}
        for fut in as_completed(futs):
            name = futs[fut]
            try:
                results[name] = fut.result() or []
            except Exception as e:
                logging.warning("[%s] fetch failed: %s", name, e)
                results[name] = []
    return results


def _enrich(event: dict) -> dict:
    """Populate state/city/category/companies/relevance from the headline+snippet."""
    blob = f"{event.get('headline','')} {event.get('snippet') or ''}"
    state, city = detect_state(blob)
    event.setdefault("state", state)
    event.setdefault("city",  city)
    event["category"] = classify_category(event.get("headline") or "")
    companies = extract_companies(blob)
    if companies:
        event["companies"] = companies
    event["relevance_score"] = relevance_score(event.get("headline"), event.get("snippet"))
    return event


def run(skip_youtube: bool = False, min_relevance: float = MIN_RELEVANCE) -> int:
    t0 = time.time()
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    logging.info("refreshing %s", DB_PATH.name)
    conn = sqlite3.connect(DB_PATH)
    migrate(conn)

    fetched = _fetch_all(skip_youtube=skip_youtube)
    raw_counts = {k: len(v) for k, v in fetched.items()}
    logging.info("fetched raw: %s", raw_counts)

    seen: set[str] = set()  # in-run url-based dedup; cross-run dedup is in upsert()
    inserted = 0
    updated = 0
    dropped = 0
    by_source: dict[str, int] = {}

    for source_name, items in fetched.items():
        for raw in items:
            if not raw.get("headline"):
                dropped += 1
                continue
            e = _enrich(raw)
            if e["relevance_score"] < min_relevance:
                dropped += 1
                continue
            key = e.get("url") or e.get("headline")
            if key in seen:
                continue
            seen.add(key)

            result = upsert(conn, e)
            if result == "inserted":
                inserted += 1
            else:
                updated += 1
            src = e.get("source") or source_name
            by_source[src] = by_source.get(src, 0) + 1
        conn.commit()

    conn.close()

    count, counts_by_source = export_news(DB_PATH, NEWS_JSON)

    prev_meta = read_meta(META_JSON)
    tier_ts = dict(prev_meta.get("tier_timestamps") or {})
    tier_ts["fast"] = _utcnow_iso()

    write_meta(META_JSON, tier_ts, counts_by_source, {
        "last_run_seconds": round(time.time() - t0, 2),
        "raw_fetched":      raw_counts,
        "inserted":         inserted,
        "updated":          updated,
        "dropped_irrelevant": dropped,
        "accepted_by_source_this_run": by_source,
    })

    logging.info(
        "done in %.1fs | inserted=%d updated=%d dropped=%d | news.json items=%d",
        time.time() - t0, inserted, updated, dropped, count,
    )
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--skip-youtube", action="store_true",
                   help="skip YouTube Data API even if key is set")
    p.add_argument("--min-relevance", type=float, default=MIN_RELEVANCE)
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()
    _setup_logging(args.verbose)
    return run(skip_youtube=args.skip_youtube, min_relevance=args.min_relevance)


if __name__ == "__main__":
    sys.exit(main())
