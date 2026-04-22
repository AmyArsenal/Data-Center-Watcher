"""Lightweight rule-based classification for ingested events.

Covers three jobs Haiku could do later but doesn't need to for v1:
- detect_state(text) → (state_code, city|None)
- classify_category(headline) → banned | cancelled | contested | announced | protested
- extract_companies(text) → list[str]
- relevance_score(headline, snippet) → 0..1  (drop below 0.3)
"""

from __future__ import annotations

import re

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

CITY_HINTS: dict[str, tuple[str, str | None]] = {
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

# Hyperscalers + prominent AI-lab tenants likely to surface in DC news
COMPANIES = [
    "Microsoft", "Meta", "Google", "Amazon", "AWS", "Oracle",
    "OpenAI", "Anthropic", "xAI", "Nvidia", "CoreWeave", "Nebius",
    "Apple", "Tesla", "Crusoe", "Lambda", "Cerebras", "SambaNova",
    "Equinix", "Digital Realty", "QTS", "CyrusOne", "Iron Mountain",
    "Stack Infrastructure", "DataBank", "Aligned", "Vantage", "Switch",
    "Holtec", "Talen", "Vistra", "Constellation",
]


# Positive signals — headline likely to be about DC opposition/action
_RELEVANT_TERMS = [
    "data center", "datacenter", "data centre",
    "hyperscaler", "ai data", "ai campus",
    "server farm",
]
_OPPOSITION_TERMS = [
    "moratorium", "ban", "banned", "opposition", "oppose", "opposed",
    "protest", "rally", "lawsuit", "sue", "sued", "block", "blocked",
    "reject", "rejected", "cancel", "cancelled", "canceled", "scrap",
    "pause", "pauses", "halts", "halted", "withdraw", "pull",
    "recall", "oust", "vote down", "community", "residents",
    "activist", "nimby", "complaint", "zoning", "moratorium",
    "city council", "county commission", "public hearing",
]


def detect_state(text: str) -> tuple[str, str | None]:
    """Match longest-hint-first so 'columbus, ohio' beats 'columbus'."""
    h = (text or "").lower()
    for hint in sorted(CITY_HINTS.keys(), key=len, reverse=True):
        if hint in h:
            return CITY_HINTS[hint]
    for code, name in STATE_NAMES.items():
        if re.search(rf"\b{re.escape(name)}\b", h):
            return code, None
    return "US", None


def classify_category(headline: str) -> str:
    h = (headline or "").lower()
    if re.search(r"\b(moratorium|ban|banned|freez(e|ing)|pause[sd]?|halt|halted)\b", h):
        return "banned"
    if re.search(r"\b(cancel|cancelled|canceled|withdraw|reject|scrap|kill|pull out)\b", h):
        return "cancelled"
    if re.search(r"\b(sue|sued|lawsuit|court|ruling|appeal|blocked|block)\b", h):
        return "cancelled"
    if re.search(r"\b(protest|oppose|oppos|push.?back|resist|slam|arrested|fight|rally|recall|oust)\b", h):
        return "protested"
    if re.search(r"\b(announce|approv|unveil|break ground|groundbreak|launch|plan(s|ned)?|build)\b", h):
        return "announced"
    return "protested"


def extract_companies(text: str) -> list[str]:
    """Case-insensitive whole-word company match. Returns canonical names."""
    out: list[str] = []
    h = (text or "").lower()
    for name in COMPANIES:
        if re.search(rf"\b{re.escape(name.lower())}\b", h) and name not in out:
            out.append(name)
    return out


def relevance_score(headline: str, snippet: str | None = None) -> float:
    """0..1. Requires a DC term AND at least one opposition/regulatory signal.

    Pure industry/announcement news ("OpenAI Stargate DC spans 548k sq ft")
    is not what this tracker is about, so it scores 0 even though 'data
    center' is mentioned.
    """
    blob = f"{headline or ''} {snippet or ''}".lower()
    has_dc = any(term in blob for term in _RELEVANT_TERMS)
    if not has_dc:
        return 0.0
    hits = sum(1 for term in _OPPOSITION_TERMS if term in blob)
    if hits == 0:
        return 0.0
    score = 0.30 + min(0.6, hits * 0.12)
    # Strong docket / legal signals
    if re.search(r"\b(ferc|docket|elibrary|ruling|injunction|appeal)\b", blob):
        score += 0.10
    return max(0.0, min(1.0, score))
