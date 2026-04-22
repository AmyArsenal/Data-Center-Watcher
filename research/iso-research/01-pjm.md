# PJM Interconnection — Stakeholder Meeting Infrastructure Research Report

*Prepared for: "RTO Insider for AI Agents" v1 pipeline design*
*Date: 2026-04-21*
*Scope: PJM (13 states + DC, ~66M customers, highest data-center load growth of any US ISO)*

---

## 1. Governance Hierarchy

PJM's stakeholder governance is a pyramidal structure codified in Manual 34: Stakeholder Process. Decisions bubble up through sector-weighted voting at each level before reaching the Board.

```
PJM Board of Managers (10 directors, final authority)
│
├── Members Committee (MC)  ← sector-weighted voting body
│   ├── Markets & Reliability Committee (MRC)  ← senior standing cmte
│   │   ├── Market Implementation Committee (MIC)
│   │   │   ├── Cost Development Subcommittee (CDS)
│   │   │   ├── Demand Response Subcommittee (DRS)
│   │   │   └── Energy Price Formation Senior Task Force
│   │   ├── Operating Committee (OC)
│   │   ├── Planning Committee (PC)
│   │   │   ├── Interconnection Process Subcommittee (IPS)
│   │   │   ├── Load Analysis Subcommittee (LAS)  ★ data-center hot seat
│   │   │   ├── Resource Adequacy Analysis Subcommittee (RAAS)
│   │   │   ├── Transmission & Substation Subcommittee
│   │   │   └── Distributed Resources Subcommittee
│   │   └── Risk Management Committee (RMC)
│   └── Liaison Committee
│
├── Transmission Expansion Advisory Committee (TEAC)
│   ├── SRRTEP-Mid-Atlantic / Southern / Western
│
├── Critical Issue Fast Path — Large Load Additions (CIFP-LLA)  ★ ad hoc
│     Concluded with Board Decisional Letter Jan 16 2026
│
└── Inter-Regional Planning Stakeholder Advisory Cmtes (IPSAC)
      ├── IPSAC-Midwest (joint w/ MISO)
      └── IPSAC-NY/NE (joint w/ NYISO + ISO-NE)
```

**Nomenclature note:** Use **LAS** (not "LASC"), **IPS** (not "IPSAC" for domestic), **TEAC** + **SRRTEP** (not "RTEPC"). CDS is Cost Development, not capacity market — capacity work happens at **MIC** and **RAAS**.

---

## 2. Top 5 data-center-relevant bodies

| Rank | Body | Cadence | Chair |
|---|---|---|---|
| 1 | CIFP-LLA | Bi-weekly when active (now dormant) | PJM staff / David Mills (Board Chair) |
| 2 | Load Analysis Subcommittee (LAS) | ~8-10/yr, heavier Sep-Nov | Dean Manno |
| 3 | Planning Committee (PC) | Monthly, 1st Tuesday | Megan Heater |
| 4 | Interconnection Process Subcommittee (IPS) | Monthly, 4th Monday | Amanda Martin |
| 5 | MRC + MC (paired) | Monthly, 4th Wednesday | Lisa Drauschak / Jason Barker |

## 3. Publication infrastructure

**Universal URL conventions (verified):**
- Landing: `https://www.pjm.com/committees-and-groups/committees/{code}`
- Materials: `https://www.pjm.com/-/media/DotCom/committees-groups/{type}/{code}/{YYYY}/{YYYYMMDD}/`
- Agenda: `{YYYYMMDD}-agenda.pdf`
- Minutes: `{YYYYMMDD}-consent-agenda-a---draft-{cmte}-minutes---{MDDYYYY}.pdf`
- Numbered items: `{YYYYMMDD}-item-{NN[letter]}---{slug}.pdf`

**RSS feeds (verified):**
- Inside Lines blog: `https://insidelines.pjm.com/feed/`
- News releases: `https://www.pjm.com/about-pjm/newsroom.aspx?news=All&rss=1`
- Ex-Parte letters: `https://www.pjm.com/about-pjm/who-we-are/pjm-board/public-disclosures.aspx?publicdisclosures=All&rss=1`
- All committee meetings: `https://www.pjm.com/committees-and-groups.aspx?meetings=All&rss=1`
- Category indexes: `/about-pjm/newsroom/rss-feeds/rss-feeds-committees`, `.../rss-feeds-subcommittees`, etc.

**Per-committee detail:**

