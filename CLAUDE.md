# CLAUDE.md

Context for future Claude Code sessions on **Data Center Watcher** — a live
dashboard tracking US data-center opposition, pivoting into a developer-facing
site-screening product.

- **Live site:** https://amyarsenal.github.io/Data-Center-Watcher/
- **Repo:** https://github.com/AmyArsenal/Data-Center-Watcher (public, main branch deploys)
- **Blog:** https://amyarsenal.github.io/Data-Center-Watcher/blog.html (placeholder)

## What this is

A single-page dashboard with **three primary tabs** in the header (News /
Bills / Social Media) plus three standalone secondary pages (newsletter.html
/ blog.html / about.html). Each tab answers one question:

| Tab | Answers | Powered by |
|---|---|---|
| **News** | Where is opposition happening right now? | Map + feed, `news.json` (15-min) + live GDELT (5-min) |
| **Bills** | Which states have moratoriums / pending legislation / community responses? | Map (paint by action density) + dense sidebar from `actions.json` — search, group-by State/Outcome/Issue, 16-tag chips |
| **Social Media** | What are people saying on X / Reddit / TikTok / Instagram / Threads / YouTube / Polymarket? | Magazine-layout `renderSocialPage()` from `social_events.json` |

Pricing ladder (live on About page): Free dashboard · **$50/mo Pro** · $499/mo
Team · Custom Enterprise. The North Star is the **developer site-screening
product**: pick a county, get back `risk_score + top citations + active bills
+ comparable projects` in milliseconds.

## Architecture at a glance

```
┌───────────────────────────────────────────────────────────────────────┐
│  BROWSER (index.html, vanilla HTML + ES modules + D3 v7 + TopoJSON)   │
│                                                                        │
│   on load + every 5 min:                                               │
│     fetch('data/news.json')           ◄── Fast tier  (CI, 15-min)     │
│     fetch('data/social_events.json')  ◄── Deep tier  (laptop, daily)  │
│     fetch('data/bills.json')          ◄── Bills tier (CI, hourly)     │
│     fetch('data/actions.json')        ◄── Dense layer — Bills tab UI  │
│     fetch('data/meta.json')           ◄── Freshness chips             │
│     GDELT DOC 2.0 direct API          ◄── Live tier (browser only)    │
└───────────────────────────────────────────────────────────────────────┘
                                   ▲
                                   │ Pages serves these static files
                                   │
┌───────────────────────────────────────────────────────────────────────┐
│  data/ (checked in; updated by cron + laptop runs)                    │
│    news.db           SQLite — events + bills + actions tables         │
│    news.json         rolling 90-day events (frontend-facing)          │
│    social_events.json  social-focused events for the Social tab       │
│    bills.json        all classified bills + per-state map aggregate   │
│    actions.json      DENSE layer — events + bills converted to        │
│                      datacentertracker.org-style schema (16 issue     │
│                      tags, 4 community outcomes, scope, action_type)  │
│    meta.json         per-tier last-refresh timestamps                 │
│    iso-boundaries.json  static ISO polygons                           │
└───────────────────────────────────────────────────────────────────────┘
                                   ▲
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
     ┌────────┴────────┐   ┌──────┴─────────┐   ┌──────┴─────────┐
     │  Fast tier      │   │  Bills tier    │   │  Deep tier     │
     │  .github/wf/    │   │  .github/wf/   │   │  scripts/      │
     │  refresh-fast   │   │  refresh-bills │   │  run_daily.sh  │
     │  cron: */15     │   │  cron: :07/hr  │   │  laptop-only   │
     └────────┬────────┘   └──────┬─────────┘   └──────┬─────────┘
              │                    │                    │
     GDELT · Reddit · RSS    OpenStates REST      last30days skill
     CourtListener · YT API  (50 states)          (X / YT-transcripts /
                                                   TikTok · IG · Threads ·
                                                   Polymarket · HN)
```

### The tiers, concretely

