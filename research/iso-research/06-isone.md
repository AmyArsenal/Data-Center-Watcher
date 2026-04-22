# ISO-NE Stakeholder Meeting Infrastructure — Research Report

**Target:** ISO New England (6 states)
**Date:** 2026-04-21

## 1. Governance hierarchy

Split governance: **ISO** runs market/grid, **NEPOOL** is regional stakeholder body (votes required for tariff changes), **NESCOE** represents 6 Governors (outside ISO/NEPOOL but influential).

```
FERC
 │
 ▼
ISO-NE Board of Directors
 ├── Management ◄───► NESCOE (state regulators, parallel)
 │
 ▼
NEPOOL Participants Committee (NPC)
 ├── Markets Committee (MC)
 ├── Reliability Committee (RC)
 ├── Transmission Committee (TC)
 ├── Budget & Finance Subcommittee
 ├── Membership Subcommittee
 │   └── Load Forecast WG, Power Supply Planning Subcommittee
 
ISO-run (not NEPOOL):
 ├── Planning Advisory Committee (PAC) — open forum
 │   ├── DG Forecast WG, EE Forecast WG, Environmental Advisory Group
 │   ├── IPSAC (tri-ISO), TOPAC
 ├── Consumer Liaison Group (CLG) — public
 └── Electric/Gas Operations Committee
```

**Dual publishing surface:** `iso-ne.com/committees/...` AND `nepool.com` (parallel site with own calendar + ICS + member directory).

## 2. Top 5 data-center-relevant bodies

| Rank | Body | Cadence | Chair |
|---|---|---|---|
| 1 | **Planning Advisory Committee (PAC)** | ~Monthly | Shounak Abhyankar (ISO-NE) |
| 2 | NEPOOL Participants Committee (NPC) | Monthly | Sec: Sebastian Lombardi |
| 3 | Markets Committee (MC) | Monthly, 2-day sessions | Emily Laine (ISO-NE) |
| 4 | Transmission Committee (TC) | Quarterly | Nick Gangi (ISO-NE) |
| 5 | NESCOE (parallel) | Irregular + filings | Rob Rio (Exec Dir) |

## 3. Publication infrastructure

**URL patterns:**
- ISO committees: `https://www.iso-ne.com/committees/{area}/{committee}`
- Documents CDN: `https://www.iso-ne.com/static-assets/documents/{6-digit-id}/{filename}.pdf`
- NEPOOL calendar: `https://nepool.com/calendar/{YYYY-MM}/`
- NEPOOL docs: `https://nepool.com/wp-content/uploads/{YYYY}/{MM}/{slug}.pdf`
- NESCOE: `https://nescoe.com/wp-content/uploads/{YYYY}/{MM}/{slug}.pdf`

**Feeds (best-in-class for ISO-NE):**
- **NEPOOL ICS (keystone):** `https://nepool.com/calendar/{YYYY-MM}/?ical=1` — valid RFC 5545 VCALENDAR with VEVENTs, LOCATION, CATEGORIES by committee, URL
- **ISO Newswire RSS:** `https://isonewswire.com/feed/` — RSS 2.0, full `<content:encoded>`, hourly, categories, `<pubDate>`
- No RSS on iso-ne.com itself for committee pages

**Agenda lead ~5 business days. Minutes lag 2-6 weeks.** Drafts posted sooner in composite packets.

**Per-committee:**

| Committee | Page | Calendar feed | URL convention |
|---|---|---|---|
| PAC | `/committees/planning/planning-advisory` | None on ISO-NE | `static-assets/documents/{id}/{YYYY_MM_DD}_pac_{slug}.pdf` |
| NPC | `/committees/participants/participants-committee` | NEPOOL ICS | `static-assets/documents/{id}/npc-{YYYY-MM-DD}-composite{N}.pdf` |
| MC | `/committees/markets/markets-committee` | NEPOOL ICS (cat=MC) | `{id}/{aNN}_mc_{YYYY_MM_DD}_{topic}.pdf` (agenda items use `aNN_` prefix) |
| TC | `/committees/transmission/transmission-committee` | NEPOOL ICS (cat=TC) | Same `{id}/..._tc_..._` |
| NESCOE | `nescoe.com` | None | Wordpress path |

