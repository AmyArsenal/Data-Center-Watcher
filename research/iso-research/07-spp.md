# SPP — Stakeholder Meeting Intelligence Report

**Target:** Southwest Power Pool (14 states; emerging Markets+ in WECC)
**Date:** 2026-04-21

## 1. Governance hierarchy

State regulators have real voting authority (RSC). MOPC is dominant technical body. FERC regulates tariff; NERC sets reliability.

```
FERC ──┐                ┌── NERC
       │                │
SPP BOARD OF DIRECTORS (quarterly)
  Chair: Raymond Hepper
  Vice: Stuart Solomon
  8 independent directors
  ├── Members Committee (~20 member reps, advises Board)
  ├── Regional State Committee (RSC, quarterly; 12 states voting)
  │     Chair: Chuck Hutchison (NE PRB)
  │     └── Cost Allocation WG (CAWG) — monthly; Chair John Krajewski
  ├── Board Committees (Corp Gov, Finance, HR, Oversight, Strategic Planning, CPPTF)
  │
  ├── MOPC (Markets & Operations Policy Committee)
  │     Meets 2x/yr (July + October)
  │     Chair: Joe Lang (OPPD); V-Chair: Olivia Hough (CU Springfield)
  │     ├── Economic Studies WG (ESWG) — monthly virtual + 2x/yr F2F
  │     ├── Market WG, Operating Reliability WG, Project Cost WG
  │     ├── Regional Tariff WG, Supply Adequacy WG, Transmission WG
  │     ├── Order 2222 Task Force, TOSP Task Force
  │
  └── (Retired: HITT — Holistic Integrated Tariff Team, closed Apr 2025)
```

**Markets+ (parallel, WECC expansion):** FERC-accepted tariff Jan 16 2025; go-live Oct 2027. MPEC (Markets+ Participant Executive Committee, 3x/yr) + 5 WGs. ~40 entities committed to Phase Two.

## 2. Top 5 data-center-relevant bodies

| Rank | Body | Why | Cadence |
|---|---|---|---|
| 1 | **MOPC** | All HILL/CPP/ITP tariff changes pass through here | **2x/year (July + October)** |
| 2 | **Board / Members Committee** | Final stakeholder vote | Quarterly + Dec virtual |
| 3 | **Regional State Committee (RSC)** | State regulator voting; cost-allocation owner | Quarterly |
| 4 | **Consolidated Planning Process Task Force (CPPTF)** | Designed CPP; now implementing | Monthly |
| 5 | **Economic Studies WG (ESWG)** | Load Review / large-spot-load approvals into ITP | Monthly + 2x/yr F2F + joint TWG |

## 3. Publication infrastructure

**Two-layer system:**
1. Calendar: `https://www.spp.org/events/` and `/calendar-list/{slug}-{YYYYMMDD}/`
2. Documents: `/spp-documents-filings/?id={folder_id}` — folder-based, **opaque numeric IDs, no stable hierarchy**

**URL conventions:**
- Events: `/calendar-list/{group-slug}-{type}-{YYYYMMDD}/`
- Docs: `/documents/{doc_id}/{slug-with-urlencoded-spaces}.pdf` — e.g. `spp.org/documents/75217/eswg%20meeting%20minutes%2020251030.pdf`
- News: `/news-list/{slug}/`, `/newsroom/press-releases/`

**Feeds:**
- **.ics: NONE**
- **RSS: NONE**
- **Public API: NONE** (OpsPortal has operational data, not meetings)
- **Search:** yes, via Documents & Filings (filtered + full-text, no API)

**CRITICAL CAVEAT — unstructured document store:**
- Folder IDs change without warning, no public index
- Inconsistent filenames (URL-encoded spaces, mixed casing, ad-hoc date formats)
- Same doc posted in multiple folders
- No "latest" aliases
- Drafts silently replaced by finals at same URL
- PDF metadata unreliable

**Per-committee lead/lag:**

| Committee | Agenda lead | Minutes lag |
|---|---|---|
| MOPC | ~2 weeks | ~4-6 weeks |
| Board/MC | ~2 weeks | ~4-6 weeks |
| RSC | ~1-2 weeks | ~4 weeks |
| CPPTF | ~1 week | ~2-4 weeks |
| ESWG | ~1 week | ~3-6 weeks (`eswg%20meeting%20minutes%20YYYYMMDD.pdf`) |

## 4. Technical access

Overall: 🟡 Yellow (trends 🔴 for materials)