| Tier | Cadence | Where | Sources | Notes |
|---|---|---|---|---|
| **Live** | 5 min | browser | GDELT DOC 2.0 (4 parallel queries) | Never committed; ephemeral |
| **Fast** | 15 min | GitHub Actions | GDELT, Reddit JSON, 8× outlet RSS, CourtListener, YouTube Data API (if key) | Commits `data/news.json` when diff |
| **Bills** | hourly (`:07`) | GitHub Actions | OpenStates v3 REST | Commits `data/bills.json` when diff |
| **Deep** | on-demand | laptop | `last30days` skill → raw markdown → ingesters | Commits `data/social_events.json` + updates `news.db` |

Cron jitter on GitHub Actions is real (10-30 min late, sometimes skipped).
Design around it — never rely on an Actions run landing at an exact minute.

## Repo layout

```
Data-Center-Watcher/
├── index.html                    single-page dashboard (~3100 lines)
├── newsletter.html               $50/mo marketing page + subscribe form
├── blog.html                     hash-routed mini-SPA: index + 2 essays
│                                 (Maine LD 307, Dominion/NoVa)
├── about.html                    mission · methodology · sources & attribution
├── README.md                     user-facing project intro
├── CLAUDE.md                     this file
├── requirements.txt              requests + feedparser (prod deps)
├── .gitignore                    .env, .claude/, __pycache__, .db-wal
├── .nojekyll                     Pages serves files as-is
│
├── .github/workflows/
│   ├── refresh-fast.yml          */15 * * * *  fast tier cron
│   └── refresh-bills.yml          7  * * * *  bills tier cron
│
├── data/
│   ├── news.db                   SQLite — events + bills + actions tables
│   ├── news.json                 90-day rolling events (frontend)
│   ├── social_events.json        social-focused export
│   ├── bills.json                classified bills + by_state map aggregate
│   ├── actions.json              DENSE layer — drives Bills-tab sidebar
│   │                             (16 issue tags, outcome, scope, action_type)
│   ├── meta.json                 per-tier freshness timestamps
│   └── iso-boundaries.json       static ArcGIS ISO polygons
│
├── scripts/
│   ├── run_daily.sh              laptop-only orchestrator (5 steps)
│   ├── refresh_fast.py           fast tier orchestrator (CI + local) —
│   │                             also runs migrate_events_to_actions +
│   │                             exports actions.json on every cycle
│   ├── refresh_bills.py          bills tier orchestrator (CI + local)
│   ├── migrate_db.py             schema migrations + hash backfill
│   ├── migrate_events_to_actions.py  events + bills → actions table,
│   │                             applies 16-tag classifier
│   ├── research_agent.py         scaffolded weekly Claude Sonnet research
│   │                             pass (NOT WIRED — needs ANTHROPIC_API_KEY +
│   │                             review queue workflow)
│   ├── build_news_db.py          legacy seed loader + social_events export
│   ├── ingest_x_from_raw.py      parse [x] items from skill markdown
│   ├── ingest_polymarket_from_raw.py   parse [polymarket] items
│   ├── ingest_social_from_raw.py parse [tiktok|instagram|threads|youtube]
│   │
│   ├── lib/
│   │   ├── schema.py             CREATE TABLE + additive ALTER migrations
│   │   │                         (events, bills, actions tables)
│   │   ├── hashing.py            canonicalize_url, url_hash, content_hash
│   │   ├── events.py             upsert() with cross-source dedup
│   │   ├── classify.py           state/city/category/companies/relevance rules
│   │   ├── bills.py              tier classifier + aggregate_by_state + upsert
│   │   ├── actions.py            16-tag taxonomy, classify_issues,
│   │   │                         classify_action_type, infer_authority,
│   │   │                         infer_scope, derive_community_outcome,
│   │   │                         derive_tier, upsert, aggregate_by_state
│   │   ├── export.py             writes news.json + actions.json + meta.json
│   │   └── sources/
│   │       ├── gdelt.py          DOC 2.0, parallel queries, 12s timeout
│   │       ├── reddit.py         public JSON, 8 queries, 0.8s between
│   │       ├── rss.py            8 feeds via feedparser, parallel
│   │       ├── youtube.py        Data API v3 (needs YOUTUBE_API_KEY)
│   │       └── openstates.py     v3 REST, 2 queries × 51 states, handles 429
│   │
│   └── tests/
│       └── test_hashing_and_upsert.py   13 unit tests, ~5ms total
│
├── docs/
│   ├── pipeline.md               older architecture note
│   └── sample-newsletter.md      end-to-end newsletter sample from real data
│
└── research/iso-research/
    ├── 00-cross-iso-synthesis.md  cross-ISO strategic synthesis
    └── 01-07-*.md                 per-ISO deep dives (PJM, MISO, ERCOT,
                                    CAISO, NYISO, ISO-NE, SPP)
```

