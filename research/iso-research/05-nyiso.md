# NYISO Stakeholder Meeting Infrastructure — Research Report

**Target:** NYISO
**Date:** 2026-04-21

## 1. Governance hierarchy

Compact, 3-tier structure. MC + BIC + OC parallel up into Management Committee.

**Board of Directors** → **Management Committee (MC)** → **Business Issues Committee (BIC)** | **Operating Committee (OC)**

**Under BIC:**
- Billing Accounting & Credit Policy WG (BACWG)
- Business Intelligence Task Force
- Electric Gas Coordination WG
- **Electric System Planning WG (ESPWG)** ★
- **Installed Capacity WG (ICAPWG)** ★
- **Load Forecasting Task Force (LFTF)** ★
- Market Issues WG
- Price-Responsive Load WG

**Under OC:**
- **Transmission Planning Advisory Subcommittee (TPAS)** ★
- System Operations / Protection Advisory Subcommittees
- Communication & Data Advisory Subcommittee
- **Interconnection Project Facilities Study WG (IPFSWG)** ★
- Inter-area Planning Stakeholder Advisory Committee (IPSAC)
- **Interconnection Issues Task Force (IITF)**

**State-side parallel: NYPSC Case 26-E-0045** — *Proactive Planning for Upgraded Electric Grid Infrastructure*. Instituted Feb 12 2026; initial comments Apr 13 2026, replies May 13 2026, tech conf Dec 31 2026, staff whitepaper Feb 12 2027.

**Note:** No "LFITF" body at NYISO. Large Facility Interconnection Requests (LFIRs) governed by **IPFSWG** (Class Year) and **IITF** (policy). Large-load reform is at **TPAS/ESPWG/LFTF**.

## 2. Top 5 data-center-relevant committees

| Rank | Committee | Cadence | Liaison |
|---|---|---|---|
| 1 | **ICAPWG** | 2-3x/month | Debbie Eckels |
| 2 | **ESPWG** | Monthly | Kirk Dixon |
| 3 | **TPAS** | Monthly | Kirk Dixon |
| 4 | **LFTF** | Quarterly-ish | Kirk Dixon |
| 5 | **IPFSWG** | Monthly during active Class Years | Kirk Dixon |

## 3. Publication infrastructure

**URL patterns:**
- Committee landing: `https://www.nyiso.com/{acronym}` — e.g., `/icapwg`, `/espwg`, `/tpas`, `/lftf`, `/ipfswg`
- Documents: `https://www.nyiso.com/documents/20142/{folder_id}/{filename}.pdf/{hash}?t={timestamp}` (Liferay CMS, inconsistent filenames)

**iCal feeds (keystone asset — 5 webcal URLs):**
- MC: `webcal://www.nyiso.com/o/oasis-rest/calendar/export/44327.ics`
- BIC: `webcal://www.nyiso.com/o/oasis-rest/calendar/export/44334.ics`
- OC: `webcal://www.nyiso.com/o/oasis-rest/calendar/export/2167912.ics`
- General: `webcal://www.nyiso.com/o/oasis-rest/calendar/export/3842422.ics`
- Training: `webcal://www.nyiso.com/o/oasis-rest/calendar/export/39568.ics`

Per NYISO: **"subscribing to a Parent committee will subscribe you to all associated subcommittee and events."** MC/BIC/OC covers every working group.

**No RSS anywhere on nyiso.com.**

**Agenda lead ~5 business days.** Minutes lag 2-3 weeks for formal; WG materials often same-day.

**MyNYISO account** required for gated "Committee File Browser" — but most underlying PDFs are indexable via direct URL.

## 4. Technical access

Overall: 🟡 Yellow

| Asset | Score | Notes |
|---|---|---|
| Committee iCal feeds | 🟢 | 5 feeds, RFC 5545, anonymous, near real-time |
| Meeting PDFs (public) | 🟡 | Stable URLs once discovered; no listing API; must crawl file-browser HTML |
| CEII/MyNYISO-gated materials | 🔴 | Account + NDA |
| RSS feeds | 🔴 | None |
| Blog / press releases | 🟢 | HTML, no auth |
| NYISO Market OASIS (different) | 🟢 | Market data only |
| NYPSC DPS doc system | 🟡 | DocRefId GUID URLs, slow, fickle search |
| CORS / auth | 🟡 | Public pages anonymous fetch OK |

**Access pattern:**
1. Poll 3 parent iCal feeds (MC + BIC + OC) every 30-60 min
2. For each VEVENT, fetch committee landing + event-list widget to find Liferay folder
3. Crawl folder for PDF URLs: regex `/documents/20142/\d+/[^/]+\.pdf`
4. Re-crawl each event 24h and 72h post-meeting for late-posted minutes
5. Supplement with NYPSC DPS filtered on Case 26-E-0045

## 5. Recent data-center actions

| Date | Action | Source |
|---|---|---|
| Feb 12 2026 | **NYPSC Case 26-E-0045** — large-load cost-allocation proceeding | [Governor Hochul](https://www.governor.ny.gov/news/governor-hochul-announces-psc-proceeding-her-plan-ensure-data-centers-pay-their-fair-share) |
| Feb → Dec 2026 | **NYISO Large-Load Interconnection Reform** — straw Jun-Jul 2026, tariff Aug 2026, FERC filing Dec 2026. ~11.9 GW of large-load queue; 8.3 GW added in 2025 | Harris Beach Murtha |
| Oct 2025+ | **Indian Point 200 MW DC inquiry (Holtec)** — ~1M sq ft hyperscale AI DC on decommissioned site; Hochul endorsed; possible $10B SMR restart | Peekskill Herald, POWER |
| Jan 28 2025 | **2025-2029 DCR accepted by FERC** — first DCR after Capacity Accreditation construct; Oct 28 2025 supplemental for CHPE bifurcation | Troutman |
| 2022 → 2025 | Energy-Intensive Projects queue: 6 projects / 1,045 MW (2022) → 48 projects / ~12 GW (end-2025). 2,500-4,000 MW expected on system by 2035 | NYISO, NYPSC |
| Nov 3-4 2025 | **Phase 1 of 2024 Cluster Study** | RTO Insider |

## 6. Pipeline recommendation — v1

| Tier | Feed | Effort |
|---|---|---|
| 1 | iCal parent feeds (MC + BIC + OC) | 4 hrs |
| 2 | NYPSC Case 26-E-0045 docket monitor | 6 hrs |
| 3 | Committee scraper: ICAPWG + ESPWG + TPAS + LFTF | 10-14 hrs |

Total MVP: **18-26 hrs**. Skip IPFSWG for v1 (CEII-gated).

## 7. Key sources

- [NYISO Committees](https://www.nyiso.com/committees)
- [NYISO Calendar Subscription](https://www.nyiso.com/calendar-subscription)
- [NYPSC Case 26-E-0045](https://documents.dps.ny.gov/public/Common/ViewDoc.aspx?DocRefId=%7B5064FE9A-0000-CF11-8DCC-2EB1053709C9%7D)
- [Governor Hochul Energize NY announcement](https://www.governor.ny.gov/news/governor-hochul-announces-psc-proceeding-her-plan-ensure-data-centers-pay-their-fair-share)
- [Harris Beach Murtha — NYISO large-load reform analysis](https://www.harrisbeachmurtha.com/insights/nyiso-considers-revisions-to-large-load-interconnection-process/)

**Key findings:** Three parent ICS feeds are the keystone asset. PDFs discoverable via Liferay URL regex. MyNYISO adds gated content but most PDFs reachable without account. NYPSC is co-primary — Case 26-E-0045 sets the cost rules.