## 4. Technical access

Overall: 🟡 Medium (🟢 for news/calendar, 🟡-🔴 for materials discovery)

| Dimension | Score |
|---|---|
| HTML (committee pages) | 🟡 — JS filter widget hydrates from backing JSON |
| PDFs | 🟢 — plain, uncorrupted, large composites (7 MB+) |
| NEPOOL ICS | 🟢 — **the gift** |
| ISO Newswire RSS | 🟢 — full content |
| Auth / CORS | 🟢 — public, no walls |
| Materials enumeration | 🔴 — URL pattern requires scraping committee page to harvest IDs |
| ISO-NE Web Services API | 🟡 — ISO Express market-data only, not stakeholder |
| NESCOE | 🟡 — WordPress, no feed, crawl+diff |

**Architecture:**
- Calendar surface (cheap, high-signal): NEPOOL ICS hourly + ISO Newswire RSS hourly
- Materials surface (expensive, high-value): per-committee scrape every 6h, diff doc list, extract

## 5. Recent data-center actions

| Date | Action |
|---|---|
| Apr 14 2026 | **Maine LD 307 enacted** — statewide DC moratorium ≥20 MW through Nov 2027. First in US. No Jay/Limestone exemption. |
| Mar 30 2026 | **FERC accepts CAR Phase 1** (ER26-925-000) — prompt auction (~1 month pre-delivery); first auction 2028; decouples retirement from auction timing. MOPR already gone after FCA 19. |
| Feb 2026 | **FCA 19 cleared** (first post-MOPR; 2028/29 capacity year) |
| Oct 20 2025 | **Transitional Cluster Study** launched — 26 requests, 8 GW; 21 BESS + 3 wind + 2 solar; mostly MA; report Jun 2026, final Aug 6 2026 |
| Apr 14 2026 | **Spring 2026 Transmission Investment Update** — 2 projects under construction; Maine RFP has 6 proposals, decision Sept 2026 |
| Jan 1 2026 | **Massachusetts large-load tariff statute** — ≥100 MW + >80% load factor customers cover transmission/dist buildout |

NESCOE's [Data Centers Primer](https://nescoe.com/resource-center/data-centers-primer/) is the policy anchor.

## 6. Pipeline recommendation

**Tier 1 (week 1, ~5 hrs):**
1. ISO Newswire RSS — 3 hrs
2. NEPOOL master ICS feed — 2 hrs

**Tier 2 (week 2, ~8-10 hrs):**
3. PAC materials scraper

**Tier 3 (week 3, ~8 hrs):**
4-5. NPC composite watcher + MC/TC + NESCOE

Total: **~25 hrs**.

## 7. Key sources

- [ISO-NE Committees](https://www.iso-ne.com/committees/)
- [Planning Advisory Committee](https://www.iso-ne.com/committees/planning/planning-advisory)
- [NEPOOL calendar](https://nepool.com/calendar/)
- [NEPOOL ICS example](https://nepool.com/calendar/2026-04/?ical=1)
- [ISO Newswire RSS](https://isonewswire.com/feed/)
- [NESCOE](https://nescoe.com/)
- [NESCOE Data Centers Primer](https://nescoe.com/resource-center/data-centers-primer/)
- [Maine LD 307 coverage — Maine Morning Star](https://mainemorningstar.com/2026/04/09/landmark-data-center-moratorium-passes-maine-legislature/)

**Key findings:** Best feed surface of any ISO after NYISO. NEPOOL ICS + ISO Newswire RSS give full calendar + news in structured form. Tier-1 MVP shippable in ~5 hrs. Materials layer is the real work.
