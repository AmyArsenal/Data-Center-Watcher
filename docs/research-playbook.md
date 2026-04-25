# Weekly Research Playbook

How to refresh `actions` with the same density as datacentertracker.org — without
paying for an LLM API. Owner: human + Claude Code (Max plan) on Sundays.

> **TL;DR** — Every Sunday: open Claude Code → run the prompts in section 3 → drop
> JSON into `data/research_pending.json` → run `scripts/upsert_research_pending.py` →
> commit + push. Total cycle ~30 minutes for a 50-state sweep.

---

## 1. Why this exists

OpenStates covers state legislatures (well, on a 6-month rolling window). It
**doesn't** cover:

- City councils (Bangor, Lowell, Monterey Park, OKC, Pemberton, …)
- County boards (DeKalb, Orange NC, Saline KS, Manitowoc, …)
- PUC / utility commission orders (PJM, ERCOT, SCC GS-5, FERC EL25-49, …)
- Court filings (Talen-AWS, Caddo Parish, Hood Co. moratorium, …)
- Hyperscaler announcements + withdrawals (Microsoft Caledonia, Spartanburg, …)
- Federal executive actions, EPA hubs, DOE federal lands, White House EOs

That's where the human review-then-merge loop comes in.

## 2. The pieces

```
research_agent.py (Claude Code, you)        ← weekly prompt-driven research
       │
       ▼
data/research_pending.json                  ← raw findings (review queue)
       │
       │  human edits: drop false positives, normalize fields
       ▼
scripts/upsert_research_pending.py          ← idempotent ingestion
       │
       ▼
data/news.db   actions table                ← single source of truth
       │
       ▼
scripts/build_dossier.py                    ← regenerate exports + API
       │
       ▼
data/actions.json + data/dossiers/* + data/api/v1/*
       │
       ▼
git commit + push                            ← Pages serves on next deploy
```

## 3. The Sunday ritual

### a) Spin up the research

In Claude Code, spawn parallel agents covering the country. Suggested split (12
agents to keep each under ~10 min and within token limits):

| Agent | Coverage |
|---|---|
| 1 | Maine (deep — most active state) |
| 2 | Virginia (deep — bills + PWC, Loudoun, etc.) |
| 3 | Texas (deep — SB 6, Hood Co., recalls) |
| 4 | WI / OK / SC tri-state |
| 5 | Northeast (NY/NJ/CT/MA/RI/VT/NH) |
| 6 | Mid-Atlantic (MD/PA/DE/WV/DC) |
| 7 | Southeast (GA/NC/MS/LA/TN/FL/AL/KY/AR) |
| 8 | Midwest (OH/IN/IL/MI/MN/IA/MO) |
| 9 | Plains/Mountain West (KS/NE/ND/SD/MT/WY/CO/UT/ID) |
| 10 | West Coast/Southwest (CA/WA/OR/NV/AZ/NM/AK) |
| 11 | Federal Congress + executive (Sanders/AOC, EOs, EPA, DOE) |
| 12 | Court filings + state PUC/PSC orders (FERC, IURC, PUCO, GA PSC, etc.) |

**Standard agent prompt** (paste this verbatim, swap `{REGION}`):

> Research data-center-related public actions in {REGION} from the last 30 days.
> Look for: enacted/proposed moratoriums, ordinances, zoning changes, PUC/PSC
> orders, lawsuits, project withdrawals, hyperscaler cancellations, ballot
> measures, recall elections, state-level bills the OpenStates feed missed (older
> sessions or non-bill resolutions). For each item return ONE JSON record with:
> state (2-letter), county (or null), jurisdiction (e.g. "Bangor City Council"),
> scope ("city" | "county" | "state" | "federal" | "regional"), action_type
> (subset of: moratorium, ordinance, zoning_restriction, legislation,
> regulatory_action, executive_action, lawsuit, ballot_measure, study_or_report,
> public_comment, recall, project_withdrawal, project_cancellation, public_hearing,
> other_opposition, other_support), authority_level (e.g. "city_council",
> "county_board", "state_legislature", "governor", "state_puc", "ferc",
> "federal_court", "state_court", "ballot"), date (YYYY-MM-DD or null), status
> (enacted | passed | introduced | in-committee | active | rejected | dead),
> community_outcome (win | loss | mixed | pending), issue_category (subset of:
> water, grid_energy, ratepayer, environmental, noise, traffic, farmland,
> tax_incentive, transparency, zoning, design_standards, community_impact,
> public_health, climate, equity, other), company (or null), hyperscaler (or
> null), project_name (or null), summary (2-3 sentences), sources (array of
> {title, url}). Return as a JSON array. Verify each item with at least one
> primary source — cite the URL. Drop anything you can't verify.

### b) Aggregate

