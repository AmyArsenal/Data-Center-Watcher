"""FIPS county resolution.

Maps free-text city/jurisdiction strings into canonical (state, county_fips,
county_name) tuples. Used by the dossier builder to roll up actions to the
county level — the unit a developer or land-team uses for site selection.

The full Census FIPS table is ~3,143 counties. We keep a static JSON snapshot
at data/fips/counties.json (regenerated with the build helper below). At
runtime we lazy-load + index by state for fast lookup.

Usage:
    from lib.geo import resolve_county
    fips, name = resolve_county('VA', 'Loudoun County')         # → ('51107', 'Loudoun County')
    fips, name = resolve_county('MO', 'Festus')                  # → ('29099', 'Jefferson County')
    fips, name = resolve_county('US', '')                        # → (None, None)
"""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
FIPS_FILE = ROOT / "data" / "fips" / "counties.json"

# A small bootstrap table covering counties we already see in the actions
# table, so the resolver works even before the full FIPS file is generated.
# Order: state, county_fips, canonical_name, common_aliases (lowercase).
_BOOTSTRAP_COUNTIES: list[tuple[str, str, str, list[str]]] = [
    # Virginia
    ("VA", "51107", "Loudoun County",         ["loudoun", "ashburn", "leesburg", "sterling"]),
    ("VA", "51153", "Prince William County",  ["prince william", "manassas", "gainesville", "haymarket"]),
    ("VA", "51061", "Fauquier County",        ["fauquier", "warrenton", "catlett"]),
    ("VA", "51179", "Stafford County",        ["stafford"]),
    ("VA", "51177", "Spotsylvania County",    ["spotsylvania", "fredericksburg"]),
    ("VA", "51047", "Culpeper County",        ["culpeper"]),
    # Maine — statewide-only is fine, but Bangor metro = Penobscot
    ("ME", "23019", "Penobscot County",       ["penobscot", "bangor"]),
    ("ME", "23005", "Cumberland County",      ["cumberland", "portland"]),
    # Missouri
    ("MO", "29099", "Jefferson County",       ["jefferson", "festus", "imperial"]),
    ("MO", "29095", "Jackson County",         ["jackson", "independence", "kansas city"]),
    ("MO", "29165", "Platte County",          ["platte", "peculiar", "kansas city north"]),
    # Texas
    ("TX", "48309", "McLennan County",        ["mclennan", "waco"]),
    ("TX", "48309", "Bell County",            ["bell", "temple", "killeen"]),
    ("TX", "48227", "Howard County",          ["howard"]),
    ("TX", "48441", "Taylor County",          ["taylor", "abilene"]),
    ("TX", "48485", "Wichita County",         ["wichita falls"]),
    ("TX", "48321", "Matagorda County",       ["matagorda"]),
    ("TX", "48231", "Hunt County",            ["hunt"]),
    # Wisconsin
    ("WI", "55101", "Racine County",          ["racine", "mount pleasant"]),
    # Iowa
    ("IA", "19153", "Polk County",            ["polk", "des moines", "west des moines"]),
    # Minnesota
    ("MN", "27037", "Dakota County",          ["dakota", "rosemount"]),
    ("MN", "27141", "Sherburne County",       ["sherburne", "becker"]),
    # Ohio
    ("OH", "39133", "Portage County",         ["portage", "ravenna"]),
    ("OH", "39041", "Delaware County",        ["delaware"]),
    ("OH", "39089", "Licking County",         ["licking", "newark", "new albany"]),
    # Illinois
    ("IL", "17197", "Will County",            ["will county"]),
    # Indiana
    ("IN", "18127", "Porter County",          ["porter", "chesterton"]),
    # Pennsylvania
    ("PA", "42011", "Berks County",           ["berks"]),
    # New Jersey
    ("NJ", "34015", "Gloucester County",      ["gloucester", "williamstown"]),
    # Georgia
    ("GA", "13077", "Coweta County",          ["coweta"]),
    ("GA", "13215", "Muscogee County",        ["columbus", "muscogee"]),
    # Mississippi
    ("MS", "28089", "Madison County",         ["madison county", "canton"]),
    # North Carolina
    ("NC", "37051", "Cumberland County",      ["cumberland nc", "fayetteville"]),
    ("NC", "37119", "Mecklenburg County",     ["mecklenburg", "charlotte"]),
    # Louisiana
    ("LA", "22083", "Richland Parish",        ["richland parish", "delhi"]),
    # Oklahoma
    ("OK", "40109", "Oklahoma County",        ["oklahoma city", "okc"]),
    ("OK", "40143", "Tulsa County",           ["tulsa"]),
    # Washington
    ("WA", "53025", "Grant County",           ["grant", "quincy", "moses lake"]),
    ("WA", "53033", "King County",            ["king", "seattle"]),
    # California
    ("CA", "06065", "Riverside County",       ["riverside", "coachella"]),
    ("CA", "06085", "Santa Clara County",     ["santa clara", "silicon valley", "south bay"]),
    # Arizona
    ("AZ", "04013", "Maricopa County",        ["maricopa", "phoenix", "chandler"]),
    ("AZ", "04019", "Pima County",            ["pima", "tucson"]),
    # Oregon
    ("OR", "41027", "Hood River County",      ["hood river", "cascade locks"]),
]


