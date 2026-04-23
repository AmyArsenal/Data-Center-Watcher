#!/usr/bin/env python3
"""Parse TikTok / Instagram / Threads items from a last30days raw markdown
dump and upsert them into data/news.db.

All three platforms share the same markdown shape emitted by the skill:
    1. [<platform>] <caption or title>
       - YYYY-MM-DD | <handle> | [Nviews, Nlikes, Ncmt] | score:NN [ | fun:NN ]
       - URL: https://...
       - Why: <one-line reason>
       - Evidence: <caption / transcript excerpt>

The caller can pass --platforms=tiktok,instagram,threads to restrict the
ingest; default is all three. Irrelevant items (explicitly tagged by the
skill's judge) are dropped before upsert.
"""

from __future__ import annotations

import argparse
import math
import os
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from lib.classify import classify_category, detect_state, extract_companies, relevance_score  # noqa: E402
from lib.events import upsert    # noqa: E402
from lib.schema import migrate   # noqa: E402

DB_PATH = ROOT / "data" / "news.db"
DEFAULT_RAW = Path(os.environ.get(
    "LAST30DAYS_RAW_PATH",
    str(Path.home() / "Documents/Last30Days/data-center-oppositions-in-us-raw-v3.md"),
))

SUPPORTED = ("tiktok", "instagram", "threads")

ITEM_RE     = re.compile(r"^\s*\d+\.\s+\[(tiktok|instagram|threads)\]\s+(.+?)\s*$")
STATS_RE    = re.compile(r"^\s*-\s*(\d{4}-\d{2}-\d{2})\s*\|\s*([^|]+?)\s*\|\s*\[([^\]]+)\]\s*\|\s*score\s*:\s*(\d+)(?:\s*\|\s*fun\s*:\s*(\d+))?", re.I)
URL_RE      = re.compile(r"^\s*-\s*URL\s*:\s*(\S+)", re.I)
WHY_RE      = re.compile(r"^\s*-\s*Why\s*:\s*(.+)$", re.I)
EVIDENCE_RE = re.compile(r"^\s*-\s*Evidence\s*:\s*(.+)$", re.I)

VIEWS_RE    = re.compile(r"([\d,]+)\s*views", re.I)
LIKES_RE    = re.compile(r"([\d,]+)\s*likes?", re.I)
CMTS_RE     = re.compile(r"([\d,]+)\s*cmt", re.I)


def _num(s: str) -> int:
    try:
        return int(s.replace(",", ""))
    except ValueError:
        return 0


def parse_items(text: str, allowed: set[str]) -> list[dict]:
    items: list[dict] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        m = ITEM_RE.match(lines[i])
        if not m or m.group(1).lower() not in allowed:
            i += 1
            continue

        platform = m.group(1).lower()
        title    = m.group(2).strip()

        # Per-item fields we scan on the following indented "- " lines
        date = handle = url = None
        views = likes = comments = 0
        score = fun = 0
        why = evidence = None

        j = i + 1
        while j < len(lines):
            ln = lines[j]
            if re.match(r"^\s*\d+\.\s+\[", ln) or ln.startswith("### "):
                break
            sm = STATS_RE.match(ln)
            if sm:
                date   = sm.group(1)
                handle = sm.group(2).strip().lstrip("@")
                stats  = sm.group(3)
                try: score = int(sm.group(4))
                except ValueError: score = 0
                if sm.group(5):
                    try: fun = int(sm.group(5))
                    except ValueError: fun = 0
                vm = VIEWS_RE.search(stats); likesm = LIKES_RE.search(stats); cm = CMTS_RE.search(stats)
                if vm:    views    = _num(vm.group(1))
                if likesm: likes    = _num(likesm.group(1))
                if cm:    comments = _num(cm.group(1))
            um = URL_RE.match(ln)
            if um: url = um.group(1).strip()
            ym = WHY_RE.match(ln)
            if ym: why = ym.group(1).strip()
            em = EVIDENCE_RE.match(ln)
            if em: evidence = em.group(1).strip()
            j += 1

        if title and url:
            items.append({
                "platform": platform,
                "title":    title,
                "date":     date,
                "handle":   handle,
                "views":    views,
                "likes":    likes,
                "comments": comments,
                "score":    score,
                "fun":      fun,
                "url":      url,
                "why":      why,
                "evidence": evidence,
            })
        i = j
    return items


def _views_to_engagement(views: int, likes: int) -> int:
    """Log-scale views; clip at 500 so viral videos don't nuke the ranking."""
    base = max(views, likes * 4)  # if we only have likes, synthesize a view-equivalent
    if base <= 0: return 0
    return min(500, int(math.log10(base + 1) * 75))


_IRRELEVANT_HINTS = ("irrelevant", "unrelated", "off-topic", "off topic")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(DEFAULT_RAW))
    ap.add_argument("--platforms", default=",".join(SUPPORTED),
                    help="comma-separated subset of: tiktok,instagram,threads")
    args = ap.parse_args()

    raw = Path(args.raw)
    if not raw.exists():
        print(f"ERROR: raw file not found: {raw}", file=sys.stderr)
        return 1

    allowed = {p.strip().lower() for p in args.platforms.split(",") if p.strip()}
    unknown = allowed - set(SUPPORTED)
    if unknown:
        print(f"WARN: ignoring unknown platforms: {sorted(unknown)}", file=sys.stderr)
    allowed &= set(SUPPORTED)

    text = raw.read_text()
    items = parse_items(text, allowed)
    print(f"[parse] found {len(items)} items across {sorted(allowed)}")

    conn = sqlite3.connect(DB_PATH)
    migrate(conn)

    accepted: dict[str, int] = {}
    skipped  = 0
    for m in items:
        why_text = (m.get("why") or "").lower()
        if any(h in why_text for h in _IRRELEVANT_HINTS):
            skipped += 1
            continue

        blob = " ".join(filter(None, [m["title"], m.get("evidence"), m.get("why")]))
        if relevance_score(m["title"], m.get("evidence")) < 0.30 and "data center" not in blob.lower():
            skipped += 1
            continue

        state, city = detect_state(blob)
        category    = classify_category(m["title"])

        event = {
            "headline":         m["title"],
            "url":              m["url"],
            "source":           m["platform"],
            "source_tier":      "deep",
            "source_domain":    f"{m['platform']}.com",
            "source_name":      f"@{m['handle']}" if m.get("handle") else m["platform"].capitalize(),
            "date":             m.get("date") or "2026-04-23",
            "platform":         m["platform"],
            "state":            state,
            "city":             city,
            "category":         category,
            "companies":        extract_companies(blob),
            "snippet":          m.get("evidence"),
            "engagement_score": _views_to_engagement(m["views"], m["likes"]),
            "views":            m["views"] or None,
            "likes":            m["likes"] or None,
            "comments":         m["comments"] or None,
            "sentiment":        None,
            "platform_metadata": {
                f"{m['platform']}_handle": m.get("handle"),
                f"{m['platform']}_score":  m["score"],
                f"{m['platform']}_fun":    m["fun"] or None,
                f"{m['platform']}_why":    m.get("why"),
            },
        }
        upsert(conn, event)
        accepted[m["platform"]] = accepted.get(m["platform"], 0) + 1

    conn.commit()
    conn.close()
    summary = ", ".join(f"{k}={v}" for k, v in sorted(accepted.items())) or "none"
    print(f"[db] accepted [{summary}], skipped {skipped} as irrelevant")
    return 0


if __name__ == "__main__":
    sys.exit(main())
