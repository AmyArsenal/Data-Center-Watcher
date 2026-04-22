#!/usr/bin/env python3.14
"""
Parse X posts from a last30days raw markdown dump, classify + geocode them,
and insert into data/news.db. Re-exports data/social_events.json when done.
"""

import hashlib
import json
import re
import sqlite3
import sys
from pathlib import Path

import os

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "news.db"
# LAST30DAYS_RAW_PATH env var lets run_daily.sh point at today's raw file
RAW_PATH = Path(os.environ.get(
    "LAST30DAYS_RAW_PATH",
    str(Path.home() / "Documents/Last30Days/data-center-oppositions-in-us-raw-v3-xkey2.md"),
))

# Copy of the exporter from build_news_db so this script is standalone
from build_news_db import export_json  # type: ignore

STATE_NAMES = {
    "AL": "alabama", "AK": "alaska", "AZ": "arizona", "AR": "arkansas",
    "CA": "california", "CO": "colorado", "CT": "connecticut", "DE": "delaware",
    "FL": "florida", "GA": "georgia", "HI": "hawaii", "ID": "idaho",
    "IL": "illinois", "IN": "indiana", "IA": "iowa", "KS": "kansas",
    "KY": "kentucky", "LA": "louisiana", "ME": "maine", "MD": "maryland",
    "MA": "massachusetts", "MI": "michigan", "MN": "minnesota", "MS": "mississippi",
    "MO": "missouri", "MT": "montana", "NE": "nebraska", "NV": "nevada",
    "NH": "new hampshire", "NJ": "new jersey", "NM": "new mexico", "NY": "new york",
    "NC": "north carolina", "ND": "north dakota", "OH": "ohio", "OK": "oklahoma",
    "OR": "oregon", "PA": "pennsylvania", "RI": "rhode island", "SC": "south carolina",
    "SD": "south dakota", "TN": "tennessee", "TX": "texas", "UT": "utah",
    "VT": "vermont", "VA": "virginia", "WA": "washington", "WV": "west virginia",
    "WI": "wisconsin", "WY": "wyoming",
}

CITY_HINTS = {
    # City/county phrases that disambiguate state (sorted long-first for regex priority)
    "portage county ohio": ("OH", "Portage County"),
    "northeast ohio": ("OH", None),
    "richland parish": ("LA", "Richland Parish"),
    "coweta county": ("GA", "Coweta County"),
    "madison county, mississippi": ("MS", "Madison County"),
    "prince william county": ("VA", "Prince William County"),
    "loudoun county": ("VA", "Loudoun County"),
    "cumberland county": ("NC", "Cumberland County"),
    "will county": ("IL", "Will County"),
    "berks county": ("PA", "Berks County"),
    "hunt county": ("TX", "Hunt County"),
    "mount pleasant": ("WI", "Mount Pleasant"),
    "new albany": ("OH", "New Albany"),
    "new mexico": ("NM", None),
    "new jersey": ("NJ", None),
    "new york": ("NY", None),
    "south bay": ("CA", "South Bay"),
    "silicon valley": ("CA", None),
    "north carolina": ("NC", None),
    "south carolina": ("SC", None),
    "virginia": ("VA", None),
    "abilene": ("TX", "Abilene"),
    "claremore": ("OK", "Claremore"),
    "ravenna": ("OH", "Ravenna"),
    "williamstown": ("NJ", "Williamstown"),
    "chesterton": ("IN", "Chesterton"),
    "rosemount": ("MN", "Rosemount"),
    "quincy": ("WA", "Quincy"),
    "omaha": ("NE", "Omaha"),
    "lansing": ("MI", "Lansing"),
    "newark": ("OH", "Newark"),
    "raleigh": ("NC", "Raleigh"),
    "becker": ("MN", "Becker"),
    "festus": ("MO", "Festus"),
    "independence, missouri": ("MO", "Independence"),
    "temple, texas": ("TX", "Temple"),
    "columbus city": ("GA", "Columbus"),
    "columbus, ohio": ("OH", "Columbus"),
    "cascade locks": ("OR", "Cascade Locks"),
    "catlett station": ("VA", "Catlett Station"),
    "peculiar": ("MO", "Peculiar"),
    "chandler": ("AZ", "Chandler"),
    "tucson": ("AZ", "Tucson"),
    "phoenix": ("AZ", "Phoenix"),
    "tri-state": ("US", None),
    "wisconsin": ("WI", None),
    "tennessee": ("TN", None),
    "arizona": ("AZ", None),
    "maine": ("ME", None),
    "missouri": ("MO", None),
    "ohio": ("OH", None),
    "oklahoma": ("OK", None),
    "pennsylvania": ("PA", None),
    "michigan": ("MI", None),
    "iowa": ("IA", None),
    "minnesota": ("MN", None),
    "louisiana": ("LA", None),
    "oregon": ("OR", None),
    "georgia": ("GA", None),
    "florida": ("FL", None),
    "indiana": ("IN", None),
    "kentucky": ("KY", None),
    "alabama": ("AL", None),
    "nevada": ("NV", None),
    "colorado": ("CO", None),
    "utah": ("UT", None),
    "california": ("CA", None),
    "texas": ("TX", None),
    "illinois": ("IL", None),
    "washington state": ("WA", None),
}


