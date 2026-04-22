# ERCOT Stakeholder Meeting Infrastructure — Research Report

**Target:** ERCOT + Public Utility Commission of Texas (PUCT)
**Date:** 2026-04-21

## 1. Governance hierarchy

ERCOT is **not FERC-jurisdictional**. PUCT is terminal regulator. Track both.

**Board (12)** — 8 independents + 4 ex officio (CEO, OPUC, PUCT Chair, PUCT Commissioner). Committees: **Reliability & Markets (R&M)**, Finance & Audit, HR & Governance, Technology & Security. Meets ~6x/yr + Annual Members. Livestreamed on Swagit.

**Technical Advisory Committee (TAC)** — top of stakeholder tree. Monthly (last Wednesday). Four subcommittees:
- **Protocol Revision Subcommittee (PRS)** — votes NPRRs
- **Reliability & Operations Subcommittee (ROS)** — votes NOGRRs/PGRRs; parent of PLWG, DWG, SSWG, OWG, OTWG
- **Wholesale Market Subcommittee (WMS)** — parent of WMWG, MSWG, CMWG, QMWG
- **Retail Market Subcommittee (RMS)** — retail, low DC signal

**Working groups direct-to-TAC:**
- **Large Load Working Group (LLWG)** — chair Bob Wittmeyer (DME), VC Patrick Gravois. *THE* data-center forum.
- Large Flexible Load Task Force (LFLTF) — **INACTIVE**; succeeded by LLWG in 2024.
- Planning Working Group (PLWG), Regional Planning Group (RPG), Dynamics WG (DWG), System Protection WG (SPWG)

**PUCT parallel track** — SB 6 (signed Jun 20 2025) triggered 5 rulemaking projects:
- **58479** Transmission cost allocation
- **58480** Large-Load Forecasting Criteria
- **58481** Large-Load Interconnection Standards (16 TAC §25.194) — proposed rule Mar 2026
- **58482** Large-Load Voluntary Demand Reduction Program
- **58484** Net-Metering / Co-Location

## 2. Top 5 data-center-relevant bodies

| Rank | Committee | Cadence | Chair |
|---|---|---|---|
| 1 | **LLWG** | Monthly (Thursday); 12/yr in 2026 | Bob Wittmeyer / Patrick Gravois |
| 2 | TAC | Monthly (last Wed) | Rotating market-participant |
| 3 | ROS | Monthly (1st Thursday) | Rotating |
| 4 | PRS | Monthly (~3rd Thursday) | Rotating |
| 5 | Regional Planning Group (RPG) | Monthly, often co-scheduled w/ PLWG | ERCOT TP staff |

## 3. Publication infrastructure

**URL patterns:**
- Committee landing: `https://www.ercot.com/committees/{parent}/{child}` — e.g. `/committees/tac/llwg`
- Event pages (2 patterns): `/calendar/{MMDDYYYY}-{Slug}-Meeting` OR legacy `/calendar/event?id={epoch-ms}`
- Materials: `https://www.ercot.com/files/docs/{YYYY}/{MM}/{DD}/{filename}`
- Formats: PDF, PPTX, DOC/DOCX, XLSX

**Agenda lead ~3-7 days** for LLWG, **7 days** for TAC/ROS/WMS/PRS. Minutes appear on next meeting's packet (~30 days).

**No .ics / RSS on master calendar.** Subscribe via per-WG email lists (e.g., `llwg@lists.ercot.com`) and Market Notices.

**NPRR/NOGRR/PGRR tracker (the crown jewel):**

| Type | Index | Pending | Per-issue |
|---|---|---|---|
| NPRR | `/mktrules/issues/nprr` | `/mktrules/issues/reports/nprr/pending` | `/mktrules/issues/NPRR{NNNN}` |
| NOGRR | `/mktrules/issues/nogrr` | `/mktrules/issues/reports/nogrr/pending` | `/mktrules/issues/NOGRR{NNN}` |
| PGRR | `/mktrules/issues/pgrr` | `/mktrules/issues/reports/pgrr/pending` | `/mktrules/issues/PGRR{NNN}` |

Monotonic IDs — ideal for "what's new since N" polling.

