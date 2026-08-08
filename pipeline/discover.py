#!/usr/bin/env python3
"""Discover candidate places for a city from OpenStreetMap and add them to
the research ledger as `unchecked`.

Data: © OpenStreetMap contributors, ODbL (openstreetmap.org/copyright).
OSM is the seed source because its license permits storing the data —
Google Places does not. Rows created here carry source: "osm".

Usage:
  python pipeline/discover.py --city tahoe-city [--radius-km 8] [--dry-run]
  python pipeline/discover.py --all-launched
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

from common import REPO_ROOT
from ledger import load_city, norm_name, save_city, slugify, upsert_place

# Public Overpass instances, tried in order (the primary 504s under load).
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
USER_AGENT = "DogEaredGuides-discover/0.1 (akoura42.slc@gmail.com)"
CITIES_DIR = REPO_ROOT / "data" / "cities"

# OSM tag -> our category. Order matters: first match wins.
TAG_CATEGORIES: list[tuple[str, str, str]] = [
    ("amenity", "restaurant", "eat"),
    ("amenity", "fast_food", "eat"),
    ("amenity", "cafe", "eat"),
    ("amenity", "bar", "drink"),
    ("amenity", "pub", "drink"),
    ("amenity", "biergarten", "drink"),
    ("craft", "brewery", "drink"),
    ("tourism", "hotel", "stay"),
    ("tourism", "motel", "stay"),
    ("tourism", "guest_house", "stay"),
    ("tourism", "chalet", "stay"),
    ("tourism", "camp_site", "stay"),
    ("leisure", "dog_park", "dog-park"),
    ("leisure", "park", "trail"),
    ("natural", "beach", "beach"),
    ("shop", "pet", "pet-supply"),
    ("shop", "pet_grooming", "services"),
    ("amenity", "veterinary", "services"),
    ("amenity", "animal_boarding", "daycare"),
]


def overpass_query(lat: float, lng: float, radius_m: int) -> str:
    # One regex clause per tag key (6 spatial passes instead of 18) — the
    # expanded per-value form times out on busy public instances.
    by_key: dict[str, list[str]] = {}
    for k, v, _ in TAG_CATEGORIES:
        by_key.setdefault(k, []).append(v)
    clauses = "".join(
        f'nwr(around:{radius_m},{lat},{lng})["{k}"~"^({"|".join(vals)})$"]["name"];'
        for k, vals in by_key.items()
    )
    return f"[out:json][timeout:60];({clauses});out center tags;"


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    import math

    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def categorize(tags: dict) -> str | None:
    for k, v, category in TAG_CATEGORIES:
        if tags.get(k) == v:
            return category
    return None


def city_config(slug: str) -> dict:
    for f in CITIES_DIR.glob("*.yaml"):
        cfg = yaml.safe_load(f.read_text())
        if isinstance(cfg, dict) and cfg.get("slug") == slug:
            return cfg
    raise SystemExit(f"no city config with slug {slug}")


def launched_city_slugs() -> list[str]:
    slugs = []
    for f in sorted(CITIES_DIR.glob("*.yaml")):
        cfg = yaml.safe_load(f.read_text())
        if isinstance(cfg, dict) and cfg.get("launched"):
            slugs.append(cfg["slug"])
    return slugs


def discover(city_slug: str, radius_km: float | None, dry_run: bool) -> int:
    cfg = city_config(city_slug)
    lat, lng = cfg["geo"]["lat"], cfg["geo"]["lng"]
    # Radius: CLI override > city yaml `discover_radius_km` > 8 km default.
    # One global radius under-discovers metros and over-reaches hamlets.
    effective_km = radius_km if radius_km is not None else cfg.get("discover_radius_km") or 8.0
    query = overpass_query(lat, lng, int(effective_km * 1000))

    elements: list[dict] | None = None
    last_error: Exception | None = None
    for url in OVERPASS_URLS:
        try:
            req = urllib.request.Request(
                url,
                data=urllib.parse.urlencode({"data": query}).encode(),
                headers={"User-Agent": USER_AGENT},
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                elements = json.load(resp)["elements"]
            break
        except Exception as exc:  # noqa: BLE001 - try the next mirror
            last_error = exc
            print(f"  overpass {url} failed ({exc}); trying next mirror")
            time.sleep(3)
    if elements is None:
        raise SystemExit(f"all Overpass instances failed: {last_error}")

    places = load_city(city_slug)
    known_refs = {row["osm_ref"] for row in places.values() if row.get("osm_ref")}

    added = adopted = 0
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name")
        if not name:
            continue
        category = categorize(tags)
        if not category:
            continue
        # Identity is the OSM element ref, not the name: two chain stores
        # with the same name are two places. Name-only dedup used to
        # collapse them into one row forever.
        ref = f"{el['type'][0]}{el['id']}"
        if ref in known_refs:
            continue  # already tracked under its OSM identity
        el_lat = el.get("lat") or (el.get("center") or {}).get("lat")
        el_lng = el.get("lon") or (el.get("center") or {}).get("lon")

        # Legacy rows (pre-osm_ref) are matched by name + proximity: a
        # same-name row within 500 m with no ref yet is the same place and
        # adopts this ref; a same-name row further away is a different
        # location and gets its own row.
        legacy = None
        for row in places.values():
            if row.get("osm_ref") or norm_name(row["name"]) != norm_name(name):
                continue
            r_lat, r_lng = row.get("lat"), row.get("lng")
            if r_lat is None or el_lat is None or _haversine_m(r_lat, r_lng, el_lat, el_lng) <= 500:
                legacy = row
                break
        if legacy is not None:
            legacy["osm_ref"] = ref
            known_refs.add(ref)
            adopted += 1
            continue

        pid = f"osm-{ref}-{slugify(name)}"
        if pid in places:
            continue
        website = tags.get("website") or tags.get("contact:website")
        note_bits = [f"OSM {el['type']}/{el['id']}"]
        if website:
            note_bits.append(website)
        upsert_place(
            places,
            pid=pid,
            name=name,
            city=city_slug,
            category=category,
            status="unchecked",
            note=" · ".join(note_bits),
            source="osm",
            lat=round(el_lat, 5) if el_lat else None,
            lng=round(el_lng, 5) if el_lng else None,
            osm_ref=ref,
        )
        known_refs.add(ref)
        added += 1

    if dry_run:
        print(f"{city_slug}: would add {added} candidates, adopt refs onto {adopted} (dry run)")
    else:
        save_city(city_slug, places)
        print(
            f"{city_slug}: added {added} candidates, adopted refs onto {adopted} "
            f"({len(places)} total tracked)"
        )
    return added


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--city")
    parser.add_argument("--all-launched", action="store_true")
    parser.add_argument(
        "--radius-km",
        type=float,
        default=None,
        help="override the city yaml's discover_radius_km (default 8)",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    slugs = launched_city_slugs() if args.all_launched else [args.city]
    if not slugs or slugs == [None]:
        parser.error("pass --city <slug> or --all-launched")

    for i, slug in enumerate(slugs):
        if i:
            time.sleep(5)  # be polite to the public Overpass instance
        discover(slug, args.radius_km, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
