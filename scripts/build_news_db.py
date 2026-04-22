#!/usr/bin/env python3.14
"""
Builds data/news.db (SQLite) of data-center opposition news + social signals,
then exports data/social_events.json for the frontend to consume.

Seed data is hand-curated from the /last30days research run on 2026-04-21.
Future: a cron job runs last30days, parses the raw markdown, and appends here.
"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "news.db"
JSON_PATH = ROOT / "data" / "social_events.json"

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  id TEXT PRIMARY KEY,
  state TEXT NOT NULL,
  city TEXT,
  category TEXT NOT NULL,
  headline TEXT NOT NULL,
  source_domain TEXT,
  source_name TEXT,
  url TEXT,
  date TEXT NOT NULL,
  platform TEXT NOT NULL,
  engagement_score INTEGER DEFAULT 0,
  upvotes INTEGER,
  comments INTEGER,
  views INTEGER,
  likes INTEGER,
  sentiment TEXT,
  companies TEXT,
  first_seen TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_events_state    ON events(state);
CREATE INDEX IF NOT EXISTS idx_events_platform ON events(platform);
CREATE INDEX IF NOT EXISTS idx_events_date     ON events(date);
CREATE INDEX IF NOT EXISTS idx_events_category ON events(category);
"""

EVENTS = [
    # --- News-source events (state + city) ---
    dict(
        id="festus-mo-2026-04-08",
        state="MO", city="Festus",
        category="protested",
        headline="Festus voters oust 4 incumbent council members after $6B AI data center approval",
        source_domain="stlpr.org", source_name="STLPR (NPR)",
        url="https://www.stlpr.org/government-politics-issues/2026-04-08/6b-data-center-festus-voters-oust-every-incumbent-council-member",
        date="2026-04-08", platform="news",
        engagement_score=95, sentiment="negative", companies=[],
    ),
    dict(
        id="independence-mo-2026-04-09",
        state="MO", city="Independence",
        category="protested",
        headline="Independence voters oust councilmembers who gave tax breaks to $6B+ Nebius AI data center",
        source_domain="kcur.org", source_name="KCUR (NPR)",
        url="https://www.kcur.org/politics-elections-and-government/2026-04-09/after-these-independence-councilmembers-supported-an-ai-data-center-voters-ousted-them",
        date="2026-04-09", platform="news",
        engagement_score=88, sentiment="negative", companies=["Nebius"],
    ),
    dict(
        id="temple-tx-2026-04-21",
        state="TX", city="Temple",
        category="protested",
        headline="Temple residents launch recall effort against mayor, council members over data center vote",
        source_domain="kbtx.com", source_name="KBTX",
        url="https://www.kbtx.com/2026/04/21/temple-residents-launch-recall-effort-against-mayor-council-members-over-data-center-vote/",
        date="2026-04-21", platform="news",
        engagement_score=75, sentiment="negative", companies=[],
    ),
    dict(
        id="columbus-ga-2026-04-16",
        state="GA", city="Columbus",
        category="protested",
        headline="Columbus City Council delays data center vote 45 days after resident concerns",
        source_domain="wtvm.com", source_name="WTVM",
        url="https://www.wtvm.com/2026/04/16/columbus-city-council-delays-vote-data-center-project-after-resident-concerns/",
        date="2026-04-16", platform="news",
        engagement_score=70, sentiment="negative", companies=[],
    ),
    dict(
        id="prince-william-va-2026-04-01",
        state="VA", city="Prince William County",
        category="cancelled",
        headline="VA Court of Appeals halts 'Digital Gateway' mega data center rezoning near Manassas battlefield",
        source_domain="virginiamercury.com", source_name="Virginia Mercury",
        url="https://virginiamercury.com/briefs/va-court-of-appeals-stops-major-data-center-development-in-prince-william-county/",
        date="2026-04-01", platform="legal",
        engagement_score=92, sentiment="negative", companies=[],
    ),
    dict(
        id="loudoun-va-2026-03-15",
        state="VA", city="Loudoun County",
        category="protested",
        headline="Loudoun County eliminates by-right data center approval - every project now requires Special Exception",
        source_domain="patch.com", source_name="Ashburn Patch",
        url="https://patch.com/virginia/ashburn/data-center-right-approval-process-removed-loudoun-county",
        date="2026-03-15", platform="news",
        engagement_score=80, sentiment="negative", companies=[],
    ),
    dict(
        id="maine-ld307-2026-04-07",
        state="ME", city=None,
        category="banned",
        headline="Maine LD 307 passes: House 82-62, Senate 19-13 - first statewide data center moratorium (20MW+) through Nov 2027",
        source_domain="cnn.com", source_name="CNN",
        url="https://www.cnn.com/2026/04/12/climate/maine-data-center-ban-bill",
        date="2026-04-07", platform="news",
        engagement_score=100, sentiment="negative", companies=[],
    ),

    # --- Social-platform events (Reddit etc.) ---
    dict(
        id="cumberland-nc-reddit-2026-04-16",
        state="NC", city="Cumberland County",
        category="protested",
        headline="Cumberland County resident quotes Microsoft lawyer at council meeting: 'nobody wants a data center in their backyard'",
        source_domain="reddit.com", source_name="r/PublicFreakout",
        url="https://www.reddit.com/r/PublicFreakout/comments/1smw0i5/cumberland_county_resident_quotes_microsoft/",
        date="2026-04-16", platform="reddit",
        engagement_score=617, upvotes=617, comments=14,
        sentiment="negative", companies=["Microsoft"],
    ),
    dict(
        id="rtechnology-half-delayed-2026-04-04",
        state="US", city=None,
        category="cancelled",
        headline="Half of planned US data center builds have been delayed or canceled - growth limited by power and parts shortages",
        source_domain="reddit.com", source_name="r/technology",
        url="https://www.reddit.com/r/technology/comments/1sbw2p1/half_of_planned_us_data_center_builds_have_been/",
        date="2026-04-04", platform="reddit",
        engagement_score=2638, upvotes=2638, comments=208,
        sentiment="negative", companies=[],
    ),
    dict(
        id="renergy-half-electricity-2026-04-21",
        state="US", city=None,
        category="protested",
        headline="Data centers now account for half of all new US electricity use, just as Americans start to sour on AI",
        source_domain="reddit.com", source_name="r/energy",
        url="https://www.reddit.com/r/energy/comments/1srp4bq/data_centers_now_account_for_half_of_all_new_us/",
        date="2026-04-21", platform="reddit",
        engagement_score=124, upvotes=124, comments=25,
        sentiment="negative", companies=[],
    ),
    dict(
        id="rpublicfreakout-city-council-2026-04-03",
        state="MO", city="Festus",
        category="protested",
        headline="City council votes to approve a $6 billion data center despite public pushback",
        source_domain="reddit.com", source_name="r/PublicFreakout",
        url="https://www.reddit.com/r/PublicFreakout/comments/1sbmroe/city_council_votes_to_approve_a_6_billion_data/",
        date="2026-04-03", platform="reddit",
        engagement_score=6272, upvotes=6272, comments=599,
        sentiment="negative", companies=[],
    ),

    # --- National-level news ---
    dict(
        id="dcwatch-report-2026-04",
        state="US", city=None,
        category="cancelled",
        headline="Data Center Watch: 142 activist groups across 24 states; $18B halted + $46B delayed",
        source_domain="datacenterwatch.org", source_name="Data Center Watch",
        url="https://www.datacenterwatch.org/report",
        date="2026-04-01", platform="news",
        engagement_score=95, sentiment="negative", companies=[],
    ),
    dict(
        id="npr-midterms-2026-04-20",
        state="US", city=None,
        category="protested",
        headline="Data centers are expensive, unpopular - and could be a tipping point in the 2026 midterms",
        source_domain="npr.org", source_name="NPR",
        url="https://www.npr.org/2026/04/20/g-s1-117729/data-center-disputes-local-midterms",
        date="2026-04-20", platform="news",
        engagement_score=90, sentiment="negative", companies=[],
    ),
    dict(
        id="techradar-half-2026-04",
        state="US", city=None,
        category="cancelled",
        headline="Nearly half of US data centers planned for 2026 canceled or delayed",
        source_domain="techradar.com", source_name="TechRadar",
        url="https://www.techradar.com/pro/if-one-piece-of-your-supply-chain-is-delayed-then-your-whole-project-cant-deliver-nearly-half-of-us-data-centers-planned-for-2026-canceled-or-delayed-and-things-could-soon-get-much-worse",
        date="2026-04-01", platform="news",
        engagement_score=85, sentiment="negative", companies=[],
    ),
    dict(
        id="toms-hardware-revolts-2026-04",
        state="US", city=None,
        category="protested",
        headline="Local political revolts threaten to derail US data center projects - hyperscalers facing billions in delays",
        source_domain="tomshardware.com", source_name="Tom's Hardware",
        url="https://www.tomshardware.com/tech-industry/local-political-revolts-threaten-to-derail-us-data-center-projects-mounting-delays-are-already-costing-ai-hyperscalers-billions",
        date="2026-04-01", platform="news",
        engagement_score=82, sentiment="negative", companies=[],
    ),
    dict(
        id="heatmap-nimby-battleground",
        state="US", city=None,
        category="protested",
        headline="Data Centers Are the New NIMBY Battleground",
        source_domain="heatmap.news", source_name="Heatmap",
        url="https://heatmap.news/plus/the-fight/spotlight/data-center-conflicts",
        date="2026-04-01", platform="news",
        engagement_score=78, sentiment="negative", companies=[],
    ),
]


