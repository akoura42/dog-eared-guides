#!/usr/bin/env python3
"""Research ledger: the pipeline's memory of every known place per city.

Published venue pages (git-reviewed markdown) remain the site's source of
truth. The ledger tracks everything AROUND them: candidates not yet
checked, places that failed verification (and why), verified no-dogs
venues we shouldn't re-research, closures, and a check history.

Storage is JSONL per city (pipeline/ledger/<city>.jsonl, one place per
line, sorted by id) plus an append-only checks log — deliberately not a
binary database, so ledger changes are reviewable in PR diffs like
everything else. At hundreds-of-rows-per-city scale, Python filters are
all the query engine this needs.

Statuses:
  unchecked          discovered, never researched
  queued             selected for the next generation batch
  published-official live on the site, tier-1 verification
  published-reported live on the site, tier-2 (visitor-reported)
  unverifiable       researched; evidence missing or conflicting (note says why)
  rejected-no-dogs   verified NOT dog-friendly (worth remembering!)
  closed             permanently closed / nonexistent
  duplicate          same place as another row (note points to it)

CLI:
  python pipeline/ledger.py stats [--city tahoe-city]
  python pipeline/ledger.py list --city tahoe-city [--status unchecked]
  python pipeline/ledger.py set-status --city tahoe-city --id X --status Y [--note ...]
  python pipeline/ledger.py sync            # reconcile with published venue files
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

from common import REPO_ROOT, VENUES_DIR, split_frontmatter, today

LEDGER_DIR = REPO_ROOT / "pipeline" / "ledger"
# Check log is sharded per city (like the place ledgers): a single global
# append-only file guarantees line-level merge conflicts the moment two
# city branches are in flight.
CHECKS_DIR = LEDGER_DIR / "checks"

STATUSES = {
    "unchecked",
    "queued",
    "published-official",
    "published-reported",
    "unverifiable",
    "rejected-no-dogs",
    "closed",
    "duplicate",
}


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "unnamed"


def norm_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def city_file(city: str) -> Path:
    return LEDGER_DIR / f"{city}.jsonl"


def checks_file(city: str) -> Path:
    return CHECKS_DIR / f"{city}.jsonl"


def load_city(city: str) -> dict[str, dict]:
    path = city_file(city)
    if not path.exists():
        return {}
    places: dict[str, dict] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        places[row["id"]] = row
    return places


def save_city(city: str, places: dict[str, dict]) -> Path:
    from schemas import require_valid

    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    path = city_file(city)
    for pid in places:
        require_valid("ledger-place", places[pid], f"{path.name} id={pid}")
    lines = [
        json.dumps(places[pid], ensure_ascii=False, sort_keys=True)
        for pid in sorted(places)
    ]
    path.write_text("\n".join(lines) + "\n" if lines else "")
    return path


def ledger_cities() -> list[str]:
    if not LEDGER_DIR.is_dir():
        return []
    return sorted(p.stem for p in LEDGER_DIR.glob("*.jsonl"))


def upsert_place(
    places: dict[str, dict],
    *,
    pid: str,
    name: str,
    city: str,
    category: str | None = None,
    status: str = "unchecked",
    note: str | None = None,
    source: str = "manual",
    lat: float | None = None,
    lng: float | None = None,
    evidence: list[str] | None = None,
    osm_ref: str | None = None,
    overture_id: str | None = None,
) -> dict:
    """Insert or update; never downgrades a researched status to unchecked."""
    assert status in STATUSES, f"unknown status: {status}"
    existing = places.get(pid)
    if existing:
        if status != "unchecked":
            existing["status"] = status
            if note:
                existing["note"] = note
        existing.setdefault("category", category)
        if lat is not None:
            existing.setdefault("lat", lat)
            existing.setdefault("lng", lng)
        if evidence:
            merged = list(dict.fromkeys([*existing.get("evidence", []), *evidence]))
            existing["evidence"] = merged
        if osm_ref:
            existing.setdefault("osm_ref", osm_ref)
        if overture_id:
            existing.setdefault("overture_id", overture_id)
        return existing
    row = {
        "id": pid,
        "name": name,
        "city": city,
        "category": category,
        "status": status,
        "note": note,
        "source": source,
        "first_seen": today(),
        "last_checked": today() if status != "unchecked" else None,
    }
    if lat is not None:
        row["lat"], row["lng"] = lat, lng
    if evidence:
        row["evidence"] = evidence
    if osm_ref:
        row["osm_ref"] = osm_ref
    if overture_id:
        row["overture_id"] = overture_id
    places[pid] = row
    return row


def record_check(city: str, place_id: str, actor: str, outcome: str, note: str = "") -> None:
    from schemas import require_valid

    CHECKS_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "city": city,
        "place_id": place_id,
        "actor": actor,
        "outcome": outcome,
        "note": note,
    }
    require_valid("check-entry", entry, f"checks/{city}.jsonl")
    with checks_file(city).open("a") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")


def next_candidates(city: str, limit: int, statuses: tuple[str, ...] = ("queued", "unchecked")) -> list[dict]:
    """Work selection: queued first, then unchecked; stable order by id."""
    places = load_city(city)
    picked: list[dict] = []
    for status in statuses:
        for pid in sorted(places):
            row = places[pid]
            if row["status"] == status:
                picked.append(row)
                if len(picked) >= limit:
                    return picked
    return picked


def sync_published() -> dict[str, int]:
    """Reconcile ledger rows with published venue files (the ground truth)."""
    counts: dict[str, int] = {}
    for city_dir in sorted(VENUES_DIR.glob("*")):
        if not city_dir.is_dir():
            continue
        city = city_dir.name
        places = load_city(city)
        # Name-based re-pointing is only safe when the name is UNAMBIGUOUS:
        # with two same-name rows (chain stores), attaching published state
        # to "whichever the dict kept" silently corrupts the other store's
        # identity. Ambiguous names get a fresh row keyed by the md stem.
        name_counts: dict[str, int] = {}
        for r in places.values():
            key = norm_name(r["name"])
            name_counts[key] = name_counts.get(key, 0) + 1
        by_name = {
            norm_name(r["name"]): pid
            for pid, r in places.items()
            if name_counts[norm_name(r["name"])] == 1
        }
        for md in sorted(city_dir.glob("*.md")):
            # One malformed hand-edited file must not abort the sync for
            # every other city — and sync runs at the tail of generate.py,
            # after the model spend.
            try:
                data, _ = split_frontmatter(md.read_text())
                name = data["name"]
            except (ValueError, KeyError) as exc:
                print(f"WARNING sync_published: skipping {md}: {exc}")
                continue
            level = (data.get("verification") or {}).get("level", "official")
            status = "published-reported" if level == "reported" else "published-official"
            last = (data.get("verification") or {}).get("last_verified")
            # If a candidate row already tracks this place under another id
            # (e.g. an osm- row that just got published), update that row
            # rather than creating a duplicate.
            pid = md.stem
            if pid not in places and norm_name(data["name"]) in by_name:
                pid = by_name[norm_name(data["name"])]
            row = upsert_place(
                places,
                pid=pid,
                name=data["name"],
                city=city,
                category=data.get("category"),
                status=status,
                source="site",
                lat=data.get("lat"),
                lng=data.get("lng"),
            )
            row["published_slug"] = md.stem
            row["last_checked"] = str(last)[:10] if last else today()
            by_name[norm_name(data["name"])] = pid
            counts[city] = counts.get(city, 0) + 1
        save_city(city, places)
    return counts


def stats(city: str | None = None) -> None:
    cities = [city] if city else ledger_cities()
    for c in cities:
        places = load_city(c)
        by_status: dict[str, int] = {}
        for row in places.values():
            by_status[row["status"]] = by_status.get(row["status"], 0) + 1
        summary = ", ".join(f"{k}: {v}" for k, v in sorted(by_status.items()))
        print(f"{c}: {len(places)} places ({summary})")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_stats = sub.add_parser("stats")
    p_stats.add_argument("--city")

    p_list = sub.add_parser("list")
    p_list.add_argument("--city", required=True)
    p_list.add_argument("--status")

    p_set = sub.add_parser("set-status")
    p_set.add_argument("--city", required=True)
    p_set.add_argument("--id", required=True)
    p_set.add_argument("--status", required=True, choices=sorted(STATUSES))
    p_set.add_argument("--note", default=None)

    sub.add_parser("sync")

    args = parser.parse_args()
    if args.cmd == "stats":
        stats(args.city)
    elif args.cmd == "list":
        places = load_city(args.city)
        for pid in sorted(places):
            row = places[pid]
            if args.status and row["status"] != args.status:
                continue
            print(f"{row['status']:20} {pid:40} {row['name']}")
    elif args.cmd == "set-status":
        places = load_city(args.city)
        if args.id not in places:
            print(f"no such place: {args.id}", file=sys.stderr)
            return 1
        places[args.id]["status"] = args.status
        places[args.id]["last_checked"] = today()
        if args.note:
            places[args.id]["note"] = args.note
        save_city(args.city, places)
        record_check(args.city, args.id, "manual", args.status, args.note or "")
        print(f"{args.id} -> {args.status}")
    elif args.cmd == "sync":
        counts = sync_published()
        for c, n in sorted(counts.items()):
            print(f"synced {n} published venues for {c}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
