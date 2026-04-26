#!/usr/bin/env python3
"""Generate per-state narrative paragraphs using Claude.

Reads each state's dossier (data/api/v1/states/{XX}.json) plus the most
recent state-tagged news + social events, sends a compact briefing pack
to Claude Haiku, and writes the result as data/narratives/{XX}.md with
YAML frontmatter.

The state landing page (state.html) fetches and renders the markdown.

Run weekly via .github/workflows/refresh-narratives.yml. Costs ~$0.40
per run for all 50 states with Haiku 4.5. Uses ANTHROPIC_API_KEY env.

Skips states with grade=N/A (insufficient data — narrative would be noise).
Idempotent: same input produces ~similar output, but we write fresh files
each run with a new generated_at stamp.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

DATA_DIR       = ROOT / "data"
API_DIR        = DATA_DIR / "api" / "v1"
NARRATIVES_DIR = DATA_DIR / "narratives"
NEWS_JSON      = DATA_DIR / "news.json"
SOCIAL_JSON    = DATA_DIR / "social_events.json"

MODEL_ID       = os.environ.get("DCW_NARRATIVE_MODEL", "claude-haiku-4-5-20251001")
MAX_TOKENS     = 700                                # narrative is short
RECENT_DAYS    = 30                                 # news/social window per state
SLEEP_BETWEEN  = 0.3                                # gentle on the API

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("narratives")


SYSTEM_PROMPT = """You are the in-house analyst for a data center risk-intelligence
product. Every Sunday you write a short briefing for one US state.

Your audience is site-selection teams at hyperscalers, utility planners,
investors with REIT or hyperscaler exposure, statehouse policy and legal teams,
and journalists. They are sharp. They do not need things explained twice.

Voice rules — these are non-negotiable:
- Zero em dashes in any output.
- No triadic structures ("A. B. C." or "X, Y, and Z" lists of three).
- No "Not just X, but Y", "concretely", "in plain English", "load-bearing",
  "thread the needle", "calibrated", "candidate-list strategy".
- No fake testimonials or anonymous quotes.
- No "What developers should read from this" or "What we'll be tracking next".
- Short sentences. Direct claims. No hedging. No filler.
- Write as a human analyst would, not an LLM giving a balanced overview.
- Cite specific bills, counties, companies, court cases by name.
  Generic statements ("there is opposition activity") are useless.
- If the data is thin, say so plainly in one sentence and stop.

Structure — produce exactly four sections, in this order, with these headers:

## Bottom line
One sentence. The state's situation as of this week.

## County-level risk
Two to four sentences. Which counties are hot. Which are cool. Where the
moratoriums or denials are clustering. Name the counties.

## Watch list (next 30 days)
Two to four sentences. Bills moving in committee, council votes scheduled,
court hearings, governor actions, ballot signature deadlines. Name the
specific items with dates if you have them.

## Social pulse
One to two sentences. What community organizers and online chatter are
focused on. Cite specific platforms, posts, or campaigns by name where you
can. Skip this section entirely if you have no social data.

Keep total output under 250 words. No preamble. No closing summary."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _recent(date_str: str | None, days: int = RECENT_DAYS) -> bool:
    if not date_str: return False
    try:
        d = datetime.strptime(date_str[:10], "%Y-%m-%d").date()
    except ValueError:
        return False
    return (datetime.now(timezone.utc).date() - d).days <= days


def _load_index() -> list[dict]:
    """Return the per-state index from data/api/v1/states.json."""
    return json.loads((API_DIR / "states.json").read_text())["states"]


def _load_dossier(state: str) -> dict | None:
    p = API_DIR / "states" / f"{state}.json"
    return json.loads(p.read_text()) if p.exists() else None


def _load_news_for_state(state: str, limit: int = 25) -> list[dict]:
    if not NEWS_JSON.exists():
        return []
    items = json.loads(NEWS_JSON.read_text()).get("items", [])
    rel = [
        i for i in items
        if i.get("state") == state and _recent(i.get("date"))
    ]
    rel.sort(key=lambda i: i.get("date", ""), reverse=True)
    return rel[:limit]


