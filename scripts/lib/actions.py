"""actions table — classifier + upsert.

This is the core of our 'dense' product layer. We mirror the taxonomy of
datacentertracker.org (CC BY 4.0) so our schemas line up if anyone ever
wants to compare datasets, but we DO NOT import their data — we build our
own pipeline against the same standard.

Tag vocabularies (frozen — UI relies on these exact strings):

ISSUE_CATEGORIES — 16 tags
ACTION_TYPES     — 15 tags
AUTHORITY_LEVELS — 27 tags
COMMUNITY_OUTCOME— 4 tags  (community POV)
DEVELOPER_TIER   — 4 tags  (developer POV — our own addition)

The classifier is rule-based v1; we plan to layer Haiku on top later for
the ambiguous 20% of records.
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone

# ---------- Issue categories (16) — verbatim from datacentertracker.org ----------
ISSUE_LABELS: dict[str, str] = {
    "zoning":              "Zoning / Land Use",
    "water":               "Water",
    "environmental":       "Environmental",
    "community_impact":    "Community Impact",
    "grid_energy":         "Grid / Energy",
    "transparency":        "Transparency",
    "ratepayer":           "Ratepayer",
    "noise":               "Noise",
    "tax_incentive":       "Tax / Incentive",
    "farmland":            "Farmland",
    "traffic":             "Traffic",
    "design_standards":    "Design Standards",
    "contract_guarantees": "Contract Guarantees",
    "anti_ai":             "Anti-AI",
    "air_quality":         "Air Quality",
    "property_values":     "Property Values",
}

ISSUE_TOOLTIPS: dict[str, str] = {
    "zoning":              "Land use and zoning concerns — whether the site should be industrial, residential, mixed-use, or agricultural",
    "water":               "Water consumption — cooling demand, aquifer depletion, impact on local supply, wetlands, or waterways",
    "environmental":       "Pollution, emissions, habitat destruction, wildlife impact, or ecosystem damage",
    "community_impact":    "Property values, rural character, displacement, noise, traffic, or quality of life",
    "grid_energy":         "Grid strain, transmission infrastructure, reliability, or new generation needs",
    "transparency":        "NDAs, secret negotiations, hidden terms, communities kept in the dark",
    "ratepayer":           "Worry that data center costs get passed to residential electric customers",
    "noise":               "Cooling-fan hum, backup generators, construction disturbance",
    "tax_incentive":       "Public subsidies, tax abatements, giveaways to corporations",
    "farmland":            "Loss of working farms, prime agricultural soil, or rural open space",
    "traffic":             "Construction trucks, road damage, permanent local traffic increases",
    "design_standards":    "Height limits, setbacks, screening, sound barriers, architectural rules",
    "contract_guarantees": "Financial assurances, early-termination fees, load ramp terms, decommissioning bonds",
    "anti_ai":             "Explicit opposition to AI as a technology — jobs, energy footprint, or industry-wide opposition",
    "air_quality":         "Emissions from on-site gas turbines, diesel backup generators, construction; respiratory effects",
    "property_values":     "Declining home prices, sale-volume drops, rental-demand effects",
}

ISSUE_KEYWORDS: dict[str, list[re.Pattern]] = {
    "zoning":              [re.compile(rf"\b{p}\b", re.I) for p in [
        "zoning", "rezoning", "land use", "land-use", "by-right", "special exception",
        "industrial use", "agricultural zone", "land swap",
    ]],
    "water":               [re.compile(rf"\b{p}\b", re.I) for p in [
        "water use", "water consumption", "aquifer", "groundwater", "wells",
        "cooling water", "drinking water", "wetland",
    ]],
    "environmental":       [re.compile(rf"\b{p}\b", re.I) for p in [
        "environmental", "wildlife", "ecosystem", "habitat", "pollution",
        "endangered species", "carbon emissions", "epa",
    ]],
    "community_impact":    [re.compile(rf"\b{p}\b", re.I) for p in [
        "community", "residents", "neighborhood", "rural character", "quality of life",
        "displacement",
    ]],
    "grid_energy":         [re.compile(rf"\b{p}\b", re.I) for p in [
        "grid", "transmission", "load growth", "power demand", "megawatt",
        "interconnection queue", "peak load", "reliability",
    ]],
    "transparency":        [re.compile(rf"\b{p}\b", re.I) for p in [
        "nda", "non-disclosure", "secret", "closed[- ]?door", "confidential",
        "transparency",
    ]],
    "ratepayer":           [re.compile(rf"\b{p}\b", re.I) for p in [
        "ratepayer", "rate-payer", "rate payer", "rate increase", "rate hike",
        "cost shift", "electric bill", "utility bill", "rate allocation",
    ]],
    "noise":               [re.compile(rf"\b{p}\b", re.I) for p in [
        "noise", "decibel", "humming", "fan noise", "generator noise",
        "sound ordinance",
    ]],
    "tax_incentive":       [re.compile(rf"\b{p}\b", re.I) for p in [
        "tax abatement", "tax exemption", "tax credit", "tax rebate", "TIF",
        "tax incentive", "tax break", "tax giveaway", "subsid", "85%? tax",
    ]],
    "farmland":            [re.compile(rf"\b{p}\b", re.I) for p in [
        "farmland", "agricultural", "farms?", "rural", "prime soil",
    ]],
    "traffic":             [re.compile(rf"\b{p}\b", re.I) for p in [
        "traffic", "trucks?", "road damage", "congestion",
    ]],
    "design_standards":    [re.compile(rf"\b{p}\b", re.I) for p in [
        "setback", "height limit", "screening", "buffer zone", "façade",
        "facade", "architectural",
    ]],
    "contract_guarantees": [re.compile(rf"\b{p}\b", re.I) for p in [
        "decommission", "performance bond", "load ramp", "early termination",
        "minimum bill",
    ]],
    "anti_ai":             [re.compile(rf"\b{p}\b", re.I) for p in [
        "AI energy", "AI footprint", "anti-AI", "stop AI", "AI moratorium",
        "no to AI",
    ]],
    "air_quality":         [re.compile(rf"\b{p}\b", re.I) for p in [
        "air quality", "emissions", "diesel", "gas turbine", "backup generator",
        "respiratory",
    ]],
    "property_values":     [re.compile(rf"\b{p}\b", re.I) for p in [
        "property value", "home price", "house price", "property prices",
    ]],
}


# ---------- Action types (15) — verbatim ----------
ACTION_TYPES = [
    "zoning_restriction", "legislation", "moratorium", "public_comment",
    "lawsuit", "project_withdrawal", "utility_regulation", "ordinance",
    "study_or_report", "regulatory_action", "executive_order",
    "other_opposition", "infrastructure_opposition", "permit_denial",
    "executive_action",
]

ACTION_TYPE_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bmoratorium\b", re.I),                        "moratorium"),
    (re.compile(r"\b(rezoning|zoning amendment|special exception)\b", re.I), "zoning_restriction"),
    (re.compile(r"\b(bill|legislation|HB|SB|LD|AB|HR|SR)\s*\d", re.I),     "legislation"),
    (re.compile(r"\b(lawsuit|sued|court of appeals|injunction|ruling)\b", re.I), "lawsuit"),
    (re.compile(r"\b(withdrew|withdrawn|cancelled|canceled|pulled out)\b", re.I), "project_withdrawal"),
    (re.compile(r"\b(public hearing|public comment|town hall)\b", re.I), "public_comment"),
    (re.compile(r"\b(ordinance)\b", re.I),                        "ordinance"),
    (re.compile(r"\b(study|report|commission)\b", re.I),          "study_or_report"),
    (re.compile(r"\b(executive order|governor's order|signed by the governor)\b", re.I), "executive_order"),
    (re.compile(r"\bpermit (denied|denial|rejected)\b", re.I),    "permit_denial"),
    (re.compile(r"\bPUC|public utility commission|utility regulator\b", re.I), "utility_regulation"),
    (re.compile(r"\b(transmission|substation) opposition\b", re.I), "infrastructure_opposition"),
]


# ---------- Authority levels (27) — verbatim ----------
AUTHORITY_LEVELS = [
    "county_commission", "city_council", "state_legislature", "township_board",
    "court", "planning_commission", "utility_commission", "governor",
    "federal_legislature", "developer", "voters", "federal_agency",
    "village_board", "advocacy_org", "federal_executive", "tribal_government",
    "congress", "grassroots", "planning_board", "advocacy",
    "township_supervisors", "state_commission", "federal_legislation",
    "local_ordinance", "school_board", "borough_council", "town_meeting",
]


# ---------- Community outcome (community POV) ----------
COMMUNITY_OUTCOMES = ["pending", "win", "loss", "mixed"]


# ---------- Developer tier (developer POV — our own) ----------
DEVELOPER_TIERS = ["restrictive", "protective", "supportive", "unclear"]


# ---------- Classifier helpers ----------

def classify_issues(title: str, summary: str | None = None) -> list[str]:
    """Return up to 6 matching issue tags ordered by # keyword hits."""
    blob = f"{title or ''} {summary or ''}"
    scores: dict[str, int] = {}
    for tag, patterns in ISSUE_KEYWORDS.items():
        n = sum(1 for p in patterns if p.search(blob))
        if n: scores[tag] = n
    return sorted(scores, key=lambda t: (-scores[t], t))[:6]


