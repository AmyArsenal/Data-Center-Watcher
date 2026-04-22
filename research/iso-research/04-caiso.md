# CAISO Stakeholder Meeting Infrastructure — Research Report

**Target:** California Independent System Operator
**Date:** 2026-04-21

## 1. Governance hierarchy

CAISO is smaller (~600 staff), state-appointed Board, hybridized with CPUC + CEC. Uses **Stakeholder Initiatives** rather than standing committees — each initiative is a separate workstream.

**Governor (CA)** → **ISO Board of Governors (5)** + **WEM Governing Body** (represents WEIM/EDAM BAs outside CA) jointly govern on EDAM, price formation, CRA.

Board committees: Audit, DMM Oversight, Market Surveillance (MSC — up to 8 meetings/yr, independent academic experts).

**Annual cycles:**
- Market Policy Catalog and Roadmap — 2026 kickoff Jan 15 2026; prioritization workshop Apr 8 2026
- Infrastructure Policy Catalog and Roadmap — newer parallel track

**Market Surveillance Committee (MSC)** — academic advisory. **Department of Market Monitoring (DMM)** — independent in-house monitor.

**CPUC's role (unusually strong):**
- Resource Adequacy proceeding (R.23-10-011; 2026 Slice-of-Day filing guide)
- IRP / LTPP proceeding (R.20-05-003) — CAISO takes portfolios as TPP inputs
- Data-center ratemaking (PG&E large-load rate proposal; OIR Jan 16 2026)

**Legislature:** **SB 57 (Padilla)** signed Oct 11 2025 — mandatory CPUC study on DC cost-shifting due Jan 1 2027. *(User-referenced AB-2863 / SB-X1-8 not found in this window.)*

## 2. Top 5 data-center-relevant initiatives

| Rank | Initiative | Phase (Apr 2026) | Lead |
|---|---|---|---|
| 1 | **Large Loads** | Proposal Development; Issue Paper Jan 30 2026 | Danielle Mills, Ebrahim Rahimi |
| 2 | **2025-2026 TPP** | Draft Plan Apr 7 2026; Board May 2026 | Jeff Billinton |
| 3 | **IPE 5.0** | Decision Apr 30 2026 | Danielle Mills, Bob Emmert |
| 4 | **RA Modeling & Program Design** | Multi-track; T1+T3A approved Oct 30 2025 | Partha Malvadkar |
| 5 | **EDAM** | Go-Live May 1 2026 (PacifiCorp + PGE) | Milos Bosanac |

## 3. Publication infrastructure

**URL conventions:**
- Initiative: `https://stakeholdercenter.caiso.com/StakeholderInitiatives/<slug>`
- Recurring (TPP, RA): `https://stakeholdercenter.caiso.com/RecurringStakeholderProcesses/<slug>`
- Documents: `https://stakeholdercenter.caiso.com/InitiativeDocuments/<filename>.pdf`
- Notices: `https://www.caiso.com/daily-briefing/notices?tag=<tag>-notices`

**Lifecycle (standard for every initiative):**
Scoping → Issue Paper → Straw Proposal → Revised Straw → Draft Final Proposal → Final Proposal → Board Memo → Board Decision → FERC tariff (ER-series) → Implementation / BPM

**Feeds:**
- ICS: **None**
- RSS: **None** on initiative pages (legacy PDF references exist but nothing live)
- **Daily Briefing email (the best bet)** — digest of every notice, M-Th 1:30pm, F 11:30am. Signup at `caiso.com/subscriptions`.
- News Releases email

**Draft comment windows: 14-21 days typical.**

## 4. Technical access

Overall: 🟡 Yellow

