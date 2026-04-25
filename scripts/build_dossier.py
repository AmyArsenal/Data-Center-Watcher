#!/usr/bin/env python3
"""Build per-state and per-county risk dossiers + a versioned static API.

This is the "Get Data" payload — when a developer (or BI tool) asks
"what's happening in Loudoun County?" or "give me everything for VA",
they hit one of these JSON files directly via the Pages CDN.

Outputs (committed to data/, served by Pages):

    data/dossiers/state-VA.json                 ← per-state rollup
    data/dossiers/county-51107.json             ← per-county (FIPS-keyed)
    data/dossiers/index.json                    ← directory of all dossiers

    data/api/v1/states.json                     ← all states + risk score
    data/api/v1/states/{XX}.json                ← one state, full dossier
    data/api/v1/counties.json                   ← all counties with activity
    data/api/v1/counties/{fips}.json            ← one county, full dossier
    data/api/v1/actions.json                    ← all actions (paged)
    data/api/v1/actions/issue/{tag}.json        ← actions filtered by issue
    data/api/v1/actions/outcome/{outcome}.json  ← actions filtered by outcome
    data/api/v1/exports/all_actions.csv         ← Pro-tier CSV download

Risk score (0–100) — composite, developer POV:
    + 40 × tier_weight    (restrictive 1.0, protective 0.6, supportive 0.0)
    + 25 × engagement     (sum of opposition_groups + petitions + sources count)
    + 20 × recency        (events in 30d count 3×, 90d count 1×, older 0.3×)
    + 10 × multi-source   (avg sources_seen > 1 = +10)
    +  5 × regulatory     (any enacted moratorium = +5)

Run locally to refresh now:
    python3 scripts/build_dossier.py
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from lib.geo    import resolve_county   # noqa: E402
from lib.schema import migrate          # noqa: E402

DB_PATH      = ROOT / "data" / "news.db"
DOSSIER_DIR  = ROOT / "data" / "dossiers"
API_DIR      = ROOT / "data" / "api" / "v1"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("dossier")


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_json(s):
    if not s: return []
    try: return json.loads(s)
    except json.JSONDecodeError: return []


# ---- Risk scoring -----------------------------------------------------

_TIER_WEIGHT = {"restrictive": 1.0, "protective": 0.6, "supportive": 0.0, "unclear": 0.3}


def _recency_weight(date_str: str | None) -> float:
    if not date_str: return 0.3
    try:
        days_ago = (datetime.now(timezone.utc).date()
                    - datetime.strptime(date_str[:10], "%Y-%m-%d").date()).days
    except ValueError:
        return 0.3
    if days_ago <= 30:  return 3.0
    if days_ago <= 90:  return 1.0
    if days_ago <= 365: return 0.3
    return 0.1


def _risk_score(actions: list[dict]) -> dict:
    """Returns {'score', 'tier_component', 'recency_component', etc.}."""
    if not actions:
        return {"score": 0, "tier": 0, "engagement": 0, "recency": 0,
                "multi_source": 0, "regulatory": 0}

    tier_sum     = sum(_TIER_WEIGHT.get(a.get("tier") or "unclear", 0.3) for a in actions)
    tier_norm    = min(1.0, tier_sum / max(1, len(actions)))   # normalize to 0..1

    engagement_raw = sum(
        len(_parse_json(a.get("opposition_groups"))) +
        (1 if a.get("petition_url") else 0) +
        len(_parse_json(a.get("sources")))
        for a in actions
    )
    engagement_norm = min(1.0, engagement_raw / max(1, len(actions) * 4))

    recency_sum  = sum(_recency_weight(a.get("date")) for a in actions)
    recency_norm = min(1.0, recency_sum / max(1, len(actions) * 1.5))

    multi_source_count = sum(1 for a in actions if len(_parse_json(a.get("sources"))) > 1)
    multi_norm   = multi_source_count / max(1, len(actions))

    regulatory   = 1.0 if any(a.get("status") == "enacted" for a in actions) else 0.0

    score = (40 * tier_norm
           + 25 * engagement_norm
           + 20 * recency_norm
           + 10 * multi_norm
           +  5 * regulatory)

    return {
        "score":            round(score, 1),
        "tier":             round(40 * tier_norm,        1),
        "engagement":       round(25 * engagement_norm,  1),
        "recency":          round(20 * recency_norm,     1),
        "multi_source":     round(10 * multi_norm,       1),
        "regulatory":       round( 5 * regulatory,       1),
    }


# ---- Aggregations -----------------------------------------------------

def _summarize(actions: list[dict]) -> dict:
    """Reusable summary block: counts by tier/outcome/scope/issue + top
    citations + active companies + opposition groups."""
    if not actions:
        return {
            "count": 0, "tier_counts": {}, "outcome_counts": {},
            "scope_counts": {}, "issue_top": {}, "top_citations": [],
            "companies": [], "opposition_groups": [], "earliest": None, "latest": None,
        }

    tier_counts    = {}
    outcome_counts = {}
    scope_counts   = {}
    issue_counts   = {}
    companies      = {}
    opp_groups     = {}
    dates          = []

    for a in actions:
        tier_counts[a.get("tier")]               = tier_counts.get(a.get("tier"), 0) + 1
        outcome_counts[a.get("community_outcome")] = outcome_counts.get(a.get("community_outcome"), 0) + 1
        scope_counts[a.get("scope")]             = scope_counts.get(a.get("scope"), 0) + 1
        for tag in _parse_json(a.get("issue_category")):
            issue_counts[tag] = issue_counts.get(tag, 0) + 1
        if a.get("company"):
            companies[a["company"]] = companies.get(a["company"], 0) + 1
        for g in _parse_json(a.get("opposition_groups")):
            opp_groups[g] = opp_groups.get(g, 0) + 1
        if a.get("date"):
            dates.append(a["date"])

    # Top 10 citations by recency × richness (sources count)
    cites = sorted(
        [a for a in actions if (a.get("summary") and a.get("date"))],
        key=lambda a: (a["date"] or "", len(_parse_json(a.get("sources")))),
        reverse=True,
    )[:10]

    return {
        "count":            len(actions),
        "tier_counts":      tier_counts,
        "outcome_counts":   outcome_counts,
        "scope_counts":     scope_counts,
        "issue_top":        dict(sorted(issue_counts.items(), key=lambda kv: -kv[1])[:8]),
        "companies":        sorted(companies.items(),  key=lambda kv: -kv[1])[:8],
        "opposition_groups":sorted(opp_groups.items(), key=lambda kv: -kv[1])[:10],
        "earliest":         min(dates) if dates else None,
        "latest":           max(dates) if dates else None,
        "top_citations": [
            {
                "id": a["id"], "date": a["date"], "jurisdiction": a.get("jurisdiction"),
                "title": (a.get("summary") or "")[:140],
                "tier": a.get("tier"), "outcome": a.get("community_outcome"),
                "url": (_parse_json(a.get("sources")) or [None])[0],
            }
            for a in cites
        ],
    }


# ---- Builders ---------------------------------------------------------

def build_state_dossier(state: str, actions: list[dict]) -> dict:
    summary = _summarize(actions)
    return {
        "schema":        "dcw.dossier.state.v1",
        "state":         state,
        "generated_at":  _utcnow(),
        "risk_score":    _risk_score(actions),
        **summary,
    }


def build_county_dossier(state: str, county_fips: str, county_name: str,
                          actions: list[dict]) -> dict:
    summary = _summarize(actions)
    return {
        "schema":        "dcw.dossier.county.v1",
        "state":         state,
        "county_fips":   county_fips,
        "county_name":   county_name,
        "generated_at":  _utcnow(),
        "risk_score":    _risk_score(actions),
        **summary,
    }


def write_csv_export(actions: list[dict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cols = ["id", "origin", "state", "county", "jurisdiction", "scope",
            "action_type", "authority_level", "date", "status",
            "community_outcome", "issue_category", "tier", "tier_reason",
            "company", "hyperscaler", "summary", "url"]
    with out_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for a in actions:
            row = {c: a.get(c) for c in cols}
            for c in ("action_type", "issue_category"):
                if isinstance(row[c], list):
                    row[c] = "|".join(row[c])
            srcs = _parse_json(a.get("sources"))
            row["url"] = srcs[0] if srcs else ""
            w.writerow(row)


# ---- Main -------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="Build per-state + per-county dossiers + static API")
    ap.add_argument("--no-csv", action="store_true", help="skip CSV export")
    args = ap.parse_args()

    if not DB_PATH.exists():
        log.error("DB not found at %s", DB_PATH)
        return 1

    conn = sqlite3.connect(DB_PATH)
    migrate(conn)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("SELECT * FROM actions").fetchall()]
    conn.close()

    log.info("loaded %d actions", len(rows))

    # Resolve county for each action that doesn't have one yet
    for r in rows:
        if not r.get("county"):
            blob = " ".join(filter(None, [r.get("city"), r.get("jurisdiction"), r.get("summary")]))
            fips, name = resolve_county(r.get("state"), blob)
            if fips:
                r["county"] = name
                r["county_fips"] = fips

    # Bucket
    by_state: dict[str, list[dict]] = {}
    by_county: dict[tuple[str, str], list[dict]] = {}     # (fips, name) → actions
    for r in rows:
        st = r.get("state")
        if st and st != "US":
            by_state.setdefault(st, []).append(r)
        if r.get("county_fips"):
            key = (r["county_fips"], r["county"])
            by_county.setdefault(key, []).append(r)

    # ---- Write per-state dossiers + state index --------------------------
    DOSSIER_DIR.mkdir(parents=True, exist_ok=True)
    state_index = []
    for st, actions in sorted(by_state.items()):
        d = build_state_dossier(st, actions)
        (DOSSIER_DIR / f"state-{st}.json").write_text(json.dumps(d, indent=2, ensure_ascii=False))
        state_index.append({
            "state":      st,
            "count":      d["count"],
            "risk_score": d["risk_score"]["score"],
            "latest":     d["latest"],
            "url":        f"data/dossiers/state-{st}.json",
        })

    # ---- Write per-county dossiers + county index -----------------------
    county_index = []
    for (fips, name), actions in sorted(by_county.items()):
        st = actions[0].get("state")
        d = build_county_dossier(st, fips, name, actions)
        (DOSSIER_DIR / f"county-{fips}.json").write_text(json.dumps(d, indent=2, ensure_ascii=False))
        county_index.append({
            "county_fips": fips, "county_name": name, "state": st,
            "count": d["count"], "risk_score": d["risk_score"]["score"],
            "latest": d["latest"],
            "url": f"data/dossiers/county-{fips}.json",
        })

    (DOSSIER_DIR / "index.json").write_text(json.dumps({
        "schema":       "dcw.dossier.index.v1",
        "generated_at": _utcnow(),
        "states":       state_index,
        "counties":     county_index,
    }, indent=2))
    log.info("dossiers: %d states + %d counties", len(state_index), len(county_index))

    # ---- Static API surface (data/api/v1/) ------------------------------
    API_DIR.mkdir(parents=True, exist_ok=True)
    (API_DIR / "states.json").write_text(json.dumps({
        "schema": "dcw.api.states.v1", "generated_at": _utcnow(),
        "states": state_index,
    }, indent=2))
    (API_DIR / "counties.json").write_text(json.dumps({
        "schema": "dcw.api.counties.v1", "generated_at": _utcnow(),
        "counties": county_index,
    }, indent=2))

    # Per-state API endpoints (mirror dossiers — same shape, different URL)
    (API_DIR / "states").mkdir(exist_ok=True)
    for st, _ in by_state.items():
        src = DOSSIER_DIR / f"state-{st}.json"
        (API_DIR / "states" / f"{st}.json").write_text(src.read_text())

    (API_DIR / "counties").mkdir(exist_ok=True)
    for (fips, _), _ in by_county.items():
        src = DOSSIER_DIR / f"county-{fips}.json"
        (API_DIR / "counties" / f"{fips}.json").write_text(src.read_text())

    # By-issue + by-outcome rollups (sliced action lists)
    (API_DIR / "actions").mkdir(exist_ok=True)
    (API_DIR / "actions" / "issue").mkdir(exist_ok=True)
    (API_DIR / "actions" / "outcome").mkdir(exist_ok=True)

    by_issue: dict[str, list[dict]] = {}
    for r in rows:
        for tag in _parse_json(r.get("issue_category")):
            by_issue.setdefault(tag, []).append(r)
    for tag, items in by_issue.items():
        (API_DIR / "actions" / "issue" / f"{tag}.json").write_text(json.dumps({
            "schema": "dcw.api.actions.v1", "generated_at": _utcnow(),
            "filter": {"issue_category": tag}, "count": len(items),
            "items": [{k: v for k, v in a.items() if k != "first_seen"} for a in items],
        }, indent=2, ensure_ascii=False))

    by_outcome: dict[str, list[dict]] = {}
    for r in rows:
        oc = r.get("community_outcome") or "pending"
        by_outcome.setdefault(oc, []).append(r)
    for oc, items in by_outcome.items():
        (API_DIR / "actions" / "outcome" / f"{oc}.json").write_text(json.dumps({
            "schema": "dcw.api.actions.v1", "generated_at": _utcnow(),
            "filter": {"community_outcome": oc}, "count": len(items),
            "items": [{k: v for k, v in a.items() if k != "first_seen"} for a in items],
        }, indent=2, ensure_ascii=False))

    log.info("API: %d issue endpoints, %d outcome endpoints",
             len(by_issue), len(by_outcome))

    # ---- CSV export (Pro-tier) ------------------------------------------
    if not args.no_csv:
        write_csv_export(rows, API_DIR / "exports" / "all_actions.csv")
        log.info("wrote CSV export: %s", API_DIR / "exports" / "all_actions.csv")

    log.info("✓ done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
