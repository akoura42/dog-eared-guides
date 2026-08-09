#!/usr/bin/env python3
"""Geocode data/waterfront-towns.csv into waterfront-towns-geo.json.

Primary source: US Census Bureau Gazetteer places file (public domain,
authoritative point coordinates for incorporated places and CDPs).
Fallback for unincorporated spots: Nominatim (OSM), politely rate-limited.

Run once (and re-run only when the CSV changes):
  python pipeline/geocode_towns.py
"""

from __future__ import annotations

import csv
import io
import json
import re
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CSV_FILE = REPO_ROOT / "data" / "waterfront-towns.csv"
OUT_FILE = REPO_ROOT / "data" / "waterfront-towns-geo.json"

GAZETTEER_URL = (
    "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/"
    "2023_Gazetteer/2023_Gaz_place_national.zip"
)
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "DogEaredGuides-build/0.1 (akoura42.slc@gmail.com)"

STATE_CODES = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT",
    "Delaware": "DE", "Florida": "FL", "Georgia": "GA", "Hawaii": "HI",
    "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA",
    "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME",
    "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI",
    "Minnesota": "MN", "Mississippi": "MS", "Missouri": "MO",
    "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM",
    "New York": "NY", "North Carolina": "NC", "North Dakota": "ND",
    "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA",
    "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD",
    "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT",
    "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
    "Wisconsin": "WI", "Wyoming": "WY",
}

# Gazetteer NAME suffixes, in preference order when a state has duplicates
# (an incorporated city/town beats a CDP of the same name).
LSAD_PREFERENCE = ["city", "town", "village", "borough", "CDP", "municipality"]
NAME_SUFFIX_RE = re.compile(
    r"\s+(city|town|village|borough|CDP|municipality|"
    r"comunidad|zona urbana|city and borough|consolidated government|"
    r"metro government|metropolitan government|urban county|unified government)"
    r"(\s+\(balance\))?$",
    re.IGNORECASE,
)


def norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def load_gazetteer() -> dict[tuple[str, str], tuple[float, float, int]]:
    print("Downloading Census gazetteer…")
    req = urllib.request.Request(GAZETTEER_URL, headers={"User-Agent": USER_AGENT})
    data = urllib.request.urlopen(req, timeout=120).read()
    zf = zipfile.ZipFile(io.BytesIO(data))
    txt = zf.read(zf.namelist()[0]).decode("utf-8", errors="replace")

    places: dict[tuple[str, str], tuple[float, float, int]] = {}
    reader = csv.DictReader(io.StringIO(txt), delimiter="\t")
    for row in reader:
        row = {k.strip(): (v.strip() if v else "") for k, v in row.items()}
        usps = row["USPS"]
        raw_name = row["NAME"]
        m = NAME_SUFFIX_RE.search(raw_name)
        lsad = m.group(1) if m else ""
        base = NAME_SUFFIX_RE.sub("", raw_name)
        try:
            rank = LSAD_PREFERENCE.index(lsad.lower() if lsad != "CDP" else "CDP")
        except ValueError:
            rank = len(LSAD_PREFERENCE)
        key = (usps, norm(base))
        lat, lng = float(row["INTPTLAT"]), float(row["INTPTLONG"])
        if key not in places or rank < places[key][2]:
            places[key] = (lat, lng, rank)
    print(f"Gazetteer: {len(places)} places indexed")
    return places


def nominatim(town: str, state: str) -> tuple[float, float] | None:
    query = urllib.parse.urlencode(
        {"q": f"{town}, {state}, USA", "format": "json", "limit": 1}
    )
    req = urllib.request.Request(
        f"{NOMINATIM_URL}?{query}", headers={"User-Agent": USER_AGENT}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            results = json.load(resp)
        if results:
            return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception as exc:  # noqa: BLE001 - log and continue
        print(f"  nominatim error for {town}, {state}: {exc}")
    return None


def main() -> int:
    import urllib.parse  # noqa: PLC0415

    globals()["urllib"].parse = urllib.parse

    # Map shows tier 1 and 2 towns only; tier 3 stays in the CSV for later.
    rows = [r for r in csv.DictReader(CSV_FILE.open()) if int(r["tier"]) <= 2]
    print(f"CSV: {len(rows)} tier-1/2 towns")
    gaz = load_gazetteer()

    out = []
    misses = []
    for row in rows:
        state = row["state"]
        code = STATE_CODES[state]
        town = row["town"]
        hit = gaz.get((code, norm(town)))
        entry = {
            "name": town,
            "state": state,
            "state_code": code,
            "tier": int(row["tier"]),
            "water_body": row["water_body"],
        }
        if hit:
            entry["lat"], entry["lng"] = round(hit[0], 4), round(hit[1], 4)
            out.append(entry)
        else:
            misses.append(entry)

    print(f"Gazetteer matched {len(out)}; falling back to Nominatim for {len(misses)}")
    still_missing = []
    for entry in misses:
        time.sleep(1.1)  # Nominatim usage policy: max 1 req/sec
        pt = nominatim(entry["name"], entry["state"])
        if pt:
            entry["lat"], entry["lng"] = round(pt[0], 4), round(pt[1], 4)
            out.append(entry)
            print(f"  ✓ {entry['name']}, {entry['state_code']}")
        else:
            still_missing.append(f"{entry['name']}, {entry['state_code']}")
            print(f"  ✗ {entry['name']}, {entry['state_code']} — NOT FOUND, skipped")

    out.sort(key=lambda e: (e["state"], e["name"]))
    OUT_FILE.write_text(json.dumps(out, indent=1) + "\n")
    print(f"\nWrote {len(out)} towns to {OUT_FILE.relative_to(REPO_ROOT)}")
    if still_missing:
        print(f"Unresolved ({len(still_missing)}): {', '.join(still_missing)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