| Surface | Score | Notes |
|---|---|---|
| Stakeholder Center initiative pages | 🟢 | Server-rendered, clean slugs, no auth |
| Initiative documents (PDFs) | 🟢 | Direct CDN links, filenames have initiative + type + date |
| Calendar (`/meetings-events/calendar`) | 🟡 | Client-side filter, no .ics or RSS |
| Notice Library (tag-filtered) | 🟢 | Best tractable feed — `?tag=large-loads-notices` pattern |
| Daily Briefing email | 🟢 | Parsable digest |
| OASIS API | 🟢 | Market data only, not stakeholder |
| FERC filings library | 🟢 | `caiso.com/library/ferc-filings-{year}` |
| Auth / CORS | 🟢 | Public |
| Rate limits / robots | 🟡 | Be polite, ~1 req/sec |

**Implication:** Anchor on **Notice Library tag URL + initiative landing + Daily Briefing email**.

## 5. Recent data-center actions

| Date | Action | Source |
|---|---|---|
| Apr 7 2026 | **Draft 2025-2026 Transmission Plan** — 38 upgrades $7B/decade; **South Bay Reinforcement ≥$1B** for 2.5 GW Silicon Valley DC+electrification | RTO Insider, CAISO |
| Jan 30 2026 | **Large Loads Initiative Issue Paper** | [CAISO PDF](https://www.caiso.com/documents/issue-paper-large-load-consideration-jan-20-2026.pdf) |
| Oct 13 2025 → Apr 30 2026 | **IPE 5.0** — caps full-deliverability allocations at lesser of 50% LSE RA share or 500 MW. Cluster 16 opens Oct 1 2026 | [Draft Final Proposal PDF](https://stakeholdercenter.caiso.com/InitiativeDocuments/Draft-Final-Proposal-Interconnection-Process-Enhancements-5-0-Oct-13-2025.pdf) |
| Oct 30 2025 | **RA Modeling Tracks 1 & 3A approved** | CAISO |
| Feb → May 2026 | **EDAM Go-Live w/ PacifiCorp + PGE** | CAISO |
| 2025 | **CPUC rate-design for large loads** (PG&E proposal; OIR Jan 16 2026) | RTO Insider |
| Oct 11 2025 | **SB 57 signed** — CPUC DC cost-shift study due Jan 1 2027 | Padilla |

## 6. Pipeline recommendation — top 3

| Priority | Target | Effort |
|---|---|---|
| 1 | Large Loads initiative page + tag-filtered Notice Library | 8-12 hrs |
| 2 | 2025-2026 TPP + Board meeting PDFs | 12-16 hrs |
| 3 | Daily Briefing email ingest + IPE 5.0 / RA initiative pages | 10-14 hrs |

Total: **~30-42 hrs**. Skip OASIS.

## 7. Key sources

- [CAISO Stakeholder Center](https://stakeholdercenter.caiso.com/)
- [Large Loads initiative](https://stakeholdercenter.caiso.com/StakeholderInitiatives/Large-loads)
- [Large Loads Issue Paper PDF](https://www.caiso.com/documents/issue-paper-large-load-consideration-jan-20-2026.pdf)
- [IPE 5.0 initiative](https://stakeholdercenter.caiso.com/StakeholderInitiatives/Interconnection-process-enhancements-5-0)
- [RA Modeling initiative](https://stakeholdercenter.caiso.com/StakeholderInitiatives/Resource-adequacy-modeling-and-program-design)
- [EDAM initiative](https://stakeholdercenter.caiso.com/StakeholderInitiatives/Extended-day-ahead-market)
- [2025-2026 TPP](https://stakeholdercenter.caiso.com/RecurringStakeholderProcesses/2025-2026-Transmission-planning-process)
- [CAISO Daily Briefing](https://www.caiso.com/daily-briefing)
- [CAISO Subscriptions](https://www.caiso.com/subscriptions)

**Key findings:** No first-class feeds — rely on HTML scraping + email digest. Every initiative follows identical Scoping→Issue Paper→Straw→Draft Final→Final→Board cadence. Best tractable signal = Notice Library tag URLs + Daily Briefing inbox poll.
