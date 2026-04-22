"""SQLite schema + forward-only migrations for data/news.db.

The base table was introduced in build_news_db.py; this module owns the
additive columns needed by the fast tier (cross-source dedup, source tiering,
richer geo/entity extraction) without renaming or dropping anything the
existing ingesters depend on.
"""

from __future__ import annotations

import sqlite3

BASE_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  id TEXT PRIMARY KEY,
  state TEXT NOT NULL,
  city TEXT,
  category TEXT NOT NULL,
  headline TEXT NOT NULL,
  source_domain TEXT,
  source_name TEXT,
  url TEXT,
  date TEXT NOT NULL,
  platform TEXT NOT NULL,
  engagement_score INTEGER DEFAULT 0,
  upvotes INTEGER,
  comments INTEGER,
  views INTEGER,
  likes INTEGER,
  sentiment TEXT,
  companies TEXT,
  first_seen TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_events_state    ON events(state);
CREATE INDEX IF NOT EXISTS idx_events_platform ON events(platform);
CREATE INDEX IF NOT EXISTS idx_events_date     ON events(date);
CREATE INDEX IF NOT EXISTS idx_events_category ON events(category);
"""

# (column_name, DDL fragment after the name) — added only if not present.
_ADDITIONS: list[tuple[str, str]] = [
    ("url_hash",          "TEXT"),
    ("content_hash",      "TEXT"),
    ("source",            "TEXT"),
    ("source_tier",       "TEXT DEFAULT 'manual'"),
    ("sources_seen",      "TEXT"),           # JSON array of source strings
    ("snippet",           "TEXT"),
    ("last_seen",         "TEXT"),
    ("counties",          "TEXT"),           # JSON array
    ("dollars_mentioned", "INTEGER"),
    ("relevance_score",   "REAL DEFAULT 1.0"),
    ("topics",            "TEXT"),           # JSON array
    ("ferc_dockets",      "TEXT"),           # JSON array
    ("platform_metadata", "TEXT"),           # JSON blob
]

_EXTRA_INDEXES = [
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_events_url_hash     ON events(url_hash) WHERE url_hash IS NOT NULL",
    "CREATE INDEX        IF NOT EXISTS idx_events_content_hash ON events(content_hash)",
    "CREATE INDEX        IF NOT EXISTS idx_events_first_seen   ON events(first_seen DESC)",
    "CREATE INDEX        IF NOT EXISTS idx_events_last_seen    ON events(last_seen DESC)",
    "CREATE INDEX        IF NOT EXISTS idx_events_source       ON events(source)",
    "CREATE INDEX        IF NOT EXISTS idx_events_source_tier  ON events(source_tier)",
]


def _existing_columns(conn: sqlite3.Connection) -> set[str]:
    return {row[1] for row in conn.execute("PRAGMA table_info(events)").fetchall()}


def migrate(conn: sqlite3.Connection) -> list[str]:
    """Apply base schema + all additive migrations. Returns the list of
    migrations that were actually applied this call (empty if up-to-date)."""
    conn.executescript(BASE_SCHEMA)

    applied: list[str] = []
    have = _existing_columns(conn)
    for col, ddl in _ADDITIONS:
        if col in have:
            continue
        conn.execute(f"ALTER TABLE events ADD COLUMN {col} {ddl}")
        applied.append(f"+col {col}")

    for idx_sql in _EXTRA_INDEXES:
        conn.execute(idx_sql)

    conn.commit()
    return applied
