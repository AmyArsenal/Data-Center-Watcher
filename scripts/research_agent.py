#!/usr/bin/env python3
"""Weekly Claude-powered research agent.

This is how we get from ~300 actions to ~1,000+ over a few months. Claude
Sonnet given a single state + 7-day window does what an analyst would do:
search the web (or feed it our existing news.json + bills.json + a few
target queries), extract structured action records, and emit them as JSON
matching our `actions` schema.

Cost envelope: ~$0.50 per state per week × 50 states = $25/week max.
Realistic: ~$5-10/week because most states have nothing new in a given
week and the agent returns empty quickly.

NOT WIRED YET. Drops here as the next-session scaffold. To run:
  1. ANTHROPIC_API_KEY in env
  2. pip install anthropic
  3. python3 scripts/research_agent.py --states=ME,VA,WI --since=7d
  4. Inspect output, then upsert into actions

Cadence target: weekly. Add to .github/workflows/refresh-research.yml
once we've validated it produces clean output for ~10 states.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

# --- prompt template (the actual research instructions) -------------------
SYSTEM_PROMPT = """You are a research analyst tracking US data-center community
opposition for the Data Center Watcher dashboard.

Your job: given a state and a date window, identify NEW community responses
or legislative actions related to data centers that have happened during
that window. Return a JSON array of records using EXACTLY the schema below.

Sources to draw on (you may search the web):
- Local newspapers (search "data center" + state + city + last week)
- County / city / township meeting agendas + minutes
- State legislature bill trackers
- State PUC dockets
- CourtListener for new federal/state court filings
- Activist group websites + petition sites (Change.org, etc.)
- Reddit local subreddits (r/<state>, r/<county>)

For each action, extract:
  - jurisdiction (e.g. "Loudoun County, VA" or "Maine (statewide)")
  - state (2-letter)
  - county (if applicable)
  - lat/lng if known
  - scope: local | statewide | federal
  - action_type: one or more from [zoning_restriction, legislation, moratorium,
    public_comment, lawsuit, project_withdrawal, utility_regulation, ordinance,
    study_or_report, regulatory_action, executive_order, other_opposition,
    infrastructure_opposition, permit_denial, executive_action]
  - authority_level: one of [county_commission, city_council, state_legislature,
    township_board, court, planning_commission, utility_commission, governor,
    federal_legislature, federal_agency, voters, ...]
  - date (when it happened, YYYY-MM-DD)
  - status (action-specific: active, pending, passed, defeated, ...)
  - community_outcome: pending | win | loss | mixed
  - issue_category: array of 1-4 from [zoning, water, environmental,
    community_impact, grid_energy, transparency, ratepayer, noise, tax_incentive,
    farmland, traffic, design_standards, contract_guarantees, anti_ai, air_quality,
    property_values]
  - company / hyperscaler if known (Microsoft, Meta, Google, Amazon, AWS,
    OpenAI, Oracle, Nebius, CoreWeave, Crusoe, ...)
  - project_name if known
  - investment_million_usd, megawatts, acreage, water_usage_gallons_per_day,
    jobs_promised — leave null if not in source
  - opposition_groups: array of named groups
  - opposition_website / facebook / twitter / instagram if applicable
  - petition_url, petition_signatures if applicable
  - summary: 2-3 sentences, plain English, NO marketing voice
  - sources: array of URLs you used

Quality bar:
- Only include events that actually happened (no rumors, no anticipated)
- Each event must have at least 2 independent sources OR 1 primary source
  (council minutes, court docket, official press release)
- Skip events already in the existing dataset (we will dedup, but flag if
  in doubt)
- If you find NOTHING new, return [] — do not pad
"""

USER_PROMPT_TEMPLATE = """State: {state}
Date window: {since} to {today}

Existing actions in this state from our dataset (so you can avoid dupes):
{existing_summary}

Find new community responses or legislative actions in this state during
the window. Output a JSON array, no preamble, no markdown fences."""


def _summarize_existing(state: str, db_path: Path) -> str:
    """Pull the 10 most-recent existing actions for this state, formatted as
    a one-line-each summary the model can deduplicate against."""
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT date, jurisdiction, summary FROM actions
           WHERE state = ? ORDER BY date DESC LIMIT 10""",
        (state,),
    ).fetchall()
    conn.close()
    if not rows:
        return "(none on file yet)"
    return "\n".join(
        f"  - {r['date'] or '?'}  {r['jurisdiction'] or '?'} — {(r['summary'] or '')[:80]}"
        for r in rows
    )


def run_for_state(state: str, since_days: int = 7) -> list[dict]:
    """Returns a list of new action records for the state. Empty if none."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logging.error("ANTHROPIC_API_KEY not set — research agent cannot run")
        return []

    try:
        from anthropic import Anthropic
    except ImportError:
        logging.error("`pip install anthropic` first")
        return []

    client = Anthropic(api_key=api_key)
    db_path = ROOT / "data" / "news.db"
    today = datetime.now(timezone.utc).date()
    since = today - timedelta(days=since_days)

    user_prompt = USER_PROMPT_TEMPLATE.format(
        state=state, since=since.isoformat(), today=today.isoformat(),
        existing_summary=_summarize_existing(state, db_path),
    )

    # Web search via Claude's built-in tool
    response = client.messages.create(
        model="claude-sonnet-4-6",     # research depth justifies Sonnet over Haiku
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": user_prompt}],
    )

    # Extract the final text block (assistant's JSON output)
    text_blocks = [b.text for b in response.content if hasattr(b, "text")]
    raw = "".join(text_blocks).strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        records = json.loads(raw)
        if not isinstance(records, list):
            logging.warning("[%s] model returned non-list: %s", state, type(records).__name__)
            return []
        return records
    except json.JSONDecodeError as e:
        logging.error("[%s] JSON parse failed: %s\n%s", state, e, raw[:500])
        return []


def main() -> int:
    p = argparse.ArgumentParser(description="Weekly Claude research agent")
    p.add_argument("--states", default="ALL",
                   help="comma-separated state codes, or ALL for all 50")
    p.add_argument("--since-days", type=int, default=7)
    p.add_argument("--out", default=str(ROOT / "data" / "research_pending.json"),
                   help="where to write findings (queue for review before upsert)")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.states == "ALL":
        from lib.sources.openstates import STATES
        states = [s.upper() for s in STATES]
    else:
        states = [s.strip().upper() for s in args.states.split(",")]

    all_records: list[dict] = []
    for st in states:
        logging.info("researching %s (last %d days)", st, args.since_days)
        records = run_for_state(st, since_days=args.since_days)
        for r in records:
            r["state"]       = r.get("state") or st
            r["data_source"] = "agent_research"
            r["origin"]      = "research_agent"
        logging.info("  → %d candidate actions", len(records))
        all_records.extend(records)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(all_records, indent=2))
    logging.info("wrote %d candidate actions to %s", len(all_records), out_path)
    logging.info("REVIEW the file, then upsert with scripts/upsert_research_findings.py")

    return 0


if __name__ == "__main__":
    sys.exit(main())