def classify_action_type(title: str, summary: str | None = None) -> list[str]:
    """Return action_type list. Multi-match allowed (e.g. moratorium + legislation)."""
    blob = f"{title or ''} {summary or ''}"
    out: list[str] = []
    for rx, label in ACTION_TYPE_RULES:
        if rx.search(blob) and label not in out:
            out.append(label)
    return out or ["other_opposition"]


def derive_community_outcome(category: str | None, status: str | None) -> str:
    """Map our existing event.category + bills.status → community POV.

    Wins (for the community) = anything that stops/slows DC builds.
    Losses = builds advance despite opposition.
    """
    cat = (category or "").lower()
    st  = (status   or "").lower()

    if cat == "banned":          return "win"        # moratorium passed
    if cat == "cancelled":       return "win"        # project withdrawn / blocked
    if cat == "protested":       return "pending"    # active fight, no resolution yet
    if cat == "announced":       return "loss"       # build is moving forward
    if st in ("enacted", "passed-both", "passed-upper", "passed-lower"):
        return "win"
    if st == "in-committee":     return "pending"
    if st == "introduced":       return "pending"
    if st == "dead":             return "loss"
    return "pending"


def derive_tier(category: str | None, summary: str | None = None) -> tuple[str, str]:
    """Developer POV: restrictive (bad-for-builds), protective (guardrails),
    supportive (helpful), unclear."""
    blob = (summary or "").lower()
    if category in ("banned", "cancelled"):
        return ("restrictive", category or "moratorium / cancellation")
    if category == "protested":
        if any(t in blob for t in ("water cap", "noise ordinance", "environmental review",
                                    "design standard", "setback")):
            return ("protective", "guardrails imposed")
        return ("restrictive", "active opposition")
    if category == "announced":
        if any(t in blob for t in ("tax abatement", "tax exemption", "fast-track",
                                    "incentive", "streamlined")):
            return ("supportive", "developer-friendly framework")
        return ("supportive", "project advancing")
    return ("unclear", "no clear signal")


