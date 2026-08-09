#!/usr/bin/env python3
"""Second discovery source: Overture Maps places -> research ledger.

Overture's places theme (CDLA-Permissive 2.0 — storage is allowed, unlike
Google Places) is fed by Meta business data and refreshes monthly, so it
catches commercial openings YEARS before volunteer-mapped OSM does (the
evo Hotel case: opened Sept 2025, absent from OSM, present in Overture).
OSM (discover.py) stays the better source for parks, trails, and beaches;
run both.

Data: (c) Overture Maps Foundation, from the release given by --release.
Rows created here carry source: "overture" and the place's stable GERS id
in `overture_id`; same-name rows within 500 m adopt the id instead of
duplicating (mirrors discover.py's osm_ref adoption).

Usage:
  python pipeline/discover_overture.py --city tahoe-city [--dry-run]
  python pipeline/discover_overture.py --all-launched
  python pipeline/discover_overture.py --city X --release 2026-07-22.0
"""

from __future__ import annotations

import argparse
import math
import sys
import time

from discover import city_config, launched_city_slugs, _haversine_m
from ledger import load_city, norm_name, save_city, slugify, upsert_place

DEFAULT_RELEASE = "2026-07-22.0"
S3_PATTERN = (
    "s3://overturemaps-us-west-2/release/{release}/theme=places/type=place/*"
)
# Below this Overture confidence score a row is more noise than lead.
MIN_CONFIDENCE = 0.5

# Overture category -> our category. First match wins; unmapped skipped.
CATEGORY_MAP: dict[str, str] = {
    "restaurant": "eat",
    "fast_food_restaurant": "eat",
    "cafe": "eat",
    "coffee_shop": "eat",
    "bakery": "eat",
    "ice_cream_shop": "eat",
    "bar": "drink",
    "pub": "drink",
    "brewery": "drink",
    "wine_bar": "drink",
    "beer_garden": "drink",
    "hotel": "stay",
    "motel": "stay",
    "bed_and_breakfast": "stay",
    "resort": "stay",
    "lodging": "stay",
    "vacation_rental": "stay",
    "campground": "stay",
    "rv_park": "stay",
    "hostel": "stay",
    "dog_park": "dog-park",
    "park": "trail",
    "beach": "beach",
    "pet_store": "pet-supply",
    "pet_supply": "pet-supply",
    "pet_groomer": "services",
    "veterinarian": "services",
    "pet_boarding_and_sitting": "daycare",
    "pet_sitting": "daycare",
    "dog_day_care_center": "daycare",
    "pet_trainer": "services",
}


def bbox_around(lat: float, lng: float, radius_km: float) -> tuple[float, float, float, float]:
    dlat = radius_km / 110.54
    dlng = radius_km / (111.32 * math.cos(math.radians(lat)))
    return lng - dlng, lat - dlat, lng + dlng, lat + dlat


def fetch_places(release: str, lat: float, lng: float, radius_km: float) -> list[dict]:
    import duckdb

    xmin, ymin, xmax, ymax = bbox_around(lat, lng, radius_km)
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; SET s3_region='us-west-2';")
    rows = con.execute(
        f"""
        SELECT
          id,
          names.primary AS name,
          categories.primary AS category,
          confidence,
          (bbox.xmin + bbox.xmax) / 2 AS lng,
          (bbox.ymin + bbox.ymax) / 2 AS lat,
          websites[1] AS website,
          phones[1] AS phone
        FROM read_parquet('{S3_PATTERN.format(release=release)}', hive_partitioning=1)
        WHERE bbox.xmin BETWEEN ? AND ?
          AND bbox.ymin BETWEEN ? AND ?
          AND confidence >= ?
        """,
        [xmin, xmax, ymin, ymax, MIN_CONFIDENCE],
    ).fetchall()
    cols = ["id", "name", "category", "confidence", "lng", "lat", "website", "phone"]
    return [dict(zip(cols, r)) for r in rows]


def discover_overture(city_slug: str, release: str, radius_km: float | None, dry_run: bool) -> int:
    cfg = city_config(city_slug)
    lat, lng = cfg["geo"]["lat"], cfg["geo"]["lng"]
    effective_km = radius_km if radius_km is not None else cfg.get("discover_radius_km") or 8.0

    print(f"{city_slug}: querying Overture {release} within {effective_km} km…")
    raw = fetch_places(release, lat, lng, effective_km)
    print(f"  {len(raw)} places above confidence {MIN_CONFIDENCE}")

    places = load_city(city_slug)
    known_ovt = {r["overture_id"] for r in places.values() if r.get("overture_id")}

    added = adopted = 0
    for p in raw:
        name = p["name"]
        if not name or p["id"] in known_ovt:
            continue
        category = CATEGORY_MAP.get(p["category"] or "")
        if not category:
            continue

        # Same-name row within 500 m (any source) adopts the Overture id —
        # both coords must be known, mirroring discover.py's rule.
        match = None
        for row in places.values():
            if row.get("overture_id") or norm_name(row["name"]) != norm_name(name):
                continue
            r_lat, r_lng = row.get("lat"), row.get("lng")
            if (
                r_lat is not None
                and _haversine_m(r_lat, r_lng, p["lat"], p["lng"]) <= 500
            ):
                match = row
                break
        if match is not None:
            match["overture_id"] = p["id"]
            known_ovt.add(p["id"])
            adopted += 1
            continue

        note_bits = [f"Overture {p['id']} · conf {p['confidence']:.2f}"]
        if p["website"]:
            note_bits.append(p["website"])
        if p["phone"]:
            note_bits.append(p["phone"])
        upsert_place(
            places,
            pid=f"ovt-{p['id'][:8]}-{slugify(name)}",
            name=name,
            city=city_slug,
            category=category,
            status="unchecked",
            note=" · ".join(note_bits),
            source="overture",
            lat=round(p["lat"], 5),
            lng=round(p["lng"], 5),
            overture_id=p["id"],
        )
        known_ovt.add(p["id"])
        added += 1

    if dry_run:
        print(f"{city_slug}: would add {added}, adopt ids onto {adopted} (dry run)")
    else:
        save_city(city_slug, places)
        print(f"{city_slug}: added {added}, adopted ids onto {adopted} ({len(places)} tracked)")
    return added


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--city")
    parser.add_argument("--all-launched", action="store_true")
    parser.add_argument("--release", default=DEFAULT_RELEASE)
    parser.add_argument("--radius-km", type=float, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    slugs = launched_city_slugs() if args.all_launched else [args.city]
    if not slugs or slugs == [None]:
        parser.error("pass --city <slug> or --all-launched")

    failed: list[str] = []
    for i, slug in enumerate(slugs):
        if i:
            time.sleep(1)
        try:
            discover_overture(slug, args.release, args.radius_km, args.dry_run)
        except Exception as exc:  # noqa: BLE001 — one city must not kill the sweep
            print(f"  {slug}: FAILED ({exc})")
            failed.append(slug)
    if failed:
        print(f"\n{len(failed)} city sweep(s) failed: {', '.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
