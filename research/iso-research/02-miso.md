# MISO Stakeholder Meeting Infrastructure — Research Report

**Target:** Midcontinent Independent System Operator (MISO)
**Date:** 2026-04-21

## 1. Governance hierarchy

MISO is **sector-based** (11 defined industry sectors elect reps). Advisory Committee is the senior stakeholder body reporting to Board.

**Board of Directors** → **Advisory Committee (AC)** (chair Dan Scripps, MI PSC) →
- Market Subcommittee (MSC)
- Reliability Subcommittee (RSC)
- Planning Advisory Committee (PAC)
- Resource Adequacy Subcommittee (RASC)
- Finance Subcommittee
- Steering Committee
- **Large Load Working Group (LLWG)** ★ data-center-specific, launched 2025
- Interconnection Process Working Group (IPWG)
- Distributed Energy Resources Working Group (DERWG)
- RECB Working Group
- Loss of Load Expectation Working Group
- Planning Subcommittee (PSC)
- Entergy Regional State Committee (ERSC) — MISO South state regs

**Parallel: recurring workshops** — Queue Process, Large Loads Workshops, LRTP, LTLF, Futures, FTR/ARR.

## 2. Top 5 data-center-relevant bodies

| Rank | Committee | Cadence | Chair / Lead |
|---|---|---|---|
| 1 | Large Load Working Group (LLWG) | ~Monthly | Chris Plante (chair) / Marc Keyser (MISO) |
| 2 | Interconnection Process Working Group (IPWG) | Monthly | Erin Murphy / Kyle Trotter |
| 3 | Resource Adequacy Subcommittee (RASC) | Monthly | Werner Roth / Zhaoxia Xie |
| 4 | Planning Advisory Committee (PAC) | Monthly (3rd week) | Cynthia Crane / Jeanna Furnish |
| 5 | Advisory Committee (AC) | Monthly | Dan Scripps / Carmen Clark |

## 3. Publication infrastructure

**URL families:**
- Committee home: `https://www.misoenergy.org/engage/committees/{slug}/`
- Event pages: `https://www.misoenergy.org/events/{YYYY}/{slug}---{month}-{DD}-{YYYY}/` (note triple-dash before date)
- Documents: `https://cdn.misoenergy.org/{URL-Encoded-Title}{6-digit-id}.pdf`

**No native RSS or iCal feeds** on calendar or committee pages. Per-committee mailing lists + general Notifications page. Help Center at `help.misoenergy.org` has structured article IDs.

Agenda lead ~5-7 days; minutes lag 1-2 weeks (often no formal minutes — just slides).

## 4. Technical access / scraping feasibility

Overall: 🟡 Medium

| Vector | Notes |
|---|---|
| Committees/events JSON API | None found |
| iCal / RSS | None advertised |
| HTML structure | Stable, predictable; AJAX-backed dropdowns worth reverse-engineering |
| Event page structure | Highly predictable — `/events/YYYY/{slug}-{month}-DD-YYYY/` trivial to crawl |
| PDF parsing | Required; text-extractable, some older scans need OCR |
| `cdn.misoenergy.org` | Open HTTPS, Fastly-fronted, no auth |
| Auth wall | Registration needed for WebEx / mailing lists; materials pages public |
| Rate limits | Not documented; ≤1 req/sec recommended |

## 5. Recent data-center actions (last 18 months)

| Date | Action | Docket |
|---|---|---|
| Dec 2024 | **LRTP Tranche 2.1 approved** — $21.8B, 24 projects, 3,631-mile 765 kV backbone | MTEP25 Ch 2 |
| Jan 30 2025 | **FERC approves MISO queue cap** (50% of non-coincident peak) | ER25-507 |
| May 16 2025 (reject) → Aug 2025 (accepted refile) | **Expedited Resource Addition Study (ERAS)** | ER25-1674 / ER25-2454 |
| Nov/Dec 2025 | FERC expands queue fast-lane 10 → 15/quarter | ER25-3543 |
| Jan 30 2026 | **Large Load Additions Workshop** — first public draft of Large Load Definition + ZGIA + firm-service step-up | LLWG |
| 2026 | Microsoft–MISO grid modernization partnership (AI tools + Microsoft is largest new load customer) | — |
| Apr 2026 | 35% load-growth forecast: 121 GW (2025) → 163 GW (2035), DC-driven | 2026 LTLF |
| 2026 launching | LRTP Tranche 2.2 + 3 kickoff + LRTP South | MTEP25 Ch 2 |

Geographic DC pressure: Mount Pleasant WI (Microsoft ~1.5 GW), West Des Moines IA (Microsoft $5-6B), Google MN, Meta MN/IA.

## 6. Pipeline recommendation — v1

| Rank | Target | Effort |
|---|---|---|
| 1 | **LLWG** | 4-6 hrs |
| 2 | **IPWG** | 6-8 hrs |
| 3 | **PAC + LRTP workshops** | 8-10 hrs |

Total MISO v1: ~20 hrs + 4 hrs shared plumbing = **~24 hrs**.

## 7. Key sources

- [MISO Committees index](https://www.misoenergy.org/engage/committees/)
- [MISO Large Load Additions](https://www.misoenergy.org/planning/large-loads---container-page/large-load-additions/)
- [LLWG page](https://www.misoenergy.org/engage/committees/large-load-working-group/)
- [Stakeholder Governance Guide PDF](https://cdn.misoenergy.org/Stakeholder%20Governance%20Guide105455.pdf)
- [RTO Insider — MISO Vows Greater Generation Totals for Big Tech in 2026](https://www.rtoinsider.com/122284-miso-vows-greater-generation-totals-for-big-tech-in-2026/)
- [Utility Dive — MISO 35% load jump forecast](https://www.utilitydive.com/news/miso-long-range-forecast-data-center/817917/)

**Key finding:** LLWG is the single highest-signal body. URL patterns are predictable. No feeds, so budget separate calendar-crawler code. Fast MVP at ~4-6 hrs.
