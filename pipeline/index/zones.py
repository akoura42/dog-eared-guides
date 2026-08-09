"""Fetch dog-zone polygons from OSM and write the explorer's zone layer.

Reads data/cities/<slug>/zones.yaml (curated: policy + note + source per
zone, grounded in the catalog's verified records — OSM supplies geometry
only), queries Overpass for each zone's polygon, simplifies it, computes
acreage, and writes data/cities/<slug>/zones.geojson for the web app.

Usage: python pipeline/index/zones.py <town-slug>

Boundaries are mapper-drawn and approximate; acreage is computed with an
equirectangular shoelace and is indicative, not survey-grade.
"""

from __future__ import annotations

import json
import math
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
TOWNS_DIR = REPO_ROOT / "data" / "cities"
OVERPASS = "https://overpass-api.de/api/interpreter"
SEARCH_RADIUS_M = 12000
SIMPLIFY_TOLERANCE_M = 8.0


def overpass(query: str) -> dict:
    data = urllib.parse.urlencode({"data": query}).encode()
    req = urllib.request.Request(
        OVERPASS, data=data, headers={"User-Agent": "dog-eared-guides-zones/1.0"}
    )
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                return json.loads(resp.read())
        except Exception as e:  # busy server, malformed retry
            if attempt == 3:
                raise
            print(f"  overpass retry ({e})", file=sys.stderr)
            time.sleep(20 * (attempt + 1))
    raise RuntimeError("unreachable")


# --- geometry helpers -------------------------------------------------------

def ring_from_way(way: dict) -> list[list[float]] | None:
    geom = way.get("geometry")
    if not geom:
        return None
    ring = [[p["lon"], p["lat"]] for p in geom]
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    return ring


def rings_from_relation(rel: dict) -> list[list[list[float]]]:
    """Stitch outer-member ways into closed rings."""
    segments = [
        [[p["lon"], p["lat"]] for p in m["geometry"]]
        for m in rel.get("members", [])
        if m.get("role") in ("outer", "") and m.get("geometry")
    ]
    rings: list[list[list[float]]] = []
    while segments:
        ring = segments.pop(0)
        progress = True
        while ring[0] != ring[-1] and progress:
            progress = False
            for i, seg in enumerate(segments):
                if seg[0] == ring[-1]:
                    ring += seg[1:]
                elif seg[-1] == ring[-1]:
                    ring += seg[-2::-1]
                elif seg[-1] == ring[0]:
                    ring = seg[:-1] + ring
                elif seg[0] == ring[0]:
                    ring = seg[::-1][:-1] + ring
                else:
                    continue
                segments.pop(i)
                progress = True
                break
        if ring[0] == ring[-1] and len(ring) >= 4:
            rings.append(ring)
    return rings


def local_meters(ring: list[list[float]]) -> list[tuple[float, float]]:
    lat0 = math.radians(sum(p[1] for p in ring) / len(ring))
    kx = 111320.0 * math.cos(lat0)
    ky = 110540.0
    return [(p[0] * kx, p[1] * ky) for p in ring]


def ring_acres(ring: list[list[float]]) -> float:
    pts = local_meters(ring)
    area = 0.0
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0 / 4046.86


def simplify(ring: list[list[float]], tol_m: float) -> list[list[float]]:
    """Douglas-Peucker in local meters; keeps ring closure."""
    pts = local_meters(ring)

    def dp(idx0: int, idx1: int, keep: set[int]) -> None:
        if idx1 <= idx0 + 1:
            return
        (x0, y0), (x1, y1) = pts[idx0], pts[idx1]
        dx, dy = x1 - x0, y1 - y0
        norm = math.hypot(dx, dy) or 1e-9
        best, best_i = -1.0, -1
        for i in range(idx0 + 1, idx1):
            px, py = pts[i]
            d = abs(dx * (y0 - py) - dy * (x0 - px)) / norm
            if d > best:
                best, best_i = d, i
        if best > tol_m:
            keep.add(best_i)
            dp(idx0, best_i, keep)
            dp(best_i, idx1, keep)

    # Closed rings (first == last) have a degenerate anchor line; split at
    # the point farthest from the start so DP has two real arcs.
    last = len(ring) - 1
    keep = {0, last}
    if ring[0] == ring[-1]:
        far = max(
            range(1, last),
            key=lambda i: (pts[i][0] - pts[0][0]) ** 2 + (pts[i][1] - pts[0][1]) ** 2,
        )
        keep.add(far)
        dp(0, far, keep)
        dp(far, last, keep)
    else:
        dp(0, last, keep)
    out = [ring[i] for i in sorted(keep)]
    return [[round(lon, 5), round(lat, 5)] for lon, lat in out]