## Daily ops cheat sheet

```bash
# ── Local daily backfill (5-step pipeline) ─────────────────────────────
bash scripts/run_daily.sh              # full: skill + X + Polymarket + TikTok
                                       #       + IG + Threads + YouTube + fast
bash scripts/run_daily.sh --skip-deep  # fast tier only (~25s, no API calls)

# Review + push
git diff --stat data/
git add data/ && git commit -m "data: daily backfill $(date -u +%F)" && git push

# ── Tier-specific local runs ────────────────────────────────────────────
python3 scripts/refresh_fast.py         # fast tier only (also rebuilds actions.json)
python3 scripts/refresh_bills.py        # bills: incremental
python3 scripts/refresh_bills.py --full # bills: all 50 states (~5 min, rate-limited)
python3 scripts/migrate_db.py           # schema + hash backfill (idempotent)
python3 scripts/migrate_events_to_actions.py  # rebuild actions table from events+bills

# ── Tests + local server ────────────────────────────────────────────────
python3 scripts/tests/test_hashing_and_upsert.py   # 13 tests
python3 -m http.server 8765 --bind 127.0.0.1 --directory .
open http://127.0.0.1:8765/

# ── CI inspection ───────────────────────────────────────────────────────
gh workflow list
gh workflow run refresh-bills.yml                  # manual trigger
gh run list --workflow=refresh-fast.yml --limit=5
gh run view <run-id> --log | grep -E 'inserted=|raw_fetched|done in'

# ── Pages / deploy status ───────────────────────────────────────────────
gh api repos/AmyArsenal/Data-Center-Watcher/pages/builds/latest \
  --jq '{commit, status, duration}'
```

`run_daily.sh` prefers `python3.14` (homebrew) and falls back to stock `python3`
(3.9). Deps (`requests`, `feedparser`) must be installed for whichever Python
actually runs. On homebrew Python you'll need
`pip install --user --break-system-packages -r requirements.txt` due to PEP 668.

## Event + Bill schemas

**`events` table** (used by news/social/fast/deep tiers, one row per deduped story):

```
id              slug or source-hash key
state, city     two-letter state + optional locality
category        banned | cancelled | protested | announced
headline        the title we show
url             canonical URL
source          gdelt | reddit | rss-dcd | x | polymarket | tiktok | ...
source_tier     live | fast | deep | manual (strongest wins on merge)
sources_seen    JSON array — appended on dedup match
platform        news | reddit | x | youtube | tiktok | instagram |
                threads | polymarket | legal
date            ISO date of the source
first_seen      when our pipeline first ingested
last_seen       last time we touched the row
engagement_score  normalized likes/upvotes/views
upvotes, comments, views, likes  platform-specific fields
companies       JSON array, from extract_companies()
relevance_score  0..1 rule-based
url_hash         sha1(canonicalize_url(url))[:16]    for dedup
content_hash     sha1(normalized title + snippet)    for cross-source dedup
platform_metadata  JSON blob, platform-specific extras
snippet, topics, ferc_dockets, sentiment, counties, dollars_mentioned
```

Dedup rule (in `lib/events.upsert()`):

1. Lookup by `url_hash`. If hit → merge `sources_seen`, union JSON list fields,
   take max of engagement sub-fields, fill-null for geo/category. Respect tier
   ordering: `manual > deep > fast > live` (higher never demoted by lower).
2. Else lookup by `content_hash` (catches paraphrased re-shares).
3. Else `INSERT`.

**`bills` table** (populated only from OpenStates):

