"""OpenStates v3 REST API adapter.

Pulls data-center-relevant bills across all 50 states + DC. Registered free
tier raises the rate limit from 500 req/day unauth to comfortably above our
hourly refresh usage.

Docs: https://docs.openstates.org/api-v3/
Sign up for a free key: https://openstates.org/accounts/profile/
Set via env var OPENSTATES_API_KEY (or ~/.config/last30days/.env, which
run_daily.sh loads). Silently returns [] without a key so CI still passes.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

import requests

log = logging.getLogger(__name__)

API = "https://v3.openstates.org"
USER_AGENT = "DataCenterWatcher/0.3 (+https://github.com/AmyArsenal/Data-Center-Watcher)"
TIMEOUT = 25

# Per-state query terms. We combine into OR to stay within the free quota.
# OpenStates full-text search is OR'd by default across multi-word queries;
# we run two narrower queries instead of one wide one to avoid recall issues.
QUERIES = [
    '"data center"',
    '"hyperscale" OR "large-load"',
]

# 50 states + DC. We skip territories.
STATES = [
    "al", "ak", "az", "ar", "ca", "co", "ct", "dc", "de", "fl",
    "ga", "hi", "id", "il", "in", "ia", "ks", "ky", "la", "me",
    "md", "ma", "mi", "mn", "ms", "mo", "mt", "ne", "nv", "nh",
    "nj", "nm", "ny", "nc", "nd", "oh", "ok", "or", "pa", "ri",
    "sc", "sd", "tn", "tx", "ut", "vt", "va", "wa", "wv", "wi", "wy",
]


def _load_env_file(path: Path) -> None:
    """Cheap key=value loader so the adapter works from a cron run without
    source ~/.config/last30days/.env."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip()
        if k and k not in os.environ:
            os.environ[k] = v


def _api_key() -> str | None:
    _load_env_file(Path.home() / ".config" / "last30days" / ".env")
    return os.environ.get("OPENSTATES_API_KEY")


def _derive_status(actions: list[dict]) -> tuple[str, str, str]:
    """Condense OpenStates' action list into (status, status_date, description).

    OpenStates uses a controlled vocabulary in `classification`. We pick the
    strongest signal present:
        enacted > passed-both > passed-upper > passed-lower > in-committee > introduced
    Unknown classifications drop through to 'in-committee' as a safe middle.
    """
    if not actions:
        return ("introduced", "", "")

    chamber_passage = {"lower": False, "upper": False}
    enacted = False
    most_recent = actions[0]  # OpenStates returns newest-first
    last_desc = most_recent.get("description") or ""
    last_date = (most_recent.get("date") or "")[:10]

    for a in actions:
        classes = a.get("classification") or []
        if "executive-signature" in classes or "became-law" in classes:
            enacted = True
        if "passage" in classes:
            org = a.get("organization") or {}
            classification = (org.get("classification") or "").lower()
            if classification == "lower":   chamber_passage["lower"] = True
            elif classification == "upper": chamber_passage["upper"] = True

    if enacted:
        status = "enacted"
    elif chamber_passage["lower"] and chamber_passage["upper"]:
        status = "passed-both"
    elif chamber_passage["upper"]:
        status = "passed-upper"
    elif chamber_passage["lower"]:
        status = "passed-lower"
    elif any("committee-passage" in (a.get("classification") or []) for a in actions):
        status = "passed-committee"
    elif any("introduction" in (a.get("classification") or []) for a in actions):
        status = "in-committee"
    else:
        status = "in-committee"

    return (status, last_date, last_desc)


def _normalize(bill: dict, state: str, query: str) -> dict:
    ocd_id = bill.get("id") or ""
    actions = bill.get("actions") or []
    status, status_date, last_desc = _derive_status(actions)

    sponsors = []
    for s in bill.get("sponsorships") or []:
        sponsors.append({
            "name":    s.get("name"),
            "primary": s.get("primary", False),
            "party":   (s.get("person") or {}).get("party"),
        })

    # OpenStates surfaces the legislature URL via `sources`, not `url`
    url_source = ""
    for src in bill.get("sources") or []:
        if src.get("url"):
            url_source = src["url"]
            break

    introduced = ""
    for a in actions:
        if "introduction" in (a.get("classification") or []):
            introduced = (a.get("date") or "")[:10]
            break

    return {
        "id":                      f"openstates:{ocd_id}",
        "state":                   state.upper(),
        "bill_number":             bill.get("identifier") or "",
        "session":                 bill.get("session") or "",
        "title":                   bill.get("title") or "",
        "summary":                 (bill.get("abstract") or ""),
        "status":                  status,
        "status_date":             status_date,
        "introduced_date":         introduced,
        "last_action_date":        status_date,
        "last_action_description": last_desc,
        "sponsors":                sponsors,
        "subjects":                bill.get("subject") or [],
        "url_openstates":          bill.get("openstates_url")
                                   or f"https://openstates.org/{state.lower()}/bills/{bill.get('session','')}/{bill.get('identifier','').replace(' ','')}/",
        "url_source":              url_source,
        "openstates_query":        query,
    }


def fetch(
    states: list[str] | None = None,
    updated_since: str | None = None,
    per_page: int = 20,
) -> list[dict]:
    """Return normalized bill dicts ready for classification + upsert.

    `updated_since`: ISO timestamp. If provided, OpenStates returns only
    bills with activity after that time — critical for the hourly-incremental
    pattern.
    """
    key = _api_key()
    if not key:
        log.warning("[openstates] OPENSTATES_API_KEY not set — skipping. "
                    "Register at https://openstates.org/accounts/profile/")
        return []

    target_states = states or STATES
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "X-API-KEY":  key,
    })

    out: list[dict] = []
    for st in target_states:
        for q in QUERIES:
            params = {
                "jurisdiction": st,
                "q":            q,
                "sort":         "updated_desc",
                "include":      ["sponsorships", "actions", "sources", "abstracts"],
                "per_page":     per_page,
            }
            if updated_since:
                params["updated_since"] = updated_since
            try:
                r = session.get(f"{API}/bills", params=params, timeout=TIMEOUT)
                if r.status_code == 429:
                    log.warning("[openstates] 429 rate-limited on %s q=%s — sleeping 5s", st, q[:24])
                    time.sleep(5)
                    continue
                r.raise_for_status()
                data = r.json()
            except Exception as e:
                log.warning("[openstates] %s q=%s failed: %s", st, q[:24], e)
                continue

            for bill in data.get("results", []):
                out.append(_normalize(bill, st, q))
            time.sleep(0.3)  # gentle; OpenStates is fine with this

    log.info("[openstates] fetched %d raw bill records across %d states", len(out), len(target_states))
    return out