def detect_state(text: str) -> tuple[str, str | None]:
    """Match against CITY_HINTS long-first so 'columbus, ohio' beats 'columbus'."""
    h = text.lower()
    for hint in sorted(CITY_HINTS.keys(), key=len, reverse=True):
        if hint in h:
            code, city = CITY_HINTS[hint]
            return code, city
    for code, name in STATE_NAMES.items():
        if re.search(rf"\b{re.escape(name)}\b", h):
            return code, None
    return "US", None


def classify(headline: str) -> str:
    h = headline.lower()
    if re.search(r"\b(moratorium|ban|banned|freez(e|ing)|pause)\b", h):
        return "banned"
    if re.search(r"\b(cancel|withdraw|reject|block|scrap|kill)\b", h):
        return "cancelled"
    if re.search(r"\b(protest|oppose|oppos|push.?back|resist|slam|arrested|fight|rally)\b", h):
        return "protested"
    if re.search(r"\b(announce|approv|unveil|break ground|groundbreak|launch)\b", h):
        return "announced"
    return "protested"  # default for opposition topic


def parse_x_items(text: str) -> list[dict]:
    """Extract X items from the markdown body, including any Evidence snippet."""
    items = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        m = re.match(r"\s*\d+\.\s+\[x\]\s+(.+?)$", lines[i])
        if not m:
            i += 1
            continue
        headline = m.group(1).strip()
        date = None
        handle = None
        likes = None
        rt = None
        url = None
        evidence = ""
        j = i + 1
        while j < len(lines) and not lines[j].lstrip().startswith(("1. [", "2. [", "3. [", "4. [", "5. [", "6. [", "### ")):
            ln = lines[j].strip()
            if ln.startswith("- ") and "|" in ln and not date:
                parts = [p.strip() for p in ln.lstrip("- ").split("|")]
                if len(parts) >= 3:
                    date = parts[0]
                    handle = parts[1].lstrip("@")
                    eng = parts[2]
                    like_m = re.search(r"([\d,]+)\s*likes?", eng)
                    rt_m = re.search(r"([\d,]+)\s*rt", eng)
                    if like_m: likes = int(like_m.group(1).replace(",", ""))
                    if rt_m: rt = int(rt_m.group(1).replace(",", ""))
            elif ln.startswith("- URL:") and not url:
                url = ln.split(":", 1)[1].strip()
            elif ln.startswith("- Evidence:"):
                evidence = ln[len("- Evidence:"):].strip()
            elif evidence and ln and not ln.startswith("-") and not ln.startswith("###"):
                # continuation of evidence
                evidence += " " + ln
            j += 1
        if headline and handle:
            items.append({
                "headline": headline,
                "handle": handle,
                "date": date,
                "likes": likes,
                "rt": rt,
                "url": url,
                "evidence": evidence,
            })
        i = j
    return items


def main():
    if not RAW_PATH.exists():
        print(f"ERROR: raw file not found: {RAW_PATH}")
        sys.exit(1)

    text = RAW_PATH.read_text()
    raw_items = parse_x_items(text)
    print(f"[parse] extracted {len(raw_items)} X items from raw markdown")

    # Dedupe by URL
    seen = set()
    unique = []
    for it in raw_items:
        k = it["url"] or it["headline"][:60]
        if k in seen: continue
        seen.add(k)
        unique.append(it)

    # Rank by likes and take top 10
    unique.sort(key=lambda x: x.get("likes") or 0, reverse=True)
    top = unique[:10]
    print(f"[parse] top {len(top)} by engagement:")
    for t in top:
        print(f"   @{t['handle']} {t.get('likes',0)} likes: {t['headline'][:60]}")

    conn = sqlite3.connect(DB_PATH)
    # Optional cleanup: drop X events older than 35 days to keep the window fresh
    conn.execute("DELETE FROM events WHERE platform='x' AND date < date('now', '-35 days')")
    for t in top:
        search_text = (t["headline"] + " " + (t.get("evidence") or "")).lower()
        state, city = detect_state(search_text)
        category = classify(t["headline"])
        # Stable ID: prefer URL (unique per tweet) else a deterministic MD5 of headline.
        # Python's hash() is randomized per process — unusable for de-dup.
        if t.get("url"):
            url_key = hashlib.md5(t["url"].encode()).hexdigest()[:10]
            ev_id = f"x-{url_key}"
        else:
            h_key = hashlib.md5(t["headline"].encode()).hexdigest()[:10]
            ev_id = f"x-{t['handle']}-{(t['date'] or '').replace('-','')}-{h_key}"
        conn.execute(
            """
            INSERT OR REPLACE INTO events
              (id, state, city, category, headline, source_domain, source_name,
               url, date, platform, engagement_score, upvotes, comments, likes, views,
               sentiment, companies)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ev_id, state, city, category, t["headline"],
                "x.com", f"@{t['handle']}",
                t["url"], t["date"] or "2026-04-21", "x",
                (t.get("likes") or 0) + (t.get("rt") or 0),
                None, None, t.get("likes"), None,
                "negative", json.dumps([]),
            ),
        )
    conn.commit()
    conn.close()
    print(f"[db] inserted {len(top)} X events into {DB_PATH}")

    export_json()


if __name__ == "__main__":
    main()