def _load_social_for_state(state: str, limit: int = 12) -> list[dict]:
    if not SOCIAL_JSON.exists():
        return []
    items = json.loads(SOCIAL_JSON.read_text()).get("items", [])
    rel = [
        i for i in items
        if i.get("state") == state and _recent(i.get("date"))
    ]
    rel.sort(key=lambda i: i.get("engagement_score", 0), reverse=True)
    return rel[:limit]


def _build_briefing(state: str, dossier: dict, news: list[dict], social: list[dict]) -> str:
    """Compact human-readable summary of the state's data, sent as the user
    message. Format optimized for the model to extract specifics from."""
    grade = dossier.get("grade", {})
    q     = dossier.get("quantified", {})
    oc    = dossier.get("outcome_counts", {})
    issue = dossier.get("issue_top", {})
    cites = dossier.get("top_citations", [])

    lines = [
        f"# State: {state}",
        f"# Snapshot date: {_today()}",
        "",
        "## Headline metrics",
        f"- Letter grade: {grade.get('letter')} ({grade.get('score', 'n/a')}/100, '{grade.get('label', '')}')",
        f"- Total actions tracked: {dossier.get('count', 0)}",
        f"- Moratoriums: {q.get('moratoriums', 0)}",
        f"- Project denials (community wins): {q.get('denials', 0)}",
        f"- Project approvals (community losses): {q.get('approvals', 0)}",
        f"- Lawsuits: {q.get('lawsuits', 0)}",
        f"- Bills tracked: introduced={q.get('bills_introduced',0)}, "
            f"passed={q.get('bills_passed',0)}, enacted={q.get('bills_enacted',0)}",
        f"- Active companies named in actions: {q.get('active_companies', 0)}",
        f"- Outcome breakdown: {dict(oc)}",
        f"- Top issue tags: {dict(list(issue.items())[:6])}",
        "",
        "## Most recent / most-cited tracked actions",
    ]
    for c in cites[:10]:
        date = c.get("date", "")
        juris = c.get("jurisdiction", "") or ""
        title = (c.get("title") or "")[:200]
        outcome = c.get("outcome", "")
        lines.append(f"- {date} | {juris} | outcome={outcome} | {title}")

    if news:
        lines += ["", f"## Recent news headlines (last {RECENT_DAYS} days)"]
        for n in news[:15]:
            date = n.get("date", "")
            src  = (n.get("source_name") or n.get("source") or "")[:30]
            cat  = n.get("category", "")
            head = (n.get("headline") or "")[:200]
            lines.append(f"- {date} | {src} | {cat} | {head}")

    if social:
        lines += ["", f"## Recent social activity (last {RECENT_DAYS} days, top by engagement)"]
        for s in social[:8]:
            date = s.get("date", "")
            plat = s.get("platform", "")
            eng  = s.get("engagement_score", 0)
            head = (s.get("headline") or "")[:180]
            lines.append(f"- {date} | {plat} | eng={eng} | {head}")

    lines += ["", "## Task",
              "Write the briefing per the system prompt. Use only the data above."]
    return "\n".join(lines)