```
id                    openstates:<ocd-bill uuid>       PK
state, bill_number    e.g. ("ME", "LD 307")
session               e.g. "2025-2026"
title, summary
status                enacted | passed-both | passed-upper | passed-lower |
                      passed-committee | in-committee | introduced | dead
status_date, introduced_date, last_action_date, last_action_description
sponsors              JSON: [{name, party, primary}]
subjects              JSON from OpenStates
tier                  restrictive | protective | supportive | unclear
tier_reason           one-line human-readable (e.g. "moratorium", "tax abatement")
keywords              JSON array: moratorium, water, tax-incentive, ...
url_openstates, url_source
first_seen, last_seen
```

`lib/bills.aggregate_by_state()` produces the per-state map payload:
priority is `restrictive > protective > supportive`, within tier
`enacted > passed-both > ... > introduced`. The first row wins for
`map_color_tier + map_color_status`, up to 3 bills are featured in tooltips.

**`actions` table** (the dense layer that drives the Bills tab UI):

```
id                     PK — origin-prefixed slug
origin                 datacentertracker | openstates | manual | research_agent
state, county, jurisdiction, lat, lng
scope                  local | statewide | federal
action_type            JSON array — see ACTION_TYPES below (15 values)
authority_level        county_commission | city_council | state_legislature | ...
date, status, last_updated
community_outcome      pending | win | loss | mixed       (community POV)
tier, tier_reason      restrictive | protective | supportive | unclear  (developer POV)
issue_category         JSON array — 16-value vocabulary
company, hyperscaler, project_name
investment_million_usd, megawatts, acreage, building_sq_ft,
water_usage_gallons_per_day, jobs_promised
opposition_groups, opposition_website, opposition_facebook,
opposition_instagram, opposition_twitter, petition_url, petition_signatures
summary, sources                JSON array of citations
data_source                     news | agent_research | web_research | etc.
bill_number, bill_session       (when origin='openstates')
```

Schema is interoperable with **datacentertracker.org** (CC BY 4.0) so vocabularies
align — but we DO NOT import their data. Our pipeline is fully our own.

**Tag vocabularies** (frozen — UI relies on exact strings, JSON arrays in DB):

- `ISSUE_CATEGORIES` (16): zoning · water · environmental · community_impact ·
  grid_energy · transparency · ratepayer · noise · tax_incentive · farmland ·
  traffic · design_standards · contract_guarantees · anti_ai · air_quality ·
  property_values
- `ACTION_TYPES` (15): zoning_restriction · legislation · moratorium ·
  public_comment · lawsuit · project_withdrawal · utility_regulation ·
  ordinance · study_or_report · regulatory_action · executive_order ·
  other_opposition · infrastructure_opposition · permit_denial · executive_action
- `AUTHORITY_LEVELS` (27): county_commission · city_council · state_legislature ·
  ... (see `lib/actions.py`)

`lib/actions.aggregate_by_state()` produces map payload with: count (drives
opacity), tier_counts, outcome_counts, scope_counts, top 3 issues, latest_date,
worst-case `map_color_tier`. Map opacity in Bills mode = `0.20 + (count/maxCount)*0.55`.

**How the actions table gets populated:**
1. `migrate_events_to_actions.py` converts every `events` + `bills` row into
   an `actions` row (currently ~312 records from existing data)
2. Hooked into `refresh_fast.py` so every 15-min CI run re-builds `actions.json`
3. (Future) `research_agent.py` weekly Claude Sonnet pass adds new records
   from web research

## Frontend architecture (`index.html`)

Single-page vanilla HTML, ~3,100 lines. **Header has two nav strips:**
- Primary `#primary-nav`: News · Bills · Social Media (large serif tabs, drive `currentView`)
- Secondary `.nav-links`: Newsletter · Blog · About (link to standalone pages)

`currentView` swap is class-based on `.app`:
- News mode: default — shows ticker + map (events layer) + feed panel
- `bills-mode` class: hides feed, reveals `.bills-panel` sidebar; map switches to actions density
- `social-mode` class: hides map+feed entirely, shows `.social-view` magazine layout

Key globals near the top of `<script type="module">`:

| Global | Purpose |
|---|---|
| `SEED_EVENTS`  | Hand-curated baseline, ~30 events, always present |
| `FAST_EVENTS`  | Fetched from `data/news.json` on load + every 5 min |
| `BILLS_DATA`   | Fetched from `data/bills.json` (legacy bills layer) |
| `ACTIONS_DATA` | Fetched from `data/actions.json` — drives the Bills tab sidebar + map paint |
| `SOCIAL_DATA`  | Fetched from `data/social_events.json` |
| `FAST_META`    | Fetched from `data/meta.json` → drives freshness chip |
| `allEvents`    | Merged seed + fast + live (GDELT) + social-geo events |
| `currentView`  | `'news' | 'bills' | 'social'` (NOT 'state' anymore) |
| `mapLayer`     | `'events' | 'bills'` — `setView()` flips this automatically per tab |
| `feedSort`     | `'top' | 'latest'` — shared across News + Social views |
| `billsFilterState`, `billsFilterOutcome`, `billsFilterIssue`, `billsFilterScope`, `billsGroupBy`, `billsSearch` | Bills sidebar UI state |
| `activeCat`, `activeCo`, `activePlatform`, `stateFilter`, `isoFilter` | News/Social filter chips |

`refresh()` is the central function. Fires on load and every 5 min, fans out to
`fetchFastEvents / fetchLiveEvents / fetchMeta / fetchSocialData / fetchBillsData / fetchActionsData`
in a single `Promise.all`, then re-paints map + feed + ticker + chip + bills sidebar.

**Key render paths:**

- `setView(view)` — flips primary tab + class + `mapLayer`, then dispatches to right renderer
- `paintMapState(events)` — state fills + dots (events mode) or **action density coloring** (bills mode)
- `renderFeed()` — News-view feed, routes to `renderFeedSocial()` in Social mode
- `renderBillsPanel()` — Dense sidebar from `ACTIONS_DATA`: search box, state dropdown,
  issue dropdown (16 tags), outcome chips (pending/win/loss), scope chips (local/state/federal),
  group-by chips (state/outcome/issue), collapsible groups with "Show all N", up to 4 issue
  tag chips per card
- `renderSocialPage()` — magazine-layout Social tab with per-platform sections
- `renderTicker()` — top-of-page scrolling ticker; items are clickable `<a>` tags
- `renderSocialCard(e, featured?)` — per-platform rich engagement rendering
- `showActionsTooltip(event, code, agg)` — hover-state tooltip for Bills layer
- `displaySource(e)` — translates internal ingester keys (`gdelt`, `rss-dcd`) to
  human publisher names; never leaks raw keys to UI

**Subscribe dock — REMOVED.** Was a floating bottom-right pill that overlapped
sidebar content. Newsletter link in header drives sign-ups; full pitch lives at
`newsletter.html` with $50/mo + Beehiiv-ready form (still localStorage capture
until Beehiiv pub exists). The Beehiiv swap-point is in newsletter.html's
inline `<script>`, NOT index.html anymore.

## Secrets + env vars

| Variable | Needed for | Where |
|---|---|---|
| `SCRAPECREATORS_API_KEY` | TikTok/Instagram/Threads (deep tier) | `~/.config/last30days/.env`, chmod 600 |
| `OPENSTATES_API_KEY` | bills (Fast in CI + local) | local env + GitHub repo secret |
| `YOUTUBE_API_KEY` | fast-tier YouTube search (optional) | GitHub secret (unset → adapter skips) |