**PUCT publications:**
- Interchange: `https://interchange.puc.texas.gov/` — deterministic `/Documents/{CONTROL}_{ITEM}_{FILINGID}.PDF`
- Open Meetings **RSS feed** at `https://www.puc.texas.gov/agency/calendar/agendas/Default.aspx` (the one true feed in the stack)
- Broadcasts/archive + AdminMonitor

## 4. Technical access

| Target | Score | Notes |
|---|---|---|
| ERCOT HTML pages | 🟡 | **403 on WebFetch** — Akamai/Cloudflare edge. Need UA spoofing + sometimes headless browser. |
| `/files/docs/` PDFs | 🟡 | Same 403 gate; once past, clean filenames |
| ERCOT Public API (`apiexplorer.ercot.com`) | 🟢 | OAuth2, registration required. **Market data only** — no stakeholder feed. |
| ERCOT Market Notices | 🟡 | Email best; archive scrapable with spoofing |
| PUCT Interchange | 🟢 | ASP.NET stack, deterministic URLs |
| PUCT Open Meetings RSS | 🟢 | Public RSS feed |

## 5. Recent data-center / large-load actions

### NOGRR282 / NPRR1308 — Large Electronic Load Ride-Through
Filed Nov 14 2025. Mandatory VRT for LELs ≥75 MW. LLWG + Board 12/8/2025. [Board item 6.2](https://www.ercot.com/files/docs/2025/12/01/6.2-NOGRR282-Large-Electronic-Load-Ride-Through-Requirements-and-NPRR1308.pdf)

### Batch Study / PGRR145 / NPRR1325 — Large Load Interconnection Overhaul
**410 GW** of large-load interconnection requests (~87% DC) against 85 GW peak. PGRR145 + NPRR1325 filed Mar 4 2026; PRS vote May 6 2026; ROS May 7 2026; Board deadline Jun 1 2026. Developers without executed IAs by Jul 15 2026 lose queue position.

### Texas SB 6 + PUCT Project 58481
Draft rule 16 TAC §25.194 published Mar 2026. Non-refundable study fees $50,000–$100,000/MW, site-control proof, affiliate disclosure, backup-generation mandates.

### PUCT Project 58484 — Co-Location / BTM
SB 6 restricts new co-located Large Loads (≥75 MW) paired w/ existing grid-facing generator (as of Sep 1 2025). Requires ERCOT reliability study + PUCT approval.

### Permian Basin Reliability Plan / 765 kV
PUCT approved Apr 24 2025. ERCOT projects Permian demand 11.1 GW (2026) → 26.4 GW (2038), 2.4x, DC/crypto driven.

### Mandatory Curtailment (PUCT 58482)
Post-2025 Large Loads (≥75 MW) curtailed during firm load-shed. Voluntary Large Load Demand Management Service procured competitively.

## 6. Pipeline recommendation — top 3

| Rank | Feed | Effort |
|---|---|---|
| 1 | **LLWG materials** | 18-24 hrs (edge protection + PDF/PPTX + LLM summary) |
| 2 | **NPRR/NOGRR/PGRR tracker** | 12-16 hrs (monotonic IDs, daily poll, relevance classifier) |
| 3 | **PUCT Interchange: 58479-58484 + Open Meetings RSS** | 14-18 hrs |

Total: **~45-60 hrs**. Skip WMS/RMS for v1; revisit RPG/PLWG in v2.

## 7. Key sources

- [ERCOT Committees](https://www.ercot.com/committees)
- [ERCOT LLWG](https://www.ercot.com/committees/tac/llwg)
- [ERCOT NPRR Tracker](https://www.ercot.com/mktrules/issues/nprr)
- [ERCOT Public API Explorer](https://apiexplorer.ercot.com/)
- [PUCT Interchange](https://interchange.puc.texas.gov/)
- [PUCT Project 58481](https://interchange.puc.texas.gov/Search/Filings?ControlNumber=58481)
- [Perkins Coie — SB 6 Implementation Tracker](https://perkinscoie.com/insights/update/sb-6-implementation-shaping-data-center-future-texas)
- [ERCOT 2025 Constraints Report](https://www.ercot.com/files/docs/2025/12/23/2025-Report-on-Existing-and-Potential-Electric-System-Constraints-and-Needs.pdf)

**Key findings:** LLWG uncontested #1. ERCOT blocks naive WebFetch — plan for header-spoofing. NPRR monotonic IDs are the best feed substitute. PUCT matters as much as ERCOT for DCs.
