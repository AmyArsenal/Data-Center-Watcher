#!/usr/bin/env python3
"""Parse Polymarket items from a last30days-full raw markdown dump and
upsert them into data/news.db with platform='polymarket'.

Markdown shape (produced by the skill):
    1. [polymarket] <market question>
       - YYYY-MM-DD | [NNN.Nvolume, NNN.Nliquidity] | score:NN
       - URL: https://polymarket.com/event/<slug>
       - Why: <one-line reason>
       - Evidence: up 43.5% this month
"""

from __future__ import annotations

import math
import os
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from lib.classify import classify_category, detect_state, extract_companies, relevance_score  # noqa: E402
from lib.events import upsert      # noqa: E402
from lib.schema import migrate     # noqa: E402

DB_PATH = ROOT / "data" / "news.db"
RAW_PATH = Path(os.environ.get(
    "LAST30DAYS_RAW_PATH",
    str(Path.home() / "Documents/Last30Days/data-center-oppositions-in-us-raw-v3-xkey2.md"),
))

ITEM_RE     = re.compile(r"^\s*\d+\.\s+\[polymarket\]\s+(.+?)\s*$")
STATS_RE    = re.compile(r"^\s*-\s*(\d{4}-\d{2}-\d{2})\s*\|\s*\[([^\]]+)\]\s*\|\s*score\s*:\s*(\d+)", re.I)
URL_RE      = re.compile(r"^\s*-\s*URL\s*:\s*(\S+)", re.I)
WHY_RE      = re.compile(r"^\s*-\s*Why\s*:\s*(.+)$", re.I)
EVIDENCE_RE = re.compile(r"^\s*-\s*Evidence\s*:\s*(.+)$", re.I)
MOVE_RE     = re.compile(r"(up|down|flat)\s+([\d.]+%)\s+this\s+(week|month|day)", re.I)
VOL_RE      = re.compile(r"([\d,.]+)\s*volume",    re.I)
LIQ_RE      = re.compile(r"([\d,.]+)\s*liquidity", re.I)


def _num(s: str) -> float:
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return 0.0


def parse_items(text: str) -> list[dict]:
    """Scan the markdown body for `1. [polymarket] ...` items + their
    attributes on the following indented lines (up to the next item)."""
    items: list[dict] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        m = ITEM_RE.match(lines[i])
        if not m:
            i += 1
            continue
        title = m.group(1).strip()

        date = None
        volume = 0.0
        liquidity = 0.0
        score = 0
        url = None
        why = None
        evidence = None
        movement = None

        j = i + 1
        while j < len(lines):
            ln = lines[j]
            if re.match(r"^\s*\d+\.\s+\[", ln) or ln.startswith("### "):
                break
            sm = STATS_RE.match(ln)
            if sm:
                date = sm.group(1)
                stats = sm.group(2)
                vm = VOL_RE.search(stats)
                lm = LIQ_RE.search(stats)
                if vm: volume    = _num(vm.group(1))
                if lm: liquidity = _num(lm.group(1))
                try: score = int(sm.group(3))
                except ValueError: score = 0
            um = URL_RE.match(ln)
            if um: url = um.group(1).strip()
            ym = WHY_RE.match(ln)
            if ym: why = ym.group(1).strip()
            em = EVIDENCE_RE.match(ln)
            if em:
                evidence = em.group(1).strip()
                mm = MOVE_RE.search(evidence)
                if mm:
                    movement = f"{mm.group(1).lower()} {mm.group(2)} / {mm.group(3)}"
            j += 1

        if title and url:
            items.append({
                "title":     title,
                "date":      date,
                "volume":    volume,
                "liquidity": liquidity,
                "score":     score,
                "url":       url,
                "why":       why,
                "evidence":  evidence,
                "movement":  movement,
            })
        i = j
    return items


def _volume_to_engagement(volume: float) -> int:
    """Log-scale $volume → 0..500 so markets span the same range as
    Reddit upvotes / X likes in the existing feed."""
    if volume <= 0: return 0
    return min(500, int(math.log10(volume + 1) * 75))


def main() -> int:
    if not RAW_PATH.exists():
        print(f"ERROR: raw file not found: {RAW_PATH}", file=sys.stderr)
        return 1

    text = RAW_PATH.read_text()
    raw = parse_items(text)
    print(f"[parse] found {len(raw)} polymarket items")

    conn = sqlite3.connect(DB_PATH)
    migrate(conn)

    accepted = 0
    skipped  = 0
    for m in raw:
        why_text = (m.get("why") or "").lower()
        if any(term in why_text for term in ("irrelevant", "unrelated", "off-topic", "epstein")):
            skipped += 1
            continue

        # Build a blob for our rule-based classifier
        blob  = " ".join(filter(None, [m["title"], m.get("evidence"), m.get("why")]))
        if relevance_score(m["title"], m.get("evidence")) < 0.30 and "data center" not in m["title"].lower():
            skipped += 1
            continue

        state, city = detect_state(blob)
        category    = classify_category(m["title"])

        event = {
            "headline":          m["title"],
            "url":               m["url"],
            "source":            "polymarket",
            "source_tier":       "deep",
            "source_domain":     "polymarket.com",
            "source_name":       "Polymarket",
            "date":              m.get("date") or "2026-04-21",
            "platform":          "polymarket",
            "state":             state,
            "city":              city,
            "category":          category,
            "companies":         extract_companies(blob),
            "snippet":           m.get("evidence"),
            "engagement_score":  _volume_to_engagement(m["volume"]),
            "sentiment":         None,
            "platform_metadata": {
                "poly_volume":    m["volume"],
                "poly_liquidity": m["liquidity"],
                "poly_movement":  m.get("movement"),   # e.g. "up 43.5% / month"
                "poly_why":       m.get("why"),
                "poly_score":     m["score"],
            },
        }
        upsert(conn, event)
        accepted += 1

    conn.commit()
    conn.close()
    print(f"[db] accepted {accepted} polymarket markets, skipped {skipped} as irrelevant")
    return 0


if __name__ == "__main__":
    sys.exit(main())
