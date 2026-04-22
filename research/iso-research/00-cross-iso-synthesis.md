# Cross-ISO Stakeholder Meeting Intelligence — Master Synthesis

_"RTO Insider for AI Agents" — v0 scoping, 2026-04-21_
_Based on parallel deep research across PJM, MISO, ERCOT, CAISO, NYISO, ISO-NE, SPP._

---

## 1. The top-signal committee per ISO (the one you'd track first)

| ISO | #1 committee | Why |
|---|---|---|
| **PJM** | Load Analysis Subcommittee (**LAS**) | Utility-by-utility large-load MW disclosures each fall — the earliest hard signal on data-center load by geography |
| **MISO** | Large Load Working Group (**LLWG**, new 2025) | Purpose-built for hyperscalers; drafting Large Load Definition + ZGIA + firm-service step-up |
| **ERCOT** | Large Load Working Group (**LLWG**) | 100% DC-relevant; originating forum for NOGRR282, NPRR1308, PGRR145, Batch Study |
| **CAISO** | **Large Loads Initiative** (Jan 2026) | First CAISO workstream scoped specifically around data-center + co-located loads |
| **NYISO** | **ICAPWG** (capacity) + **ESPWG/TPAS** (planning) | Large-load reform plan running Feb → Dec 2026; ~11.9 GW of large-load queue requests as of Feb 2026 |
| **ISO-NE** | Planning Advisory Committee (**PAC**) | Open forum; hosts Cluster Study + 2050 Tx Study + Maine-to-rest-of-region RFP |
| **SPP** | **MOPC** (meets only 2×/yr — July + Oct) | All major tariff changes (HILL, HILLGA, CPP) pass through here |

**Pattern:** every ISO has a dedicated data-center body now. Three were created/activated in 2025 (MISO LLWG, ERCOT LLWG, CAISO Large Loads). The Western non-RTO regions and most state PUCs don't have one yet.

---

## 2. Feed infrastructure — cross-ISO comparison

| ISO | iCal | RSS | Structured JSON API for stakeholder? | Notes |
|---|---|---|---|---|
| PJM | Per-meeting .ics from Meeting Center; training-calendar .ics | **Yes** — multiple feeds: committees, subcommittees, task forces, ex-parte, news, Inside Lines blog | No | **Best-in-class.** RSS + deterministic URL conventions. Scraper #1 target. |
| MISO | **No** | **No** | No | HTML scrape required. Predictable event URLs (`/events/YYYY/{slug}---{month}-DD-YYYY/`). |
| ERCOT | No | No | No (Public API is market-data only) | **WebFetch returns 403** — Akamai edge protection. Need header-spoofing or headless browser. |
| CAISO | No | No (legacy refs exist; none live for initiatives) | No (OASIS is market-data only) | **Daily Briefing email is the best feed** — digest of every notice. |
| NYISO | **Yes — 5 webcal ICS feeds (MC / BIC / OC / Training / General)** | **No** | No | **Calendar-feed leader.** Three parent ICS cover every subcommittee. Materials scraper still needed. |
| ISO-NE | **Yes — NEPOOL `?ical=1` per month + ISO Newswire RSS** | **Yes (ISO Newswire)** | No | **Tied with NYISO for best feed surface.** RSS + ICS + clean URL patterns. |
| SPP | **No** | **No** | No | Scrape-hostile. Opaque folder IDs, no index, inconsistent filenames. **Hardest ISO to cover.** |

**Design implication:** no ISO has a JSON stakeholder API. The pipeline needs 4 crawl modes: (1) ICS-driven calendar discovery (NYISO, ISO-NE, PJM per-meeting), (2) RSS news watcher (PJM, ISO-NE), (3) HTML scrape (MISO, CAISO, SPP), (4) edge-hardened scrape with browser emulation (ERCOT). Plus email-digest ingestion for CAISO's Daily Briefing.

---

## 3. Recent big-ticket actions (18-month window)

| ISO | Biggest DC-related action (2024-2026) |
|---|---|
| PJM | **CIFP-LLA Board Decisional Letter** (Jan 16 2026) + **FERC EL25-49 co-location order** (Dec 18 2025, requires tariff revisions by Jun 2026) + 2025/26 BRA clearing at $269.92/MW-day |
| MISO | **Jan 30 2026 Large Load Workshop** — first public draft of Large Load Definition + ZGIA + firm-service step-up. **LRTP Tranche 2.1** approved Dec 2024 ($21.8B, 3,631 miles of 765 kV) |
| ERCOT | **Texas SB 6 signed Jun 2025** — 5 parallel PUCT projects (58479-58484). **NPRR1308 / NOGRR282** (ride-through for LELs ≥75 MW). **Batch Study Process** launching mid-2026 for 410 GW queue of large-load requests |
| CAISO | **Large Loads Initiative** Issue Paper Jan 2026. **Draft 2025-26 Transmission Plan** (Apr 7 2026) with ~$1B South Bay Reinforcement for Silicon Valley DC. **SB 57** signed Oct 2025 (study-first approach) |
| NYISO | **NYPSC Case 26-E-0045** (Feb 12 2026) — large-load cost-allocation proceeding. **Indian Point 200 MW DC inquiry** (Holtec). Reform timeline: Dec 2026 Board approval + FERC filing |
| ISO-NE | **Maine LD 307** enacted Apr 14 2026 (first statewide DC moratorium). **CAR Phase 1** accepted by FERC Mar 30 2026 (shifts to prompt auction). **Transitional Cluster Study** (26 projects, 8 GW) launched Oct 20 2025 |
| SPP | **HILL/HILLGA tariff (RR 696)** — Board approved Sep 2025; FERC accepted Jan 14 2026. **CPP approved** by FERC Mar 13 2026. **2025 ITP portfolio $8.6B approved** Nov 2025, largely DC-driven |