def centroid(ring: list[list[float]]) -> tuple[float, float]:
    return (
        sum(p[1] for p in ring) / len(ring),
        sum(p[0] for p in ring) / len(ring),
    )


def dist_m(a: tuple[float, float], b: list[float]) -> float:
    kx = 111320.0 * math.cos(math.radians(a[0]))
    return math.hypot((a[0] - b[0]) * 110540.0, (a[1] - b[1]) * kx)


# A candidate polygon whose NEAREST VERTEX is farther than this from the
# zone's `near` point is a different place that happens to share the name
# (e.g. a second "Dog Park"). Vertex distance, not centroid — a large
# park's centroid can sit kilometers from its own boundary.
MAX_MATCH_DIST_M = 1000.0


def min_vertex_dist(rings: list[list[list[float]]], near: list[float]) -> float:
    a = (near[0], near[1])
    return min(dist_m(a, [p[1], p[0]]) for r in rings for p in r)


def circle_ring(lat: float, lng: float, radius_m: float, n: int = 24) -> list[list[float]]:
    kx = 111320.0 * math.cos(math.radians(lat))
    ring = [
        [
            round(lng + radius_m * math.cos(2 * math.pi * i / n) / kx, 5),
            round(lat + radius_m * math.sin(2 * math.pi * i / n) / 110540.0, 5),
        ]
        for i in range(n)
    ]
    return ring + [ring[0]]


# --- main -------------------------------------------------------------------

def line_miles(line: list[list[float]]) -> float:
    pts = local_meters(line)
    return sum(
        math.hypot(x2 - x1, y2 - y1) for (x1, y1), (x2, y2) in zip(pts, pts[1:])
    ) / 1609.34


def point_in_ring(lng: float, lat: float, ring: list[list[float]]) -> bool:
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > lat) != (yj > lat) and lng < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def trail_features(spec: dict, zone_features: list[dict]) -> list[dict]:
    """Fetch dog-allowed trail lines (paved network + named forest paths),
    excluding trails inside no-dog state-park polygons, grouped by trail
    name into one MultiLineString feature each."""
    cfg = spec.get("trails")
    if not cfg:
        return []
    lat, lng = cfg["center"]
    r = cfg["radius_m"]
    query = (
        f"[out:json][timeout:120];\n"
        f"(\n"
        f'  way(around:{r},{lat},{lng})["highway"="cycleway"];\n'
        f'  way(around:{r},{lat},{lng})["highway"="path"]["name"];\n'
        f");\n"
        f"out geom;"
    )
    print("fetching trail lines from Overpass…")
    result = overpass(query)

    # State-park polygons already fetched above — trails inside them are
    # dropped (dogs banned on unpaved state-park trails).
    exclude_rings: list[list[list[float]]] = []
    for zf in zone_features:
        if zf["properties"]["id"] in cfg.get("exclude_zone_ids", []):
            g = zf["geometry"]
            exclude_rings += (
                [g["coordinates"][0]]
                if g["type"] == "Polygon"
                else [poly[0] for poly in g["coordinates"]]
            )

    def excluded(way_geom: list[dict]) -> bool:
        mid = way_geom[len(way_geom) // 2]
        return any(point_in_ring(mid["lon"], mid["lat"], r_) for r_ in exclude_rings)

    classes = {c["selector"]: c for c in cfg["classes"]}
    groups: dict[tuple[str, str], list[list[list[float]]]] = {}
    dropped = 0
    for el in result.get("elements", []):
        if el["type"] != "way" or not el.get("geometry"):
            continue
        tags = el.get("tags", {})
        selector = "cycleway" if tags.get("highway") == "cycleway" else "named-path"
        if selector not in classes:
            continue
        if excluded(el["geometry"]):
            dropped += 1
            continue
        name = tags.get("name") or classes[selector]["label"]
        line = simplify([[p["lon"], p["lat"]] for p in el["geometry"]], SIMPLIFY_TOLERANCE_M)
        if len(line) >= 2:
            groups.setdefault((selector, name), []).append(line)
    if dropped:
        print(f"  trails: dropped {dropped} way(s) inside no-dog state-park zones")

    features = []
    by_class_miles: dict[str, float] = {}
    for (selector, name), lines in sorted(groups.items()):
        cls = classes[selector]
        miles = round(sum(line_miles(l) for l in lines), 1)
        by_class_miles[selector] = by_class_miles.get(selector, 0) + miles
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "id": f"trail-{selector}-{name}",
                    "name": name,
                    "kind": "trail",
                    "policy": cls["policy"],
                    "note": cls["note"],
                    "source_url": cls["source_url"],
                    "venue": cls.get("venue"),
                    "acres": None,
                    "miles": miles,
                    "approx": False,
                    "osm": None,
                },
                "geometry": {"type": "MultiLineString", "coordinates": lines},
            }
        )
    for selector, miles in by_class_miles.items():
        print(f"  trails/{selector:12s} {miles:7.1f} mi in {sum(1 for k in groups if k[0]==selector)} named groups")
    return features