# ---------- Authority-level inference (best-effort from blob) ----------

_AUTHORITY_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bcounty (commission|board|supervisors)\b", re.I),  "county_commission"),
    (re.compile(r"\bcity council\b", re.I),                           "city_council"),
    (re.compile(r"\b(state )?legislature\b|\b(senate|house) (passed|approved)\b", re.I), "state_legislature"),
    (re.compile(r"\btownship board\b", re.I),                         "township_board"),
    (re.compile(r"\b(court of appeals|district court|judge|ruling)\b", re.I), "court"),
    (re.compile(r"\bplanning commission\b", re.I),                    "planning_commission"),
    (re.compile(r"\b(public utility commission|PUC|utility commission)\b", re.I), "utility_commission"),
    (re.compile(r"\bgovernor\b", re.I),                               "governor"),
    (re.compile(r"\b(congress|federal legislature|senate bill|house bill)\b", re.I), "federal_legislature"),
    (re.compile(r"\bvoters?\b", re.I),                                "voters"),
    (re.compile(r"\b(EPA|FERC|federal agency)\b", re.I),              "federal_agency"),
    (re.compile(r"\bvillage board\b", re.I),                          "village_board"),
    (re.compile(r"\btribal\b", re.I),                                 "tribal_government"),
    (re.compile(r"\bschool board\b", re.I),                           "school_board"),
]


def infer_authority(title: str, summary: str | None = None) -> str | None:
    blob = f"{title or ''} {summary or ''}"
    for rx, label in _AUTHORITY_RULES:
        if rx.search(blob): return label
    return None


# ---------- Scope inference ----------

def infer_scope(state: str | None, authority: str | None, jurisdiction: str | None = None) -> str:
    """3-way: local | statewide | federal."""
    if authority in ("federal_legislature", "federal_agency", "federal_executive", "congress"):
        return "federal"
    if (jurisdiction or "").lower().startswith("federal"):
        return "federal"
    if authority in ("state_legislature", "governor", "state_commission"):
        return "statewide"
    if (jurisdiction or "").lower().endswith("(statewide)"):
        return "statewide"
    return "local"


# ---------- Upsert ----------

def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _json_or_none(v) -> str | None:
    if v in (None, "", []): return None
    return v if isinstance(v, str) else json.dumps(v, separators=(",", ":"), ensure_ascii=False)