| Committee | Landing | Agenda lead | Minutes lag |
|---|---|---|---|
| MC | `/committees-and-groups/committees/mc` | ~7 days | ~30 days |
| MRC | `/committees-and-groups/committees/mrc` | ~7 days | ~30 days |
| MIC | `/committees-and-groups/committees/mic` | 3-7 days | ~30 days |
| PC | `/committees-and-groups/committees/pc` | ~5 days | ~30 days |
| IPS | `/committees-and-groups/subcommittees/ips` | 5-7 days | ~30 days |
| LAS | `/committees-and-groups/subcommittees/las` | ~3 days (tightest) | ~30 days |
| TEAC | `/committees-and-groups/committees/teac` | ~7 days | ~30 days |
| CIFP-LLA | `/committees-and-groups/cifp-lla` | Variable 2-14 days | ad hoc |

## 4. Technical access / scraping feasibility

| Committee | Difficulty | Notes |
|---|---|---|
| MC / MRC / PC / IPS | 🟢 Low | Predictable URLs, static PDFs, open |
| MIC / TEAC / LAS | 🟡 Medium | 20+ numbered items per meeting; tight lead time on LAS |
| CIFP-LLA | 🔴 Hard when active | 12-package vote cycle = ~150 PDFs |

- **No JSON APIs for stakeholder content.** Data Miner 2 + API Portal are markets-only.
- **Sitecore CMS stable 3+ years** — low structural-break risk.
- **No CORS issues** for server-side scraping.
- **No auth on committee materials.** Member-only content is on pjm.my.site.com (Salesforce).
- **No published rate limits.** Be ≤1 req/sec with UA.

## 5. Recent data-center actions (last 18 months)

| Action | Date | Docket | Outcome |
|---|---|---|---|
| Amazon-Talen Susquehanna Amended ISA | Filed Jun 2024; FERC rejected Nov 2024; rehearing denied Apr 2025 | FERC EL24-82 / ER24-2172 | 2-1 rejected, Talen appealing |
| FERC show-cause on PJM co-location | Initiated Feb 2025; Order Dec 18 2025 | FERC EL25-49-000 | PJM must file tariff revisions Jan 20 2026; FERC to act by Jun 2026 |
| 2025/26 Base Residual Auction | Cleared Jul 2024 | PJM RPM BRA | **$269.92/MW-day** (up from $28.92); ~$14.7B total; 5,250 MW new load mostly DC |
| 2027/28 BRA | Dec 17 2025 | PJM RPM BRA | 134,479 MW procured; ~5.6% short of reliability req |
| CIFP-LLA Board Decisional Letter | Jan 16 2026 | PJM CIFP-LLA | Accepted blended package from 12 stakeholder proposals; ≥50 MW at POI defines "large load" |
| Manual 14H / RGIS | Effective May 20 2026; 14A/14E retired Jun 30 2026 | PC docket | Fast CIR transfer to replacement at same POI |

## 6. Pipeline recommendation — top 3 for v1

| Priority | Body | Effort |
|---|---|---|
| #1 | Load Analysis Subcommittee (LAS) | ~12 hrs — URL generator + RSS poller + PDF table extraction |
| #2 | Planning Committee (PC) + IPS | ~8 hrs combined |
| #3 | Members Committee (MC) + MRC (paired) | ~6 hrs |

Total PJM v1: **~26 hrs scraper + ~16 hrs PDF-to-structured + ~8 hrs dedupe = ~50 hrs**.

## 7. Key sources

- [PJM Committees & Groups index](https://www.pjm.com/committees-and-groups/committees)
- [PJM Meeting Center](https://www.pjm.com/committees-and-groups/meeting-center.aspx)
- [PJM RSS Feeds index](https://www.pjm.com/en/about-pjm/newsroom/rss-feeds)
- [PJM Manual 34: Stakeholder Process](https://www.pjm.com/-/media/DotCom/documents/manuals/m34.pdf)
- [FERC Fact Sheet — PJM co-location order (EL25-49)](https://www.ferc.gov/news-events/news/fact-sheet-ferc-directs-nations-largest-grid-operator-create-new-rules-embrace)
- [PJM Board Decisional Letter on CIFP-LLA](https://www.pjm.com/-/media/DotCom/about-pjm/who-we-are/public-disclosures/2026/20260116-pjm-board-letter-re-results-of-the-cifp-process-large-load-additions.pdf)

**Key finding:** PJM is the **easiest of the 7 ISOs to scrape** once you know the URL convention. Deterministic paths under `pjm.com/-/media/DotCom/committees-groups/`, RSS for discovery, no CORS issues, no login walls. Make PJM scraper #1.
