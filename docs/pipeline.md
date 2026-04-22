# Data pipeline

How data gets into the dashboard, end to end.

## Overview

The dashboard has two data layers:

1. **State view** — geographic events (news, legal rulings, hyperscaler announcements). Read at page load from `SEED_EVENTS` inlined in `index.html` + live GDELT queries from the browser.
2. **Social view** — what people are saying on X / Reddit / YouTube. Sourced from a SQLite DB (`data/news.db`) refreshed by a daily script, exported to `data/social_events.json`, and inlined into `index.html`.

## State view data flow

```
index.html SEED_EVENTS (hand-curated)  ----┐
                                           |
GDELT Doc 2.0 API  ---- 4 parallel queries ┼--->  browser merges  --->  map + feed
  (banned | cancelled |                    |        every 5 min
   protested | announced)                  |
                                           |
data/social_events.json  (items           ─┘
  with state != "US" auto-flow in
  so X post engagement bumps
  the state map dots)
```

GDELT queries are each ~50 chars (under GDELT's length cap). Engine hits 4 in parallel on page load, then polls every 5 minutes. CORS-enabled, no auth needed.

## Social view data flow

```
last30days skill  (runs from CLI, hits Reddit + X via xAI + YouTube + GitHub + Polymarket)
   |
   v
~/Documents/Last30Days/data-center-oppositions-in-us-raw-{suffix}.md   (raw markdown dump)
   |
   v
scripts/ingest_x_from_raw.py   (parses X items, geocodes by keyword,
                                dedups by MD5(URL), drops rows >35d)
   |
   v
data/news.db   (SQLite)
   |
   v
scripts/build_news_db.py::export_json()
   |
   v
data/social_events.json
   |
   v
re-inlined into index.html as <script type="application/json" id="social-data">
   |
   v
browser JSON.parse() at page load  --->  editorial magazine layout
```

## SQLite schema

```sql
CREATE TABLE events (
  id TEXT PRIMARY KEY,                -- stable: x-{md5(url):10} or news/reddit variant
  state TEXT NOT NULL,                -- 2-letter code, or "US" for national
  city TEXT,
  category TEXT NOT NULL,             -- banned | cancelled | protested | announced
  headline TEXT NOT NULL,
  source_domain TEXT,
  source_name TEXT,                   -- for X: "@handle"; for Reddit: "r/sub"; for news: publication name
  url TEXT,
  date TEXT NOT NULL,                 -- ISO 8601
  platform TEXT NOT NULL,             -- news | reddit | x | youtube | tiktok | legal
  engagement_score INTEGER DEFAULT 0, -- likes + reposts for X; upvotes for Reddit; views for YouTube
  upvotes INTEGER,
  comments INTEGER,
  views INTEGER,
  likes INTEGER,
  sentiment TEXT,                     -- negative | neutral | positive (toward DC)
  companies TEXT,                     -- JSON array of hyperscaler tags
  first_seen TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_events_state    ON events(state);
CREATE INDEX idx_events_platform ON events(platform);
CREATE INDEX idx_events_date     ON events(date);
CREATE INDEX idx_events_category ON events(category);
```

## Running it

### Daily refresh

```bash
bash scripts/run_daily.sh
```

Runs: last30days → ingest_x_from_raw → build_news_db → re-inline HTML. 2-3 min.

Dedupe is idempotent — re-running on the same day updates engagement numbers on existing tweets without creating duplicates.

### Manual seed (initial population)

```bash
python3 scripts/build_news_db.py
```

Seeds from the hardcoded `EVENTS` list in `build_news_db.py`. Safe to re-run.

### One-off X ingest from a specific raw file

```bash
LAST30DAYS_RAW_PATH=/path/to/raw.md python3 scripts/ingest_x_from_raw.py
```

## Dedup mechanics

- **X posts**: primary key is `x-{md5(url)[:10]}`. Re-ingesting the same tweet → same ID → SQLite `INSERT OR REPLACE` updates engagement, no duplicate row.
- **35-day cleanup**: `ingest_x_from_raw.py` runs `DELETE FROM events WHERE platform='x' AND date < date('now', '-35 days')` before each ingest so the rolling window stays fresh.
- **News/legal events**: currently hand-curated in `build_news_db.py`. `INSERT OR REPLACE` with stable IDs so re-running is safe.

## Gaps (what's not yet wired)

- Reddit + YouTube parsers — `ingest_x_from_raw.py` only handles X. Tomorrow's last30days run will fetch 13 Reddit threads + 4 YouTube videos but they won't flow into the DB until parsers exist.
- GDELT → SQLite — live GDELT events exist only in the browser. If you want historical GDELT data in the DB, need a server-side poller.
- Authoritative hyperscaler feeds (SEC 8-K, company press releases) — not wired. Hyperscaler seed events in `SEED_EVENTS` are manual.
- Per-ISO stakeholder meeting ingest — research complete (`research/iso-research/`), pipeline not built.

## Deployment

Fully static. Works from `file://` (with inlined JSON). For live-refresh hosting:

- **GitHub Pages**: push to `main`, enable Pages on `/` root → served at `https://amyarsenal.github.io/Data-Center-Watcher/`
- **Vercel / Netlify**: connect the repo, no build command, output directory = `/`
- **Local HTTP**: `python3 -m http.server 8000`

Once served over HTTP, switch from inlined JSON to `fetch('./data/social_events.json')` for hot-reload after `run_daily.sh`.