---

## 4. Total effort estimate for full coverage

| ISO | MVP (top committee) | Full v1 (3 committees) | Notes |
|---|---|---|---|
| PJM | ~12 hrs | ~26 hrs | Cleanest. RSS + deterministic URLs. |
| MISO | ~6 hrs (LLWG) | ~20 hrs | Medium. Predictable event URLs. |
| ERCOT | ~18 hrs (LLWG only) | ~50 hrs | Hardest. Need headless browser. NPRR tracker is gold once working. |
| CAISO | ~12 hrs (Large Loads) | ~30-42 hrs | Heavy PDF volume; no feeds → rely on email digest. |
| NYISO | ~10 hrs | ~20-26 hrs | Tier 1 (iCal) is ~4 hrs; materials scrape adds 15+ hrs. |
| ISO-NE | ~5 hrs (RSS+ICS) | ~25 hrs | Easiest Tier 1. Materials layer is the work. |
| SPP | ~12 hrs | ~30 hrs | Most engineering time per signal unit. |
| **Total** | ~75 hrs | **~200-225 hrs** | ≈5-6 weeks of focused engineering for all 7 ISOs |

---

## 5. Unified data schema (normalized output)

Every ingested artifact lands in one of three rows:

```json
{
  "id": "miso-llwg-2026-04-20",
  "type": "meeting",                // meeting | document | filing | docket-action
  "iso": "MISO",
  "committee_code": "LLWG",
  "committee_name": "Large Load Working Group",
  "parent_committee": "Advisory Committee",
  "title": "Large Load Working Group — April 20, 2026",
  "date": "2026-04-20T13:00-05:00",
  "status": "upcoming",              // upcoming | today | in-session | past | cancelled
  "url_event": "https://misoenergy.org/events/...",
  "url_materials": ["https://cdn.misoenergy.org/..."],
  "docs": [
    {
      "kind": "agenda",              // agenda | presentation | whitepaper | minutes | redline | filing
      "title": "Agenda",
      "url": "...",
      "published_at": "2026-04-13T...",
      "page_count": 6
    }
  ],
  "topics": ["large-load", "queue-reform", "firm-service-step-up"],
  "companies_mentioned": ["Microsoft", "Meta"],
  "states_affected": ["MN", "IA", "WI"],
  "ferc_dockets": [],
  "summary_md": "…",                 // LLM-generated
  "first_seen": "2026-04-19T08:00Z",
  "source_feed": "miso-event-scraper"
}
```

Filing-type shape (for FERC dockets):

```json
{
  "id": "ferc-el25-49",
  "type": "filing",
  "iso": "PJM",
  "docket": "EL25-49-000",
  "docket_type": "EL",               // EL | ER | AD | RM
  "caption": "PJM Co-Location Rules — Show Cause",
  "filed_by": "FERC",
  "filed_at": "2025-12-18",
  "next_deadline": "2026-06-15",
  "status": "order-issued",          // filed | pending | comment-period | order-issued | appealed | concluded
  "topics": ["co-location", "btmg", "transmission-service"],
  "related_iso_items": ["pjm-mrc-2026-02-18"],
  "summary_md": "…",
  "url": "https://www.ferc.gov/news-events/news/..."
}
```

---

## 6. UI / UX — "RTO Insider for AI Agents"

**Four views, same map geometry across all of them:**

### View A — **Opposition** (already built)
State map with news events from GDELT + social. Current `data-center-tracker.html`.

### View B — **Regulatory** (new)
ISO map. Each ISO shows a **live case load** (open dockets + upcoming meetings). Click ISO → side panel swaps to a case-timeline view.
- Upcoming meetings list (next 30 days) sorted by ISO
- Active FERC dockets filtered to DC-relevant
- "Heat" indicator = recent filings velocity per ISO

### View C — **Meetings** (new)
Calendar-centric. Horizontal timeline view showing **next 30 days of stakeholder meetings across all 7 ISOs**, colored by ISO. Click a meeting → drawer with agenda items filtered to DC-relevant, recent minutes from same committee, LLM summary of agenda.

