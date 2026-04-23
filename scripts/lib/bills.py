"""Bill classification + DB upsert helpers.

Tier taxonomy (developer POV):
    restrictive  — makes DC development harder or impossible
                   (moratorium, ban, pause, mandatory study)
    protective   — adds community-side guardrails without a ban
                   (water caps, noise ordinances, approval requirements)
    supportive   — actively helps DC development
                   (tax abatements, fast-track permitting)
    unclear      — DC-adjacent but intent not obvious from title + summary

Rule-based v1 — fast, free, good enough for the first dossier. Haiku upgrade
later once we have real volume to justify the cost.
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone

# Each tuple is (compiled regex, short reason). Order matters — first match wins.
# Reasons are short human-readable fragments for the dossier tooltip.
_RESTRICTIVE_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bmoratorium\b",             re.I), "moratorium"),
    (re.compile(r"\b(ban|prohibit|preclude|freeze)\b.*\b(data ?centers?|hyperscale)\b", re.I), "ban / prohibit"),
    (re.compile(r"\b(pause|halt)\b.*\b(construction|approvals?|permits?)\b",            re.I), "construction pause"),
    (re.compile(r"\bstudy commission\b",       re.I), "study commission"),
    (re.compile(r"\bsuspend\b.*\bapprovals?\b", re.I), "suspend approvals"),
    (re.compile(r"\blimit\b.*\b(MW|megawatt|load)\b", re.I), "MW limit / load cap"),
    (re.compile(r"\bsurcharge\b.*\b(electricity|energy|data ?centers?)\b", re.I), "DC electricity surcharge"),
    (re.compile(r"\bfee\b.*\b(data ?centers?|hyperscale)\b", re.I), "fee on data centers"),
    (re.compile(r"\bimpact (assessment|review)\b.*\bdata ?centers?\b", re.I), "impact assessment required"),
]

_PROTECTIVE_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bwater use\b",              re.I), "water-use restrictions"),
    (re.compile(r"\bnoise\b.*\b(ordinance|cap|limit)\b", re.I), "noise ordinance"),
    (re.compile(r"\bcommunity benefit\b",      re.I), "community benefit agreement"),
    (re.compile(r"\benvironmental (review|impact)\b",   re.I), "environmental review"),
    (re.compile(r"\bpublic hearing\b.*required", re.I), "public-hearing requirement"),
    (re.compile(r"\b(setback|buffer) (requirement|zone)\b", re.I), "setback / buffer"),
    (re.compile(r"\blocal (approval|veto|siting)\b",     re.I), "local-approval requirement"),
    (re.compile(r"\bzoning\b.*\b(restrict|require|amend)\b", re.I), "zoning change"),
    (re.compile(r"\b(rate|cost) (allocation|shift)\b",   re.I), "rate / cost allocation"),
    (re.compile(r"\bgrid impact\b",            re.I), "grid-impact review"),
]

_SUPPORTIVE_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(sales|use|property) tax (exemption|abatement|rebate|credit)\b", re.I), "tax abatement"),
    (re.compile(r"\btax increment financing\b", re.I), "TIF"),
    (re.compile(r"\b(fast[- ]track|expedited) (permit|approval|siting)\b", re.I), "fast-track permitting"),
    (re.compile(r"\bstreamlin(e|ed) (permit|approval|process)\b", re.I), "streamlined permitting"),
    (re.compile(r"\beconomic development incentive\b",           re.I), "economic-development incentive"),
    (re.compile(r"\bincentiv(e|es)\b.*\b(data ?centers?|hyperscale)\b", re.I), "incentive for data centers"),
    (re.compile(r"\bqualif(y|ied|ying) data ?centers?\b",        re.I), "qualified-data-center program"),
    (re.compile(r"\bopportunity zone\b.*\b(data center|hyperscale)\b", re.I), "opportunity zone"),
    (re.compile(r"\bworkforce training\b.*\bdata center\b",       re.I), "workforce training"),
]

# DC-relevance gate at ingest time. OpenStates full-text search occasionally
# returns bills where "data center" appears only in sponsor bios, not in the
# bill itself. Require title or summary to actually mention DCs.
_DC_TERMS = ("data center", "datacenter", "data centre", "hyperscale",
             "large-load", "large load", "server farm")


def is_dc_relevant(title: str, summary: str | None = None) -> bool:
    blob = f"{title or ''} {summary or ''}".lower()
    return any(t in blob for t in _DC_TERMS)


def classify(title: str, summary: str | None = None) -> tuple[str, str]:
    """Returns (tier, reason). Prefers the most explicit signal.

    Restrictive always wins over protective, protective over supportive,
    because for a developer the worst-case tier is the load-bearing one.
    """
    blob = f"{title or ''}\n{summary or ''}".strip()
    if not blob:
        return ("unclear", "empty title + summary")

    for rx, reason in _RESTRICTIVE_RULES:
        if rx.search(blob):
            return ("restrictive", reason)
    for rx, reason in _PROTECTIVE_RULES:
        if rx.search(blob):
            return ("protective", reason)
    for rx, reason in _SUPPORTIVE_RULES:
        if rx.search(blob):
            return ("supportive", reason)
    return ("unclear", "no keyword match")


def extract_keywords(title: str, summary: str | None = None) -> list[str]:
    """Small set of dimensional tags for the dossier."""
    blob = f"{title or ''} {summary or ''}".lower()
    tags: list[str] = []
    table = {
        "moratorium":         r"\bmoratorium\b",
        "tax-incentive":      r"\btax (exemption|abatement|rebate|credit)\b",
        "water":              r"\bwater\b",
        "noise":              r"\bnoise\b",
        "zoning":             r"\bzoning\b",
        "environmental":      r"\benvironmental\b",
        "grid":               r"\bgrid\b|\btransmission\b|\bload\b",
        "local-control":      r"\blocal (approval|veto|siting|control)\b",
        "study":              r"\bstudy\b",
        "rate-allocation":    r"\brate (allocation|shift|structure)\b",
        "large-load":         r"\blarge[- ]load\b|\bhyperscale\b",
    }
    for tag, pattern in table.items():
        if re.search(pattern, blob):
            tags.append(tag)
    return tags


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


_INSERT_COLS = [
    "id", "state", "bill_number", "session", "title", "summary",
    "status", "status_date", "introduced_date", "last_action_date",
    "last_action_description", "sponsors", "subjects", "tier", "tier_reason",
    "keywords", "url_openstates", "url_source", "last_seen",
]


def _json_or_none(v) -> str | None:
    if v in (None, ""):
        return None
    return v if isinstance(v, str) else json.dumps(v, separators=(",", ":"), ensure_ascii=False)


def upsert(conn: sqlite3.Connection, bill: dict) -> str:
    """Insert or update a single bill row. Classification is applied here so
    callers can just hand us raw OpenStates-normalized dicts. Returns
    'inserted' | 'updated' | 'noop'."""
    tier, reason = classify(bill.get("title") or "", bill.get("summary"))
    kw = extract_keywords(bill.get("title") or "", bill.get("summary"))

    row = {
        "id":                       bill["id"],
        "state":                    bill["state"],
        "bill_number":              bill.get("bill_number"),
        "session":                  bill.get("session"),
        "title":                    bill.get("title") or "",
        "summary":                  bill.get("summary"),
        "status":                   bill.get("status") or "introduced",
        "status_date":              bill.get("status_date"),
        "introduced_date":          bill.get("introduced_date"),
        "last_action_date":         bill.get("last_action_date"),
        "last_action_description":  bill.get("last_action_description"),
        "sponsors":                 _json_or_none(bill.get("sponsors")),
        "subjects":                 _json_or_none(bill.get("subjects")),
        "tier":                     tier,
        "tier_reason":              reason,
        "keywords":                 _json_or_none(kw),
        "url_openstates":           bill.get("url_openstates"),
        "url_source":               bill.get("url_source"),
        "last_seen":                _utcnow(),
    }

    existing = conn.execute("SELECT status, tier FROM bills WHERE id = ?", (row["id"],)).fetchone()
    if existing is None:
        placeholders = ",".join("?" * len(_INSERT_COLS))
        cols         = ",".join(_INSERT_COLS)
        conn.execute(
            f"INSERT INTO bills ({cols}) VALUES ({placeholders})",
            [row[c] for c in _INSERT_COLS],
        )
        return "inserted"

    # Skip the write if nothing meaningful changed — keeps commit-if-changed
    # from rewriting bills.json on every cron run.
    if existing[0] == row["status"] and existing[1] == row["tier"]:
        conn.execute(
            "UPDATE bills SET last_seen = ? WHERE id = ?",
            (row["last_seen"], row["id"]),
        )
        return "noop"

    set_clause = ", ".join(f"{c} = ?" for c in _INSERT_COLS if c != "id")
    values = [row[c] for c in _INSERT_COLS if c != "id"]
    conn.execute(f"UPDATE bills SET {set_clause} WHERE id = ?", [*values, row["id"]])
    return "updated"


def aggregate_by_state(conn: sqlite3.Connection) -> dict[str, dict]:
    """Build per-state summary used by the frontend map layer. For each state:
        - highest-priority active bill tier
        - counts by tier
        - up-to-3 featured bills (enacted > passed > in-committee)
    """
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT id, state, bill_number, title, status, status_date, tier,
                  tier_reason, url_openstates, url_source, keywords
           FROM bills
           WHERE tier IN ('restrictive','protective','supportive')
             AND status != 'dead'
           ORDER BY
             CASE tier
               WHEN 'restrictive' THEN 1
               WHEN 'protective'  THEN 2
               WHEN 'supportive'  THEN 3
               ELSE 4 END,
             CASE status
               WHEN 'enacted'          THEN 1
               WHEN 'passed-both'      THEN 2
               WHEN 'passed-upper'     THEN 3
               WHEN 'passed-lower'     THEN 3
               WHEN 'passed-committee' THEN 4
               WHEN 'in-committee'     THEN 5
               WHEN 'introduced'       THEN 6
               ELSE 7 END,
             status_date DESC"""
    ).fetchall()

    out: dict[str, dict] = {}
    for r in rows:
        st = r["state"]
        ent = out.setdefault(st, {
            "state": st,
            "tier_counts": {"restrictive": 0, "protective": 0, "supportive": 0, "unclear": 0},
            "status_counts": {},
            "featured": [],
            "map_color_tier": None,   # priority-ordered hint for map rendering
            "map_color_status": None,
        })
        if r["tier"] in ent["tier_counts"]:
            ent["tier_counts"][r["tier"]] += 1
        ent["status_counts"][r["status"]] = ent["status_counts"].get(r["status"], 0) + 1

        if len(ent["featured"]) < 3:
            ent["featured"].append({
                "id":          r["id"],
                "bill_number": r["bill_number"],
                "title":       r["title"],
                "status":      r["status"],
                "status_date": r["status_date"],
                "tier":        r["tier"],
                "tier_reason": r["tier_reason"],
                "url":         r["url_source"] or r["url_openstates"],
            })

        # First row for a state is already the highest-priority one thanks to the sort
        if ent["map_color_tier"] is None:
            ent["map_color_tier"]   = r["tier"]
            ent["map_color_status"] = r["status"]

    return out