_INSERT_COLS = [
    "id", "origin", "state", "county", "jurisdiction", "lat", "lng",
    "scope", "action_type", "authority_level", "date", "status",
    "community_outcome", "issue_category",
    "company", "hyperscaler", "project_name", "investment_million_usd",
    "megawatts", "acreage", "building_sq_ft", "water_usage_gallons_per_day",
    "jobs_promised",
    "opposition_groups", "opposition_website", "opposition_facebook",
    "opposition_instagram", "opposition_twitter", "petition_url",
    "petition_signatures",
    "summary", "sources", "data_source", "last_updated", "first_seen",
    "bill_number", "bill_session",
    "tier", "tier_reason",
]


def upsert(conn: sqlite3.Connection, action: dict) -> str:
    """Insert or update an action row. Returns 'inserted' | 'updated' | 'noop'."""
    row = {col: action.get(col) for col in _INSERT_COLS}
    row["last_seen"] = row.get("last_updated") or _utcnow()
    if not row.get("first_seen"):
        row["first_seen"] = _utcnow()

    # JSON-encode list fields
    for col in ("action_type", "issue_category", "opposition_groups", "sources"):
        row[col] = _json_or_none(row[col])

    existing = conn.execute(
        "SELECT status, community_outcome, tier FROM actions WHERE id = ?",
        (row["id"],),
    ).fetchone()

    if existing is None:
        cols = ",".join(_INSERT_COLS)
        ph   = ",".join("?" * len(_INSERT_COLS))
        conn.execute(
            f"INSERT INTO actions ({cols}) VALUES ({ph})",
            [row[c] for c in _INSERT_COLS],
        )
        return "inserted"

    if (existing[0] == row["status"]
        and existing[1] == row["community_outcome"]
        and existing[2] == row["tier"]):
        return "noop"

    set_clause = ", ".join(f"{c} = ?" for c in _INSERT_COLS if c != "id")
    values     = [row[c] for c in _INSERT_COLS if c != "id"]
    conn.execute(f"UPDATE actions SET {set_clause} WHERE id = ?", [*values, row["id"]])
    return "updated"


# ---------- Per-state aggregation for the map ----------

_TIER_PRIORITY = {"restrictive": 1, "protective": 2, "supportive": 3, "unclear": 4}
_OUTCOME_PRIORITY = {"loss": 1, "pending": 2, "mixed": 3, "win": 4}


def aggregate_by_state(conn: sqlite3.Connection) -> dict[str, dict]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT * FROM actions
           ORDER BY date DESC"""
    ).fetchall()

    out: dict[str, dict] = {}
    for r in rows:
        st = r["state"]
        if not st:
            continue
        ent = out.setdefault(st, {
            "state":           st,
            "count":           0,
            "outcome_counts":  {"pending": 0, "win": 0, "loss": 0, "mixed": 0},
            "tier_counts":     {"restrictive": 0, "protective": 0, "supportive": 0, "unclear": 0},
            "scope_counts":    {"local": 0, "statewide": 0, "federal": 0},
            "issue_top":       {},
            "latest_date":     "",
            "map_color_tier":  None,
            "map_color_outcome": None,
        })
        ent["count"] += 1
        if r["community_outcome"] in ent["outcome_counts"]:
            ent["outcome_counts"][r["community_outcome"]] += 1
        if r["tier"] in ent["tier_counts"]:
            ent["tier_counts"][r["tier"]] += 1
        if r["scope"] in ent["scope_counts"]:
            ent["scope_counts"][r["scope"]] += 1
        if r["issue_category"]:
            try:
                for tag in json.loads(r["issue_category"]):
                    ent["issue_top"][tag] = ent["issue_top"].get(tag, 0) + 1
            except json.JSONDecodeError:
                pass
        if (r["date"] or "") > ent["latest_date"]:
            ent["latest_date"] = r["date"] or ""

        # First (= highest-priority since we sorted by date DESC) tier wins
        if ent["map_color_tier"] is None and r["tier"]:
            ent["map_color_tier"] = r["tier"]
        if ent["map_color_outcome"] is None and r["community_outcome"]:
            ent["map_color_outcome"] = r["community_outcome"]

    # Pick the worst-case (most-restrictive / most-loss) tier for map color
    # rather than just "first by date" — that's misleading on the map
    for st, ent in out.items():
        worst_tier = None
        for t in ("restrictive", "protective", "supportive", "unclear"):
            if ent["tier_counts"].get(t, 0) > 0:
                worst_tier = t
                break
        ent["map_color_tier"] = worst_tier or ent["map_color_tier"]

        worst_outcome = None
        for o in ("loss", "pending", "mixed", "win"):
            if ent["outcome_counts"].get(o, 0) > 0:
                worst_outcome = o
                break
        ent["map_color_outcome"] = worst_outcome or ent["map_color_outcome"]

        # Top 3 issues for tooltip
        ent["issue_top"] = dict(sorted(ent["issue_top"].items(),
                                        key=lambda kv: (-kv[1], kv[0]))[:3])

    return out