def _call_claude(briefing: str) -> str:
    """POST to Anthropic Messages API. Returns the assistant text."""
    import urllib.request, urllib.error
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    body = json.dumps({
        "model":      MODEL_ID,
        "max_tokens": MAX_TOKENS,
        "system":     SYSTEM_PROMPT,
        "messages":   [{"role": "user", "content": briefing}],
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        method="POST",
        headers={
            "Content-Type":      "application/json",
            "X-Api-Key":         api_key,
            "Anthropic-Version": "2023-06-01",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body_txt = e.read().decode(errors="replace") if e.fp else ""
        raise RuntimeError(f"Anthropic HTTP {e.code}: {body_txt[:300]}") from None
    return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")


def _frontmatter(state: str, dossier: dict, model_id: str) -> str:
    grade = dossier.get("grade", {})
    return (
        "---\n"
        f"state: {state}\n"
        f"grade: {grade.get('letter')}\n"
        f"grade_score: {grade.get('score')}\n"
        f"action_count: {dossier.get('count')}\n"
        f"generated_at: {_utcnow()}\n"
        f"model: {model_id}\n"
        "---\n\n"
    )


_STATE_NAMES = {
    "AL":"Alabama","AK":"Alaska","AZ":"Arizona","AR":"Arkansas","CA":"California",
    "CO":"Colorado","CT":"Connecticut","DE":"Delaware","DC":"District of Columbia",
    "FL":"Florida","GA":"Georgia","HI":"Hawaii","ID":"Idaho","IL":"Illinois","IN":"Indiana",
    "IA":"Iowa","KS":"Kansas","KY":"Kentucky","LA":"Louisiana","ME":"Maine","MD":"Maryland",
    "MA":"Massachusetts","MI":"Michigan","MN":"Minnesota","MS":"Mississippi","MO":"Missouri",
    "MT":"Montana","NE":"Nebraska","NV":"Nevada","NH":"New Hampshire","NJ":"New Jersey",
    "NM":"New Mexico","NY":"New York","NC":"North Carolina","ND":"North Dakota","OH":"Ohio",
    "OK":"Oklahoma","OR":"Oregon","PA":"Pennsylvania","RI":"Rhode Island","SC":"South Carolina",
    "SD":"South Dakota","TN":"Tennessee","TX":"Texas","UT":"Utah","VT":"Vermont","VA":"Virginia",
    "WA":"Washington","WV":"West Virginia","WI":"Wisconsin","WY":"Wyoming",
}


def _stub_briefing(state: str, dossier: dict, news: list[dict], social: list[dict]) -> str:
    """Template-driven briefing from raw data (no API call). Used as a
    placeholder until Claude is wired in CI; gets overwritten on the first
    real refresh-narratives run.

    Avoids the AI-slop tells from the system prompt: no em dashes, no triadic
    structures, short sentences."""
    name  = _STATE_NAMES.get(state, state)
    grade = dossier.get("grade", {})
    q     = dossier.get("quantified", {})
    cites = dossier.get("top_citations", [])

    bills_total = (q.get("bills_introduced", 0) + q.get("bills_passed", 0)
                   + q.get("bills_enacted", 0))
    moratoriums = q.get("moratoriums", 0)
    denials     = q.get("denials", 0)
    lawsuits    = q.get("lawsuits", 0)

    # --- Bottom line ---
    if grade.get("letter") in ("F", "D"):
        bottom = (f"{name} is one of the harder states to build a hyperscale data center in right now, "
                  f"with {moratoriums} active or proposed moratorium{'s' if moratoriums != 1 else ''} "
                  f"and {denials} community win{'s' if denials != 1 else ''} against projects in our database.")
    elif grade.get("letter") == "C":
        bottom = (f"{name} is mid-pack: meaningful regulatory activity in both directions, "
                  f"{bills_total} bill{'s' if bills_total != 1 else ''} tracked, "
                  f"{denials} project denial{'s' if denials != 1 else ''} on record.")
    elif grade.get("letter") == "B":
        bottom = (f"{name} remains a relatively friendly jurisdiction for new builds, "
                  f"with limited moratorium activity and {bills_total} bill{'s' if bills_total != 1 else ''} tracked.")
    else:
        bottom = f"Limited recent data for {name}. Updated grade pending more activity."

    # --- County-level risk ---
    counties = []
    for c in cites[:10]:
        j = c.get("jurisdiction") or ""
        # Extract county/city if present in the jurisdiction string
        if "County" in j or "City Council" in j or "Township" in j or "Board" in j:
            counties.append(j)
    counties = list(dict.fromkeys(counties))[:3]
    if counties:
        county_block = (f"Most concentrated activity has come from "
                        f"{', '.join(counties[:-1])}{' and ' + counties[-1] if len(counties) > 1 else counties[0]}.")
    else:
        county_block = "We do not yet have enough county-level resolution to call out specific jurisdictions."
    if lawsuits:
        county_block += f" {lawsuits} active lawsuit{'s' if lawsuits != 1 else ''} on the docket."

    # --- Watch list ---
    pending_items = [c for c in cites if (c.get("outcome") == "pending")][:3]
    if pending_items:
        watch_lines = []
        for p in pending_items:
            j = (p.get("jurisdiction") or "Unknown").replace("—", " ")
            t = (p.get("title") or "")[:120].replace("—", " ").replace("–", " ")
            watch_lines.append(f"{j}: {t.rstrip('.')}")
        watch = "Items to watch: " + "; ".join(watch_lines) + "."
    else:
        watch = "No major pending items in our queue this week."

    # --- Social pulse ---
    if social:
        plats = sorted(set(s.get("platform", "") for s in social
                           if s.get("platform") and s.get("platform") != "news"))
        top   = social[0]
        head  = (top.get("headline") or "")[:140].rstrip().replace("—", " ").replace("–", " ")
        if plats:
            social_block = (f"Most online discussion this week is on {', '.join(plats[:3])}. "
                            f"Highest-engagement post: \"{head}\".")
        else:
            social_block = f"Highest-engagement recent item: \"{head}\"."
    else:
        social_block = ""

    out = [
        "## Bottom line",
        bottom,
        "",
        "## County-level risk",
        county_block,
        "",
        "## Watch list (next 30 days)",
        watch,
    ]
    if social_block:
        out += ["", "## Social pulse", social_block]
    return "\n".join(out)


def main() -> int:
    NARRATIVES_DIR.mkdir(parents=True, exist_ok=True)

    stub_mode = "--stub" in sys.argv
    if not stub_mode and not os.environ.get("ANTHROPIC_API_KEY"):
        log.error("ANTHROPIC_API_KEY not set; pass --stub to generate placeholders instead")
        return 1

    states = _load_index()
    log.info("loaded %d states from index (mode=%s)", len(states), "stub" if stub_mode else "live")

    written = skipped = errors = 0
    for s in states:
        st = s["state"]
        if s.get("grade") == "N/A":
            skipped += 1
            continue

        dossier = _load_dossier(st)
        if not dossier:
            skipped += 1
            continue

        news   = _load_news_for_state(st)
        social = _load_social_for_state(st)

        if stub_mode:
            body = _stub_briefing(st, dossier, news, social)
            model_tag = "stub"
            dur = 0
        else:
            briefing = _build_briefing(st, dossier, news, social)
            try:
                t0 = time.time()
                body = _call_claude(briefing)
                dur = round(time.time() - t0, 1)
            except Exception as e:
                log.warning("[%s] generation failed: %s", st, e)
                errors += 1
                time.sleep(SLEEP_BETWEEN)
                continue
            model_tag = MODEL_ID

        out = _frontmatter(st, dossier, model_tag) + body.strip() + "\n"
        (NARRATIVES_DIR / f"{st}.md").write_text(out)
        written += 1
        log.info("[%s] wrote %s (grade %s, %d chars, %.1fs)",
                 st, f"{st}.md", dossier["grade"]["letter"], len(body), dur)
        if not stub_mode:
            time.sleep(SLEEP_BETWEEN)

    # Index file the frontend can hit to discover what's available.
    index = []
    for st_meta in states:
        st = st_meta["state"]
        p = NARRATIVES_DIR / f"{st}.md"
        if p.exists():
            index.append({
                "state": st,
                "grade": st_meta.get("grade"),
                "url":   f"data/narratives/{st}.md",
                "size":  p.stat().st_size,
            })
    (NARRATIVES_DIR / "index.json").write_text(json.dumps({
        "schema":       "dcw.narratives.index.v1",
        "generated_at": _utcnow(),
        "model":        ("stub" if stub_mode else MODEL_ID),
        "narratives":   index,
    }, indent=2))

    log.info("✓ done. written=%d skipped=%d errors=%d", written, skipped, errors)
    return 0 if errors == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
