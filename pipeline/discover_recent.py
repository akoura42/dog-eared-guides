#!/usr/bin/env python3
"""Third discovery layer: model-driven sweep for RECENT openings.

Bulk datasets lag reality — OSM by years for businesses, Overture by
months (evo Hotel Tahoe City opened Sept 2025 and was still absent from
both in Aug 2026). This sweep has the model research venues that opened,
rebranded, or changed hands recently and writes them as PENDING QUEUE
ROWS (not ledger rows): each is a lead with sources, and the normal
generate.py run does the actual policy verification.

Usage:
  python pipeline/discover_recent.py --city tahoe-city [--months 18] [--dry-run]

Dedup: a lead whose name matches an existing ledger row or queue item is
dropped. Everything else lands in pipeline/queue/<city>.yaml with the
model's evidence in notes.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import yaml

from common import DEFAULT_MODEL, REPO_ROOT, call_model
from discover import city_config
from ledger import load_city, norm_name

QUEUE_DIR = REPO_ROOT / "pipeline" / "queue"

SYSTEM = """You research newly opened venues for a dog-friendly city guide.
Output ONLY a fenced yaml block containing a list. Each entry:
  name: <venue name>
  category: eat | drink | stay | trail | beach | activity | dog-park | shop | pet-supply | daycare | services
  opened: <what you can tell about when it opened/rebranded, with year>
  address: <street address if known>
  evidence: <the URLs (space-separated) where you learned this — press,
    the venue's own site, local news. REQUIRED; no URL, no entry.>
  dog_signal: <anything found about a dog/pet policy, or "none found">
Only venues you have actual evidence opened, reopened, rebranded, or
changed hands within the window. No inference, no filler. An empty list
([]) is a valid answer."""


def prompt_for(city_cfg: dict, months: int) -> str:
    return (
        f"City: {city_cfg['name']}, {city_cfg['state']} (around "
        f"{city_cfg['geo']['lat']}, {city_cfg['geo']['lng']}).\n"
        f"Find venues (restaurants, bars, lodging, cafes, pet businesses, "
        f"activity outfitters) that OPENED, REOPENED, REBRANDED, or CHANGED "
        f"HANDS in the last {months} months. Use web search: local news, "
        f"'now open' coverage, chamber/visitor-bureau announcements, the "
        f"venues' own sites. Return the yaml list."
    )


def parse_leads(text: str) -> list[dict]:
    m = re.search(r"```(?:yaml)?\n(.*?)```", text, re.DOTALL)
    if not m:
        return []
    leads = yaml.safe_load(m.group(1)) or []
    return [l for l in leads if isinstance(l, dict) and l.get("name") and l.get("evidence")]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--city", required=True)
    parser.add_argument("--months", type=int, default=18)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--model", default=os.environ.get("MODEL", DEFAULT_MODEL))
    args = parser.parse_args()

    cfg = city_config(args.city)
    print(f"{args.city}: researching openings in the last {args.months} months…")
    leads = parse_leads(call_model(SYSTEM, prompt_for(cfg, args.months), args.model))
    print(f"  {len(leads)} sourced lead(s)")

    known = {norm_name(r["name"]) for r in load_city(args.city).values()}
    queue_path = QUEUE_DIR / f"{args.city}.yaml"
    doc = yaml.safe_load(queue_path.read_text()) if queue_path.exists() else {"items": []}
    known |= {norm_name(i.get("name") or "") for i in doc.get("items", [])}

    fresh = [l for l in leads if norm_name(l["name"]) not in known]
    for l in fresh:
        cat = l.get("category")
        item = {
            "type": "venue",
            "city": args.city,
            "name": l["name"],
            "notes": (
                f"RECENT OPENING ({l.get('opened', 'window unknown')}). "
                f"{l.get('address', '')}. Dog signal: {l.get('dog_signal', 'none found')}. "
                f"Sources: {l.get('evidence')}"
            ).strip(),
        }
        if cat and isinstance(cat, str):
            item["category"] = cat
        doc.setdefault("items", []).append(item)
        print(f"  + {l['name']} ({cat or '?'})")
    for l in leads:
        if norm_name(l["name"]) in known and l not in fresh:
            print(f"  = {l['name']} (already tracked)")

    if args.dry_run:
        print(f"{args.city}: would queue {len(fresh)} lead(s) (dry run)")
        return 0
    if fresh:
        from generate import save_queue

        save_queue(queue_path, doc)
    print(f"{args.city}: queued {len(fresh)} lead(s) -> {queue_path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