| Dimension | Score |
|---|---|
| HTML structure (calendar-list) | 🟢 |
| PDF-heavy materials | 🟡 |
| Feed availability | 🔴 |
| Auth walls | 🟡 (RMS Stakeholder Center gated; public calendar + most docs open) |
| Robots / rate limits | 🟡 (none published; ~1 req/sec) |
| CORS | 🟢 (server-side) |
| OpsPortal | 🟢 (GI queue, DISIS/CPP tracking) |
| Folder-ID stability | 🔴 — hand-curated registry needed |

**Net:** Plan for hand-curated folder-ID registry + periodic full-tree crawls + RTO Insider SPP briefs as secondary signal.

## 5. Recent data-center actions (last 18 months)

| Date | Action | Docket | Outcome |
|---|---|---|---|
| Oct 10 2025 | **Provisional Load Process (OATT Att. AX)** accepted | ER25-2430-000/001; RR 672 | Effective retroactive Aug 4 2025. Since 2020: 26.4 GW of >100 MW load requests, 9 GW disclosed as DCs |
| Sep 2025 → Jan 14 2026 | **HILL / HILLGA (RR 696)** approved | ER26-247 | Accepted Jan 14 2026; effective Jan 15 2026. First-in-nation fast-lane for data-center + BTM gen co-study |
| Feb 10 2026 | **CHILLS refile** | ER26-series pending | Requested FERC action by mid-April 2026; target Jul 1 2026 |
| Aug 2025 → Mar 13 2026 | **Consolidated Planning Process (CPP)** approved by FERC | ER26-414-000 | Effective Mar 1 2026. Merges ITP + DISIS. First window Apr 2026; first portfolio 2028. Commissioner Rosner called it "bold step" |
| Nov 2025 | **2025 ITP portfolio $8.6B approved** | — | Largest annual in SPP history. Of 166 GW forecast peak growth, ~90 GW linked to DCs |
| 2024-2026 | **Winter PRM step-up:** 12% → 15% (Winter 2025/26) → 36% (Winter 2026/27) | RSC-led | Raises capacity obligations for LREs hosting DC loads (OPPD / Google Omaha) |

**Major DC developer activity:**
- **Google Omaha/Lincoln NE** — OPPD +600 MW accredited since 2023; projecting +100 MW/yr; possible 1-3 GW new NE facility
- **Google OK** — $9B AI expansion announced
- **Jericho Energy Ventures OK** — 20 MW via 345 kV line, active Jan 2026
- **CleanSpark Cheyenne WY** — 100 MW (beat Microsoft), crypto+AI, 6-mo deployment
- **Oklahoma BTM bill** — signed May 2025; DCs can self-generate, state-level end-run on SPP tariff

## 6. Pipeline recommendation — top 3

| Rank | Target | Effort |
|---|---|---|
| 1 | MOPC + Board/MC calendar + materials | 12 hrs |
| 2 | RSC + CAWG materials | 8 hrs |
| 3 | CPPTF + ESWG minutes | 10 hrs |

**Total MVP ~30 hrs** including:
- Calendar crawler — 4 hrs
- Folder-ID registry (hand-curate ~15 top folders) — 3 hrs
- PDF ingestion — 10 hrs
- RTO Insider secondary-source poller (pattern `/{id}-spp-{committee}-{MMDDYY}/`) — 4 hrs
- DC keyword/entity extractor — 6 hrs
- FERC docket watcher (ER25-2430, ER26-247, ER26-414) — 3 hrs

## 7. Key sources

- [SPP Governance](https://www.spp.org/governance/)
- [MOPC page](https://www.spp.org/stakeholder-groups-list/organizational-groups/board-of-directorsmembers-committee/markets-and-operations-policy-committee/)
- [RSC page](https://www.spp.org/stakeholder-groups-list/organizational-groups/regional-state-committee/)
- [CPPTF page](https://www.spp.org/stakeholder-groups-list/organizational-groups/board-of-directorsmembers-committee/consolidated-planning-process-task-force/)
- [SPP HILL Integration](https://www.spp.org/markets-operations/high-impact-large-load-hill-integration/)
- [SPP Events Calendar](https://www.spp.org/events/)
- [SPP Documents & Filings](https://www.spp.org/spp-documents-filings/)
- [RTO Insider SPP MOPC Briefs pattern](https://www.rtoinsider.com/110443-spp-markets-operations-policy-comm-071525/)

**Key findings:**
1. SPP is the hardest of the 7 to scrape. Budget the curation work.
2. MOPC meets **only twice per year** — fewer but denser events.
3. HILL / HILLGA / CHILLS / CPP / GRID-C cluster is the hottest DC storyline.
4. Nebraska PRB chairs both RSC and CAWG — Nebraska is the canary state given Google Omaha.
5. Markets+ is 2027-go-live parallel track — low DC relevance today, matters later.
