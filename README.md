# Data Center Watcher

> Tracking data center oppositions across the US.

A live dashboard of local community opposition, cancellations, moratoriums, and announcements for US data-center projects. Aggregates press coverage, court rulings, and real-time social media sentiment (X, Reddit, YouTube).

**Why?** Nearly half of US data centers planned for 2026 are delayed or cancelled. 142 activist groups in 24 states have blocked or delayed $64B+ in projects. The story is bipartisan, bottom-up, and under-reported. This dashboard tries to make the scale visible.

## Quickstart

### View the dashboard

```bash
# Simplest — open the file directly
open index.html

# Or serve over HTTP for future live fetches
python3 -m http.server 8000
# visit http://localhost:8000
```

### Refresh the data

```bash
bash scripts/run_daily.sh
```

This runs the [last30days skill](https://github.com/mvanhorn/last30days-skill) against "data center oppositions in US", parses the output, dedups into `data/news.db`, re-exports `data/social_events.json`, and re-inlines it into `index.html`. Takes 2-3 minutes.

## What you see

Two views, toggle in the header:

**State view** — map-centric dashboard
- US state map, each state dotted by event count, colored by most recent category
- Live ticker across the top (breaking news, left-to-right scroll)
- Feed of news + legal rulings + hyperscaler announcements
- Category filters: `Banned · Cancelled · Contested · Announced`
- Company filters: `Microsoft · Meta · Google · Amazon · OpenAI · Anthropic · Oracle · Nvidia · CoreWeave`
- Live news from GDELT 2.0 (4 parallel queries, 5-min refresh)

**Social view** — what people are actually saying
- No map, full-page editorial layout
- Platform filters: `X · Reddit · YouTube · TikTok`
- Big engagement numbers: `43K LIKES`, `6,272 UPVOTES`, `11K VIEWS`
- Top Voices rail (highest-engagement, any platform)
- Per-platform sections

## Data provenance

| Source | Where it comes from | Refresh |
|---|---|---|
| State map — seed events | Hand-coded in `index.html` `SEED_EVENTS` | Manual |
| State map — live news | GDELT Doc 2.0 API (public, CORS-enabled) | Browser, every 5 min |
| Social — X posts | xAI Grok-4 `/v1/responses` API (via last30days) | `run_daily.sh` |
| Social — Reddit | Public Reddit JSON (via last30days) | `run_daily.sh` (parser TBD) |
| Social — YouTube | `yt-dlp` + transcripts (via last30days) | `run_daily.sh` (parser TBD) |
| ISO boundaries | HIFLD ArcGIS FeatureServer, simplified | Static |

## Architecture

```
last30days skill  --->  raw markdown (local)
                              |
                              v
      ingest_x_from_raw.py  (parses X posts, dedups by URL hash,
                             drops rows >35d, inserts into SQLite)
                              |
                              v
      data/news.db  (SQLite — single source of truth for social)
                              |
                              v
      build_news_db.py  (re-exports to JSON)
                              |
                              v
      data/social_events.json
                              |
                              v
      index.html  (inlined <script type="application/json">, reads on load)
```

The HTML is fully self-contained — all data is inlined, no runtime dependencies except D3 + TopoJSON from a CDN. Works from `file://`. Can be deployed to GitHub Pages / Vercel / any static host.

## Tech

- **Frontend:** vanilla HTML + CSS + ES modules, [D3 v7](https://d3js.org/), [TopoJSON client](https://github.com/topojson/topojson-client). No build step.
- **Typography:** Tiempos Text / Source Serif 4 (fallback) for body, Inter for UI, JetBrains Mono for data.
- **Palette:** paper / ink aesthetic (`#F0EEE6` background, `#1A1915` ink) — deliberately not an AI-dashboard look.
- **Backend:** Python 3.12+, SQLite, shell. No server required.
- **Data:** [last30days skill v3.0.10+](https://github.com/mvanhorn/last30days-skill) (social aggregator), xAI Grok-4 API for X search.

## Research

See [`research/iso-research/`](research/iso-research/) for deep dives into each ISO's stakeholder meeting infrastructure (PJM, MISO, ERCOT, CAISO, NYISO, ISO-NE, SPP) and the cross-ISO synthesis. Written for a future "RTO Insider for AI Agents" layer; not wired into the dashboard yet.

## License

MIT
