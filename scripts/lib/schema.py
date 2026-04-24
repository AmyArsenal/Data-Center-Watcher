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

# Community + legislative actions — the dense layer.
# Schema mirrors datacentertracker.org's fights.json (CC BY 4.0) so we can
# bulk-import their 956-record historical dataset and round-trip diffs cleanly,
# plus our developer-tier classification on top.
ACTIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS actions (
  id                       TEXT PRIMARY KEY,
  origin                   TEXT NOT NULL,         -- 'datacentertracker' | 'openstates' | 'manual'

  -- Geo
  state                    TEXT NOT NULL,
  county                   TEXT,
  jurisdiction             TEXT,
  lat                      REAL,
  lng                      REAL,

  -- Action
  scope                    TEXT,                  -- local | statewide | federal
  action_type              TEXT,                  -- JSON array
  authority_level          TEXT,                  -- county_commission, city_council, ...
  date                     TEXT,                  -- ISO YYYY-MM-DD
  status                   TEXT,                  -- procedural: active|pending|passed|...
  community_outcome        TEXT,                  -- pending|win|loss|mixed

  -- Issue (16 tags from datacentertracker.org)
  issue_category           TEXT,                  -- JSON array

  -- Project economics
  company                  TEXT,
  hyperscaler              TEXT,
  project_name             TEXT,
  investment_million_usd   REAL,
  megawatts                REAL,
  acreage                  REAL,
  building_sq_ft           REAL,
  water_usage_gallons_per_day REAL,
  jobs_promised            INTEGER,

  -- Opposition
  opposition_groups        TEXT,                  -- JSON array
  opposition_website       TEXT,
  opposition_facebook      TEXT,
  opposition_instagram     TEXT,
  opposition_twitter       TEXT,
  petition_url             TEXT,
  petition_signatures      INTEGER,

  -- Provenance
  summary                  TEXT,
  sources                  TEXT,                  -- JSON array
  data_source              TEXT,                  -- their classification
  last_updated             TEXT,
  first_seen               TEXT DEFAULT CURRENT_TIMESTAMP,

  -- Bill-specific (when origin='openstates')
  bill_number              TEXT,
  bill_session             TEXT,

  -- Our developer-tier classification (parallel to community_outcome)
  tier                     TEXT,                  -- restrictive|protective|supportive|unclear
  tier_reason              TEXT
);

CREATE INDEX IF NOT EXISTS idx_actions_state          ON actions(state);
CREATE INDEX IF NOT EXISTS idx_actions_outcome        ON actions(community_outcome);
CREATE INDEX IF NOT EXISTS idx_actions_tier           ON actions(tier);
CREATE INDEX IF NOT EXISTS idx_actions_scope          ON actions(scope);
CREATE INDEX IF NOT EXISTS idx_actions_date           ON actions(date DESC);
CREATE INDEX IF NOT EXISTS idx_actions_origin         ON actions(origin);
"""

# Legislative bills — legal-tier signal (stronger than news/social for
# developer site-screening). Populated from OpenStates API.
BILLS_SCHEMA = """
CREATE TABLE IF NOT EXISTS bills (
  id                       TEXT PRIMARY KEY,      -- "openstates:<ocd-bill-id>"
  state                    TEXT NOT NULL,         -- "ME", "VA", "TX" ...
  bill_number              TEXT,                  -- "LD 307", "SB 1038"
  session                  TEXT,                  -- "2025-2026"
  title                    TEXT NOT NULL,
  summary                  TEXT,
  status                   TEXT,                  -- introduced | in-committee |
                                                  -- passed-lower | passed-upper |
                                                  -- passed-both | enacted | vetoed | dead
  status_date              TEXT,
  introduced_date          TEXT,
  last_action_date         TEXT,
  last_action_description  TEXT,
  sponsors                 TEXT,                  -- JSON: [{name, party, primary}]
  subjects                 TEXT,                  -- JSON from OpenStates
  tier                     TEXT,                  -- restrictive | protective |
                                                  -- supportive | unclear
  tier_reason              TEXT,
  keywords                 TEXT,                  -- JSON array
  url_openstates           TEXT,
  url_source               TEXT,                  -- legislature.state.xx.us
  first_seen               TEXT DEFAULT CURRENT_TIMESTAMP,
  last_seen                TEXT
);

CREATE INDEX IF NOT EXISTS idx_bills_state     ON bills(state);
CREATE INDEX IF NOT EXISTS idx_bills_tier      ON bills(tier);
CREATE INDEX IF NOT EXISTS idx_bills_status    ON bills(status);
CREATE INDEX IF NOT EXISTS idx_bills_last_seen ON bills(last_seen DESC);
"""


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

    # bills table + its indexes (no ALTER needed — pure CREATE IF NOT EXISTS)
    had_bills = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='bills'"
    ).fetchone() is not None
    conn.executescript(BILLS_SCHEMA)
    if not had_bills:
        applied.append("+table bills")

    # actions table — broader than bills, mirrors datacentertracker.org schema
    had_actions = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='actions'"
    ).fetchone() is not None
    conn.executescript(ACTIONS_SCHEMA)
    if not had_actions:
        applied.append("+table actions")

    conn.commit()
    return applied