def build_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    for e in EVENTS:
        conn.execute(
            """
            INSERT OR REPLACE INTO events
              (id, state, city, category, headline, source_domain, source_name,
               url, date, platform, engagement_score, upvotes, comments, views,
               likes, sentiment, companies)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                e["id"], e["state"], e.get("city"), e["category"], e["headline"],
                e.get("source_domain"), e.get("source_name"), e.get("url"),
                e["date"], e["platform"],
                e.get("engagement_score", 0),
                e.get("upvotes"), e.get("comments"), e.get("views"), e.get("likes"),
                e.get("sentiment"),
                json.dumps(e.get("companies", [])),
            ),
        )
    conn.commit()
    conn.close()
    print(f"[db] wrote {len(EVENTS)} events to {DB_PATH}")


def export_json() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM events ORDER BY date DESC, engagement_score DESC"
    ).fetchall()
    conn.close()

    items = []
    for r in rows:
        d = dict(r)
        d["companies"] = json.loads(d.get("companies") or "[]")
        items.append(d)

    # Per-state engagement aggregation for the map dots
    by_state: dict[str, dict] = {}
    for it in items:
        st = it["state"]
        if st == "US":
            continue
        agg = by_state.setdefault(
            st,
            {"state": st, "count": 0, "total_engagement": 0,
             "categories": {}, "platforms": {}, "latest_date": ""},
        )
        agg["count"] += 1
        agg["total_engagement"] += int(it.get("engagement_score") or 0)
        agg["categories"][it["category"]] = agg["categories"].get(it["category"], 0) + 1
        agg["platforms"][it["platform"]] = agg["platforms"].get(it["platform"], 0) + 1
        if it["date"] > agg["latest_date"]:
            agg["latest_date"] = it["date"]

    out = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "count": len(items),
        "items": items,
        "by_state": by_state,
    }
    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(JSON_PATH, "w") as f:
        json.dump(out, f, indent=2)
    print(f"[json] wrote {len(items)} items to {JSON_PATH}")


if __name__ == "__main__":
    build_db()
    export_json()
