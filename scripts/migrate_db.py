#!/usr/bin/env python3
"""Apply schema migrations to data/news.db and backfill url_hash / content_hash
for existing rows.

Idempotent: safe to run repeatedly. Prints what it did.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from lib.hashing import content_hash, url_hash  # noqa: E402
from lib.schema import migrate                  # noqa: E402

DB_PATH = ROOT / "data" / "news.db"


def backfill_hashes(conn: sqlite3.Connection) -> tuple[int, int]:
    """Populate url_hash / content_hash / sources_seen / last_seen for legacy rows."""
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT id, url, headline, source, platform, sources_seen,
                  url_hash, content_hash, last_seen, first_seen, source_tier
           FROM events"""
    ).fetchall()

    url_updates = 0
    content_updates = 0
    for r in rows:
        updates: dict = {}
        if r["url"] and not r["url_hash"]:
            updates["url_hash"] = url_hash(r["url"])
        if not r["content_hash"]:
            updates["content_hash"] = content_hash(r["headline"] or "", None)
        if not r["sources_seen"]:
            src = r["source"] or r["platform"] or "seed"
            updates["sources_seen"] = f'["{src}"]'
        if not r["source_tier"]:
            updates["source_tier"] = "manual"
        if not r["last_seen"]:
            updates["last_seen"] = r["first_seen"]

        if updates:
            if "url_hash" in updates:
                url_updates += 1
            if "content_hash" in updates:
                content_updates += 1
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(
                f"UPDATE events SET {set_clause} WHERE id = ?",
                [*updates.values(), r["id"]],
            )
    conn.commit()
    return url_updates, content_updates


def main() -> None:
    if not DB_PATH.exists():
        print(f"[migrate] creating new db at {DB_PATH}")
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    applied = migrate(conn)
    if applied:
        print(f"[migrate] applied {len(applied)} change(s): {', '.join(applied)}")
    else:
        print("[migrate] schema up-to-date")

    url_n, content_n = backfill_hashes(conn)
    print(f"[backfill] url_hash: {url_n} row(s), content_hash: {content_n} row(s)")

    total = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    by_tier = conn.execute(
        "SELECT source_tier, COUNT(*) FROM events GROUP BY source_tier"
    ).fetchall()
    conn.close()
    print(f"[db] {total} total events; by tier: {dict(by_tier)}")


if __name__ == "__main__":
    main()