### View D — **Companies** (new)
Per-hyperscaler feed: Microsoft, Meta, Google, Amazon, Oracle, OpenAI, Anthropic, Nvidia, CoreWeave. For each, show: all news mentions, all filings where they're named (e.g., Amazon-Talen EL24-82), their projects by ISO, and capex/earnings tie-ins from Polymarket + Polygon.

**Shared surfaces across all four views:**
- Live ticker (breaking news, same as today)
- Company filter chips
- ISO/State view toggle
- Category filters (banned / cancelled / contested / announced / regulatory / meeting)

---

## 7. Proposed repo structure

```
rto-stream/  (or gridsurf-signals — new repo, MIT or proprietary)
├── README.md
├── .github/workflows/
│   └── scrape-cron.yml          # every 4 hrs, commits data/*.json
├── scripts/
│   ├── ingest_pjm/              # MVP priority
│   │   ├── las.py
│   │   ├── pc.py
│   │   └── mrc_mc.py
│   ├── ingest_miso/
│   │   ├── llwg.py
│   │   └── pac.py
│   ├── ingest_ercot/            # headless browser
│   │   ├── llwg.py
│   │   └── nprr_tracker.py
│   ├── ingest_caiso/
│   │   ├── large_loads.py
│   │   └── daily_briefing_email.py
│   ├── ingest_nyiso/
│   │   ├── ical_parent.py       # MC + BIC + OC
│   │   └── icapwg_espwg.py
│   ├── ingest_isone/
│   │   ├── nepool_ical.py
│   │   ├── iso_newswire_rss.py
│   │   └── pac.py
│   ├── ingest_spp/
│   │   ├── mopc_board.py
│   │   └── rsc_cawg.py
│   ├── ingest_ferc/             # cross-cutting
│   │   └── elibrary_rss.py
│   ├── classify.py              # LLM topic + relevance + entity tagging
│   └── aggregate.py             # writes data/meetings.json + data/dockets.json
├── data/
│   ├── meetings.json            # committed output — the frontend reads this
│   ├── dockets.json
│   ├── iso-boundaries.json      # existing, reusable
│   └── history/                 # daily snapshots for diff/decay
├── web/
│   ├── index.html               # evolution of data-center-tracker.html
│   ├── views/
│   │   ├── opposition.js
│   │   ├── regulatory.js
│   │   ├── meetings.js
│   │   └── companies.js
│   └── components/
│       ├── map.js
│       ├── feed.js
│       └── ticker.js
├── agents/                      # MCP-served tools for AI agents
│   ├── server.py                # FastMCP server
│   └── tools/
│       ├── search_meetings.py
│       ├── get_docket.py
│       └── summarize_filing.py
└── research/                    # this folder, the 7 ISO reports
    └── ...
```

**Two deployment surfaces:**
1. **Frontend (`web/`)** — static site on Vercel/GitHub Pages
2. **MCP server (`agents/`)** — served over streamable-HTTP, so Claude/other agents can query the same underlying data programmatically — THIS is the "for AI agents" part

---

## 8. Suggested v1 build order (6 weeks)

| Week | Deliverable | Effort |
|---|---|---|
| 1 | Repo scaffold + GitHub Actions cron + aggregate.py + normalized schema | ~20 hrs |
| 2 | PJM ingest (LAS + PC + MRC/MC) + FERC eLibrary RSS | ~30 hrs |
| 3 | MISO (LLWG + PAC) + ISO-NE (NEPOOL ICS + ISO Newswire RSS + PAC) | ~25 hrs |
| 4 | NYISO (parent ICS + ICAPWG/ESPWG/TPAS) + CAISO (Large Loads + Daily Briefing) | ~30 hrs |
| 5 | ERCOT (LLWG + NPRR/NOGRR tracker w/ headless browser) + SPP (MOPC + RSC) | ~40 hrs |
| 6 | Frontend rebuild — 4 views, ticker, filters, MCP server | ~40 hrs |
| **Total** | **Full v1 live** | **~185 hrs** |

---

## 9. Key risks / known unknowns

1. **ERCOT 403 blocking** — may need residential proxy or full headless Chrome; budget uncertainty
2. **CAISO URL instability** — site redesigned late 2024; selectors may break
3. **SPP folder-ID drift** — opaque IDs can change; need monitoring
4. **FERC rate-limit / API-key tier** — eLibrary is public but heavy usage may trigger throttling
5. **LLM cost** — ~0.20–0.50 per document summary; 300-500 docs/month = /mo budget
6. **Legal summary risk** — LLM paraphrases of rulings can be wrong; human-in-the-loop gate needed for anything declarative about decisions
7. **RTO Insider licensing** — they have a paywall; our summaries must be independent, not scraped from their pieces

---

## 10. Naming suggestions for the repo / product

- **rto-stream** — matches the "news stream" framing
- **gridsurf-signals** — ties to your gridsurf.ai brand
- **iso-pulse** — emphasizes real-time
- **rto-agent** — emphasizes the "for AI agents" framing
- **stakeholder-intel** — descriptive, unambiguous
- **compass-rto** — navigational framing

Pick one; I can scaffold the new repo with the folder structure above as soon as you decide.