Concatenate all 12 agent JSON responses into a single array and write to
`data/research_pending.json`. Manually drop:

- Duplicates (same jurisdiction + same week — pick the most-cited).
- Items where the source is a paywalled aggregator only (need at least one open URL).
- Anything that's already in OpenStates with the same bill number.

### c) Ingest

```bash
python3 scripts/upsert_research_pending.py
python3 scripts/build_dossier.py
```

`upsert_research_pending.py` generates stable IDs of the form
`research:{state}-{jurisdiction}-{date}-{title-prefix}`, so re-running the same
weekly batch is idempotent — second run will report `updated=N` not `inserted=N`.

### d) Sanity check

```bash
sqlite3 data/news.db "SELECT origin, COUNT(*) FROM actions GROUP BY origin;"
sqlite3 data/news.db "SELECT state, COUNT(*) FROM actions GROUP BY state ORDER BY 2 DESC LIMIT 10;"
sqlite3 data/news.db "SELECT COUNT(*) FROM actions WHERE last_updated >= date('now','-7 days');"
```

Expected: ~10–30 new rows per week once steady-state. First-time backfill (the
April 2026 sweep) added 169.

### e) Ship it

```bash
git add data/ scripts/upsert_research_pending.py docs/
git commit -m "research: weekly sweep $(date -u +%F)"
git push
```

GitHub Pages picks up within ~60s.

## 4. Quality bar

Every record needs **at least one** of:

- A primary source (newspaper, gov website, court docket, PUC filing).
- A direct video / Twitter clip from the meeting (with timestamp).
- A photo / scan of the ordinance / resolution text.

Reddit threads + TikTok engagement + secondary aggregators are signal — they're
welcome in the `events` table (via `last30days` skill). They are **not** sufficient
for the `actions` table on their own. The `actions` table is the load-bearing
spine of the developer-facing dossier product; integrity matters.

## 5. Cost

- **Claude Code (Max plan):** ~$200/mo flat. Sunday usage is ~30 min, well
  inside fair-use limits.
- **Anthropic API:** $0. Not used for research — the API path stays reserved
  for unattended cron jobs (newsletter generation, sentiment scoring) that
  can't be human-supervised.
- **OpenStates:** free tier sufficient (1 req/sec, 10k req/day).
- **GitHub Actions:** within free tier (~120 min/mo for 15-min cron).

## 6. Failure modes + recovery

| Failure | Symptom | Fix |
|---|---|---|
| Agent returns 0 rows for a state | Quiet week is normal; verify by spot-checking 1–2 known issues | Move on. |
| `upsert_research_pending.py` reports errors | Bad JSON shape | Edit the offending record in `research_pending.json` and re-run. Idempotent. |
| GitHub Actions race with bills tier | Push rejected on rebase | `git pull --rebase -X theirs origin main && git push`. Same recipe as fast tier. |
| Dossier file size > 5 MB | Pages serve slows | We're at ~488 actions and ~80 KB; not a concern until ~5k+ actions. |
| Stale records (events that were "pending" months ago) | Outdated dossier | Re-run a single state via the agent prompt with "last 90 days"; ingestion is idempotent. |

## 7. When a record changes status

Example: NY S9144 moves from "in-committee" to "passed-lower". Two options:

1. **Re-research** — Run the agent for NY with "last 30 days" focus on bill
   updates. The new record will hit the same `id` and trigger an `update` not an
   `insert`.
2. **Manual SQL** — for surgical updates outside the Sunday ritual:

   ```sql
   UPDATE actions
      SET status='passed-lower', last_updated=date('now')
    WHERE id='research:ny-new-york-senate-assembly-...';
   ```

   Then run `python3 scripts/build_dossier.py` to refresh exports.

## 8. Future automation hooks (not built yet)

- `scripts/research_agent.py` — script to fan out to the Anthropic API instead of
  manual Sunday Claude Code session, **only if** Sunday cadence breaks down. Cost
  estimate: 12 agents × ~30k input + ~10k output × $15/M input + $75/M output =
  ~$10/sweep. Pencils out at ~$520/yr — cheaper than a missed-week rebuild but
  not worth it as long as the Sunday ritual is happening.
- Webhook into Beehiiv to surface "new this week" in the Sunday Watch newsletter.
- Slack ping to a private channel when `community_outcome='loss'` appears (for
  hyperscaler / consultant subscribers eventually).

## 9. Reference

- OpenStates v3: https://docs.openstates.org/api-v3/
- FIPS county codes (used by `build_dossier.py`): see `data/iso-boundaries.json`
- Issue + action_type taxonomies: see `lib/actions.py` constants
- Datacentertracker.org for sanity checks (CC BY 4.0, do not import)

---

**Last sweep:** 2026-04-24 (169 records added across 50 states).
**Next sweep:** Sunday 2026-04-27.