@lru_cache(maxsize=1)
def _index() -> dict[str, list[tuple[str, str, list[str]]]]:
    """{state_code: [(fips, canonical_name, aliases_lower), ...]}."""
    out: dict[str, list[tuple[str, str, list[str]]]] = {}
    for state, fips, name, aliases in _BOOTSTRAP_COUNTIES:
        out.setdefault(state, []).append((fips, name, aliases))

    # If the full FIPS file is generated, merge it in (won't override
    # bootstrap entries that have richer aliases).
    if FIPS_FILE.exists():
        try:
            extra = json.loads(FIPS_FILE.read_text())
            for st, rows in extra.items():
                bucket = out.setdefault(st, [])
                seen = {fips for fips, _, _ in bucket}
                for r in rows:
                    if r["fips"] in seen: continue
                    bucket.append((r["fips"], r["name"], [r["name"].lower().replace(" county", "")]))
        except Exception as e:
            log.warning("[geo] failed to load %s: %s", FIPS_FILE, e)
    return out


def resolve_county(
    state: str | None,
    text: str | None,
) -> tuple[str | None, str | None]:
    """Best-effort: scan `text` (city / jurisdiction / summary) for a known
    county name or known city alias. Returns (county_fips, county_name) or
    (None, None) if no confident match.

    Always returns (None, None) for state in {None, '', 'US'} since national
    items don't roll up to a county.
    """
    if not state or state == "US":
        return (None, None)
    if not text:
        return (None, None)

    haystack = text.lower()
    for fips, name, aliases in _index().get(state.upper(), []):
        # Try canonical name first
        n = name.lower()
        if n in haystack:
            return (fips, name)
        # Try "<name without 'County'>"
        bare = re.sub(r"\s+county$|\s+parish$", "", n)
        if re.search(rf"\b{re.escape(bare)}\b", haystack):
            return (fips, name)
        # Try aliases (city or local name)
        for alias in aliases:
            if re.search(rf"\b{re.escape(alias.lower())}\b", haystack):
                return (fips, name)
    return (None, None)


# ----------------------------------------------------------------------------
# One-time helper to download + flatten the full Census FIPS dataset.
# Run with:  python -m lib.geo --build-fips
# ----------------------------------------------------------------------------

def _build_fips_csv() -> int:
    """Download the canonical Census 'national_county.txt' and write a
    state-keyed JSON to data/fips/counties.json. Idempotent."""
    import urllib.request
    URL = ("https://www2.census.gov/geo/docs/reference/codes/files/"
           "national_county.txt")
    log.info("downloading %s", URL)
    raw = urllib.request.urlopen(URL, timeout=30).read().decode("latin-1")

    out: dict[str, list[dict]] = {}
    for line in raw.splitlines():
        # Format: STATE,STATEFP,COUNTYFP,COUNTYNAME,CLASSFP
        parts = line.strip().split(",")
        if len(parts) < 4: continue
        st, sfp, cfp, name = parts[0], parts[1], parts[2], parts[3]
        out.setdefault(st, []).append({"fips": sfp + cfp, "name": name})

    FIPS_FILE.parent.mkdir(parents=True, exist_ok=True)
    FIPS_FILE.write_text(json.dumps(out, indent=2))
    log.info("wrote %d states / %d counties to %s",
             len(out), sum(len(v) for v in out.values()), FIPS_FILE)
    return 0


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    if "--build-fips" in sys.argv:
        sys.exit(_build_fips_csv())
    print("Usage: python -m scripts.lib.geo --build-fips")