Never commit any of these. `.env` is gitignored. When in doubt, use
`echo 'FOO=bar' >> ~/.config/last30days/.env` (the skill's canonical location).
For CI: `gh secret set OPENSTATES_API_KEY --repo AmyArsenal/Data-Center-Watcher`.

Secrets to explicitly **not** chase:

- **xAI / Grok API** — `last30days` uses your browser-logged-in x.com session
  for free. Paid API path is not required and not wired.
- **Perplexity / OpenRouter** — nice-to-have, not in current scope.

## Known gotchas (the sharp edges)

1. **Reddit 0 rows in CI.** GitHub Actions shared egress IPs get 429'd by
   `reddit.com/search.json`. Reddit works fine locally. Fix: register a Reddit
   app and switch `lib/sources/reddit.py` to OAuth + `REDDIT_CLIENT_ID/SECRET`
   GitHub secrets.

2. **GDELT timeouts.** 2-3 of 6 queries flap per run. We parallelize + accept
   partial results. If all 6 fail the run still succeeds (GDELT returns 0).

3. **`build_news_db.py` INSERT OR REPLACE** wipes backfilled `url_hash` /
   `content_hash` on legacy SEED rows. `run_daily.sh` re-runs `migrate_db.py`
   at the end to re-backfill. Never call `build_news_db.py` directly mid-run.

4. **Bills false-positive matches.** OpenStates full-text search occasionally
   matches when "data center" appears only in sponsor bios or action history.
   `lib/bills.is_dc_relevant()` gates every upsert; `refresh_bills.py` also
   runs a one-shot cleanup DELETE on every run. Idempotent, safe.

5. **GitHub Actions rebase conflicts.** `refresh-fast` and `refresh-bills` both
   commit to `data/`. If they race, one is rejected. Both workflows run
   `git pull --rebase -X theirs origin main` before pushing to resolve
   automatically. If you `git push` from your laptop while a bot run is
   mid-flight, do the same: `git pull --rebase -X theirs origin main`.

6. **PEP 668 on homebrew Python.** Installing `requests` / `feedparser` needs
   `--break-system-packages`. See the ops cheat sheet.

7. **Social Sentiment tab chips are separate from State-view chips.** There
   are two places that render platform filter chips: the `#platform-filters`
   row in the State view and the chips inside `renderSocialPage()`. If you add
   a new platform, update **both**.

8. **Python version split.** On macOS, `python3` is 3.9 (stock) while
   `python3.14` is homebrew. The shebang in newer scripts prefers `python3.14`;
   CI uses `3.12`. Deps must be installed in whichever interpreter runs.

9. **Ticker click vs scroll.** `.ticker-band:hover .ticker-track { animation-play-state: paused }`
   is what makes clicks work. Don't remove it if you touch ticker CSS.

10. **Bills `unclear` tier stays out of the map aggregate** via
    `aggregate_by_state`'s `WHERE tier IN ('restrictive','protective','supportive')`.
    Unclear bills still appear in `bills.json items[]` for dossier search later.

11. **16-tag taxonomy is FROZEN.** Issue categories, action types, and authority
    levels in `lib/actions.py` mirror datacentertracker.org's vocabulary verbatim
    so datasets stay interoperable. Never add a new tag without verifying it
    doesn't conflict with their list at https://datacentertracker.org/. We also
    use their tooltip text verbatim (with credit on the About page).

12. **Never leak internal source keys to UI.** `gdelt`, `rss-dcd`, `x-grok`,
    `seed`, `manual` are ingester-internal. Always use `displaySource(e)` in
    JS — it falls back to `SOURCE_DISPLAY_NAMES` map, returns `''` for
    internal-only keys. Same applies to status chip text — say "Auto-updating"
    not "Fast tier", "Updating live news" not "Fetching GDELT".

13. **Source attribution lives at `about.html#sources`** — full table per
    source with cadence + direct link, plus methodology and a vocabulary credit
    to datacentertracker.org. Footer credit on every page is just
    "Updated continuously · Sources & methodology" linking there. Don't
    re-introduce inline source lists on other pages.

14. **Subscribe dock REMOVED** (commit `38ac8cf`). Don't put it back — it was
    overlapping sidebar content in Bills mode. Newsletter link in header is
    enough; the dedicated newsletter.html has the full marketing surface +
    subscribe form.

15. **Actions table is rebuilt on every fast-tier run** — `refresh_fast.py`
    invokes `migrate_events_to_actions.py` as a subprocess and re-exports
    `actions.json`. Cheap (~50 ms for 300 rows). If you change the actions
    schema, both the migration script AND `lib/actions._INSERT_COLS` need
    updating in lockstep.

## Conventions

- **Commit messages:** concise title (<72 chars), blank line, optional body
  explaining *why*. Every commit ends with
  `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` (use
  HEREDOC — see existing commits for format).
- **No mid-refactor commits.** Each commit should leave the dashboard working.
- **File imports:** `sys.path.insert(0, str(ROOT / "scripts"))` at the top of
  orchestrators so `lib.*` imports resolve. Don't turn `scripts/` into a
  package — it isn't one.
- **Logging:** `logging.basicConfig` with `%(asctime)s %(levelname)s %(name)s | %(message)s`.
  Each source module gets its own `log = logging.getLogger(__name__)`.
- **Shell scripts:** `set -euo pipefail`. Prefer `"$PY"` variable over
  hardcoding `python3` / `python3.14`.
- **CSS:** paper/ink aesthetic. Never introduce emoji in UI chrome without
  explicit user approval — we learned this when the `📬 Weekly Brief` pill got
  called AI slop.
- **Tests:** `python3 scripts/tests/test_*.py` should be runnable standalone
  (no pytest required). Keep them fast (<100ms total).

## Product direction (where this is heading)

Next unshipped phases, in priority order:

1. **Wire `research_agent.py`** — scaffold exists, not yet automated. Needs
   `ANTHROPIC_API_KEY` repo secret, a review-queue workflow at
   `data/research_pending.json` so we can manually approve before upserting,
   and `.github/workflows/refresh-research.yml` (weekly cron). This is the
   multiplier that takes us from 312 actions → 800-1100 over 2-3 months.
2. **CourtListener structured ingest** — currently CourtListener flows in as
   news cards. Adding `lib/sources/courtlistener_actions.py` that extracts
   case captions + parties + judges + ruling dates as proper actions. Adds
   ~50-100 records.
3. **FIPS county resolver** — OpenStates is state-level only. For the
   developer-dossier product we need county-level rollups. Inject a ~3,100-row
   FIPS CSV to extract counties from event `city` + free-text matching.
4. **Historical bills backfill** — OpenStates defaults to ~180-day window.
   Need `--session` support to pick up Maine LD 307 + earlier enacted bills.
5. **`scripts/build_dossier.py`** — per-state + per-county risk dossier
   committed as `data/dossiers.json`. Composite score uses the new actions
   table + tier_counts + outcome_counts + multi-source bonus.
6. **`/site-screening.html`** — 2-column dossier UI: filter by state/county →
   dossier card + CSV download + top citations + neighbor counties.
7. **Beehiiv wire-up** — replace the localStorage capture in
   `newsletter.html`'s submit handler with a real Beehiiv API POST.
8. **Stripe + Pro gating** — paid tier ($50/mo Pro per the live About page).
   Gates county-level dossiers + alerts + API.
9. **Reddit OAuth** — unlocks Reddit in Actions.
10. **Weekly newsletter automation** — `scripts/weekly_brief.py` generating
    the draft shown in `docs/sample-newsletter.md` from real DB data,
    draft to Beehiiv.

**Live pricing tiers** (visible on `about.html`, repeated for clarity):
Free dashboard · **$50/mo Pro** (county dossiers + CSV + 10k API + alerts) ·
**$499/mo Team** (5 seats + Slack webhooks) · **Custom Enterprise** (unlimited
seats + real-time webhooks + white-label + quarterly analyst reports).

The strategic pivot: **from "opposition feed for journalists" → "site-intelligence
API for developers"**. Bills + actions table + county dossiers + API access are
the load-bearing pieces. The 16-tag taxonomy + datacentertracker.org-grade
density on the Bills tab is the visible product credibility; the data behind it
is fully our own pipeline (no imports from any third-party dataset).
See `docs/sample-newsletter.md` for the editorial voice,
`research/iso-research/00-cross-iso-synthesis.md` for regulatory context, and
`scripts/research_agent.py` for the next-multiplier scaffold.

## References

- OpenStates API: https://docs.openstates.org/api-v3/
- OpenStates key signup: https://openstates.org/accounts/profile/
- GDELT DOC 2.0: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
- Reddit API: https://www.reddit.com/dev/api/
- ScrapeCreators (TikTok/IG/Threads): https://scrapecreators.com
- last30days skill: https://github.com/mvanhorn/last30days-skill
- Beehiiv API (for newsletter wire-up): https://developers.beehiiv.com/