def run(slug: str) -> None:
    town_dir = TOWNS_DIR / slug
    spec = yaml.safe_load((town_dir / "zones.yaml").read_text())
    sys.path.insert(0, str(REPO_ROOT / "pipeline"))
    from schemas import require_valid

    require_valid("zones", spec, str(town_dir / "zones.yaml"))
    zones = spec["zones"]

    names = sorted({z["osm_name"] for z in zones})
    center_lat = sum(z["near"][0] for z in zones) / len(zones)
    center_lng = sum(z["near"][1] for z in zones) / len(zones)
    # Overpass regexes are POSIX ERE; escape metacharacters or a zone named
    # "Commons Park (North)" sends an unbalanced paren (HTTP 400) and names
    # with "." or "+" silently over-match and can attach the wrong polygon.
    def _ere_escape(name: str) -> str:
        return re.sub(r'([.^$*+?()\[\]{}|\\"])', r"\\\1", name).replace(" ", "\\ ")

    name_regex = "^(" + "|".join(_ere_escape(n) for n in names) + ")$"
    query = (
        f'[out:json][timeout:120];\n'
        f'wr(around:{SEARCH_RADIUS_M},{center_lat},{center_lng})'
        f'["name"~"{name_regex}"];\n'
        f'out geom;'
    )
    print(f"fetching {len(names)} named polygons from Overpass…")
    result = overpass(query)

    candidates: dict[str, list] = {}
    for el in result.get("elements", []):
        name = el.get("tags", {}).get("name")
        if name:
            candidates.setdefault(name, []).append(el)

    features = []
    for zone in zones:
        options = candidates.get(zone["osm_name"], [])
        best = None
        best_d = float("inf")
        for el in options:
            if el["type"] == "way":
                rings = [r] if (r := ring_from_way(el)) else []
            elif el["type"] == "relation":
                rings = rings_from_relation(el)
            else:
                continue
            if not rings:
                continue
            d = min_vertex_dist(rings, zone["near"])
            if d < best_d:
                best_d, best = d, (el, rings)
        max_match = zone.get("max_match_m", MAX_MATCH_DIST_M)
        if best is not None and best_d > max_match:
            print(
                f"  REJECTED: {zone['id']} — nearest {zone['osm_name']!r} is "
                f"{best_d:.0f} m from `near` (limit {max_match:.0f})"
            )
            best = None
        approx = False
        if best is None:
            radius = zone.get("approx_radius_m")
            if not radius:
                print(f"  MISSING: {zone['id']} (osm_name {zone['osm_name']!r})")
                continue
            rings = [circle_ring(zone["near"][0], zone["near"][1], radius)]
            el, acres, approx = None, None, True
            simplified = rings
            print(f"  {zone['id']:22s} {zone['policy']:10s}    approx circle r={radius}m")
        else:
            el, rings = best
            rings = sorted(rings, key=ring_acres, reverse=True)
            acres = round(sum(ring_acres(r) for r in rings), 2)
            simplified = [simplify(r, SIMPLIFY_TOLERANCE_M) for r in rings]
            print(f"  {zone['id']:22s} {zone['policy']:10s} {acres:9.2f} acres  (osm {el['type']}/{el['id']})")
        geometry = (
            {"type": "Polygon", "coordinates": simplified}
            if len(simplified) == 1
            else {"type": "MultiPolygon", "coordinates": [[r] for r in simplified]}
        )
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "id": zone["id"],
                    "name": zone.get("label") or zone["osm_name"],
                    "policy": zone["policy"],
                    "note": zone["note"],
                    "source_url": zone["source_url"],
                    "venue": zone.get("venue"),
                    "acres": acres,
                    "approx": approx,
                    "osm": f"{el['type']}/{el['id']}" if el else None,
                },
                "geometry": geometry,
            }
        )

    features += trail_features(spec, features)

    out = {
        "type": "FeatureCollection",
        "attribution": "Zone boundaries © OpenStreetMap contributors (ODbL); boundaries approximate",
        "features": features,
    }
    out_file = town_dir / "zones.geojson"
    out_file.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"wrote {out_file} ({out_file.stat().st_size // 1024} KB, {len(features)} zones)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: zones.py <town-slug>")
    run(sys.argv[1])
