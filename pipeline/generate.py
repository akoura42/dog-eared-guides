#!/usr/bin/env python3
"""Draft venue/guide content from the work queue (or ledger) and open a PR.

Usage:
  python pipeline/generate.py                 # process pending queue items
  python pipeline/generate.py --limit 3       # first 3 pending items
  python pipeline/generate.py --dry-run       # write files, no branch/PR
  python pipeline/generate.py --from-ledger tahoe-city --limit 5
                                              # pull unchecked ledger candidates
  python pipeline/generate.py --from-ledger tahoe-city --list-only
                                              # show what would be selected

Reads pipeline/queue.yaml. Every dog-policy fact must be verified by the
model against an official source (web search/fetch tools are enabled and the
system prompt requires citations); anything unverifiable lands in the PR
description as an open question. Sign-off = PR merge. Never commits to main.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import yaml

from common import (
    CONTENT_DIR,
    DEFAULT_MODEL,
    REPO_ROOT,
    VOICE_FILE,
    GenerationResult,
    call_model,
    existing_venue_slugs,
    few_shot_examples,
    load_prompt,
    model_engine,
    open_pr,
    parse_generation_output,
    recent_editorial_log,
    today,
    validate_venue_file,
)

QUEUE_FILE = REPO_ROOT / "pipeline" / "queue.yaml"


def build_system_prompt() -> str:
    parts = [load_prompt("SYSTEM.md"), "\n\n# STYLE GUIDE\n\n" + load_prompt("STYLE_GUIDE.md")]
    # House voice — injected into every generation prompt per docs/voice.md.
    # It governs how copy sounds; it never overrides sourcing rules.
    if VOICE_FILE.exists():
        parts.append("\n\n# HOUSE VOICE (binding)\n\n" + VOICE_FILE.read_text())
    log = recent_editorial_log()
    if log:
        parts.append("\n\n# RECENT EDITORIAL CORRECTIONS (binding)\n\n" + log)
    return "".join(parts)


def build_user_prompt(item: dict) -> str:
    city = item["city"]
    slugs = existing_venue_slugs(city)
    common = (
        f"Today's date: {today()}\n"
        f"City: {city}\n"
        f"Existing venue slugs in this city (valid VenueEmbed targets): {', '.join(slugs) or '(none)'}\n\n"
        f"# APPROVED EXAMPLES\n\n{few_shot_examples(city)}\n\n"
    )
    if item["type"] == "venue":
        return common + (
            f"Work item: draft ONE venue page.\n"
            f"Venue: {item['name']}\n"
            f"Category: {item.get('category', 'unknown — determine and set correctly')}\n"
            f"Notes from the queue: {item.get('notes', 'none')}\n\n"
            "Research the venue's official website / official social pages with your "
            "web tools, verify the dog policy, and produce the file at "
            f"venues/{city}/<venue-slug>.md per the output contract. "
            "If the dog policy cannot be verified on an official source, produce no "
            "file and list the venue under OPEN QUESTIONS with what you found."
        )
    return common + (
        f"Work item: draft ONE long-form guide (1,200-2,500 words, MDX).\n"
        f"Topic: {item['topic']}\n"
        f"Notes from the queue: {item.get('notes', 'none')}\n\n"
        "Verify every rule/policy claim against the enforcing agency's official "
        "pages with your web tools. Embed existing venues with <VenueEmbed/> where "
        f"relevant. Produce the file at guides/{city}/<guide-slug>.mdx per the "
        "output contract."
    )


def generate_item(model: str, item: dict) -> GenerationResult:
    text = call_model(build_system_prompt(), build_user_prompt(item), model)
    return parse_generation_output(text)


def ledger_items(city: str, limit: int) -> list[dict]:
    """Turn unchecked/queued ledger candidates into venue work items."""
    from ledger import next_candidates

    items = []
    for row in next_candidates(city, limit):
        notes = [f"Ledger candidate ({row['status']}, source: {row['source']}, id: {row['id']})."]
        if row.get("note"):
            notes.append(row["note"])
        if row.get("lat") is not None:
            notes.append(f"Approx location: {row['lat']}, {row['lng']}.")
        items.append(
            {
                "type": "venue",
                "city": city,
                "name": row["name"],
                "category": row.get("category"),
                "notes": " ".join(notes),
                "_ledger_id": row["id"],
            }
        )
    return items


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--from-ledger", metavar="CITY", default=None)
    parser.add_argument("--list-only", action="store_true")
    parser.add_argument("--model", default=os.environ.get("MODEL", DEFAULT_MODEL))
    args = parser.parse_args()

    if args.from_ledger:
        items = ledger_items(args.from_ledger, args.limit or 5)
        if args.list_only:
            for item in items:
                print(f"{item['_ledger_id']:45} {item.get('category') or '?':10} {item['name']}")
            print(f"({len(items)} candidates selected)")
            return 0
    else:
        queue = yaml.safe_load(QUEUE_FILE.read_text()) or {}
        items = [i for i in queue.get("items", []) if not i.get("done")]
        if args.limit:
            items = items[: args.limit]
    if not items:
        print("Nothing to generate.")
        return 0

    print(f"Engine: {model_engine()}")
    written: list[Path] = []
    all_questions: list[str] = []
    titles: list[str] = []
    ledger_outcomes: list[tuple[dict, bool]] = []  # (item, produced_a_file)

    for item in items:
        label = item.get("name") or item.get("topic")
        print(f"\n=== Generating: {label} ===", flush=True)
        try:
            result = generate_item(args.model, item)
        except RuntimeError as exc:
            # One failed item (timeout, rate limit, refusal) must not kill
            # the batch. Leave its ledger status untouched for a retry.
            print(f"  ERRORED: {exc}", flush=True)
            all_questions.append(f"{label}: generation errored ({exc}) — item left for retry")
            continue
        all_questions.extend(result.open_questions)

        for gen in result.files:
            target = (CONTENT_DIR / gen.rel_path).resolve()
            if CONTENT_DIR.resolve() not in target.parents:
                print(f"  REJECTED path outside src/content/: {gen.rel_path}")
                continue
            if gen.rel_path.startswith("venues/"):
                problems = validate_venue_file(gen.content)
                if problems:
                    print(f"  REJECTED {gen.rel_path}:")
                    for p in problems:
                        print(f"    - {p}")
                    all_questions.append(f"{label}: draft rejected ({'; '.join(problems)})")
                    continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(gen.content)
            written.append(target)
            titles.append(label)
            print(f"  wrote {target.relative_to(REPO_ROOT)}")

        if not result.files:
            print("  no file produced (unverifiable — see open questions)")
        if item.get("_ledger_id"):
            ledger_outcomes.append((item, bool(result.files)))

    # Ledger bookkeeping: published candidates flip via sync; the rest are
    # recorded as unverifiable so they aren't re-selected next run.
    ledger_paths: list[Path] = []
    if args.from_ledger and ledger_outcomes:
        from ledger import CHECKS_FILE, city_file, load_city, record_check, save_city, sync_published

        places = load_city(args.from_ledger)
        for item, produced in ledger_outcomes:
            pid = item["_ledger_id"]
            outcome = "draft-produced" if produced else "unverifiable"
            if not produced and pid in places:
                places[pid]["status"] = "unverifiable"
                places[pid]["note"] = (
                    "Generation run found no publishable evidence — see the PR's open questions."
                )
                places[pid]["last_checked"] = today()
            record_check(args.from_ledger, pid, "generate", outcome, item["name"])
        save_city(args.from_ledger, places)
        sync_published()
        ledger_paths = [city_file(args.from_ledger), CHECKS_FILE]

    if not written:
        print("\nNothing verifiable was produced. Open questions:")
        for q in all_questions:
            print(f"  - {q}")
        return 1

    if args.dry_run:
        print("\n--dry-run: files written, skipping branch/PR.")
        return 0

    branch = f"content/generate-{today()}-{os.getpid()}"
    question_md = "\n".join(f"- [ ] {q}" for q in all_questions) or "_none_"
    body = (
        f"AI-drafted content for review. **Merging this PR is the approval step.**\n\n"
        f"Items: {', '.join(dict.fromkeys(titles))}\n\n"
        f"## Open questions (unverified — resolve before or note in review)\n{question_md}\n\n"
        "Every dog-policy fact in these files carries a `verification.source_url`. "
        "Corrections you make during review should get a one-line entry in "
        "`pipeline/prompts/EDITORIAL_LOG.md` so future drafts improve."
    )
    open_pr(
        branch,
        f"content: {len(written)} drafted page(s) for review",
        body,
        written + [p for p in ledger_paths if p.exists()],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
