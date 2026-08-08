#!/usr/bin/env python3
"""Draft venue/guide content from the work queue (or ledger) and open a PR.

Usage:
  python pipeline/generate.py                 # all cities' pending queue items
  python pipeline/generate.py --city charlotte --limit 3
  python pipeline/generate.py --dry-run       # write files, no branch/PR
  python pipeline/generate.py --from-ledger tahoe-city --limit 5
                                              # pull unchecked ledger candidates
  python pipeline/generate.py --from-ledger tahoe-city --list-only
                                              # show what would be selected

Reads pipeline/queue/<city>.yaml (one queue per city) and writes done
markers back after each run — a processed item is never re-drafted. Every
dog-policy fact must be verified by the model against an official source
(web search/fetch tools are enabled and the system prompt requires
citations); anything unverifiable lands in the PR description as an open
question. Sign-off = PR merge. Never commits to main.
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

# Work queues are sharded per city (pipeline/queue/<city>.yaml) so two
# city batches in flight never conflict on one file, and completed items
# are written back automatically instead of hand-marked.
QUEUE_DIR = REPO_ROOT / "pipeline" / "queue"


def load_queues(city: str | None) -> list[tuple[Path, dict]]:
    """Load per-city queue files; a specific city or all of them."""
    if not QUEUE_DIR.is_dir():
        return []
    paths = [QUEUE_DIR / f"{city}.yaml"] if city else sorted(QUEUE_DIR.glob("*.yaml"))
    queues = []
    for path in paths:
        if not path.exists():
            raise SystemExit(f"no queue file: {path}")
        queues.append((path, yaml.safe_load(path.read_text()) or {}))
    return queues


def save_queue(path: Path, doc: dict) -> None:
    from schemas import require_valid

    # Strip runtime-only keys (e.g. _queue_path) — they must never serialize.
    clean = dict(doc)
    clean["items"] = [
        {k: v for k, v in item.items() if not k.startswith("_")}
        for item in doc.get("items", [])
    ]
    for i, item in enumerate(clean["items"]):
        require_valid("queue-item", item, f"{path.name} items[{i}]")
    path.write_text(yaml.safe_dump(clean, sort_keys=False, allow_unicode=True))


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
    parser.add_argument("--city", default=None, help="work only this city's queue file")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--from-ledger", metavar="CITY", default=None)
    parser.add_argument("--list-only", action="store_true")
    parser.add_argument(
        "--parallel",
        type=int,
        default=1,
        metavar="N",
        help="concurrent generation calls (2-3 recommended; the ceiling is "
        "the Claude subscription's usage window, not this machine)",
    )
    parser.add_argument("--model", default=os.environ.get("MODEL", DEFAULT_MODEL))
    args = parser.parse_args()

    if args.from_ledger:
        items = ledger_items(args.from_ledger, args.limit or 5)
        if args.list_only:
            for item in items:
                print(f"{item['_ledger_id']:45} {item.get('category') or '?':10} {item['name']}")
            print(f"({len(items)} candidates selected)")
            return 0
    queue_docs: dict[Path, dict] = {}
    if not args.from_ledger:
        queue_docs = dict(load_queues(args.city))
        items = []
        for path, doc in queue_docs.items():
            for i in doc.get("items", []):
                if not i.get("done"):
                    i["_queue_path"] = path
                    items.append(i)
        if args.limit is not None:  # --limit 0 selects nothing, not everything
            items = items[: args.limit]
    if not items:
        print("Nothing to generate.")
        return 0

    print(f"Engine: {model_engine()}")
    written: list[Path] = []
    all_questions: list[str] = []
    titles: list[str] = []
    ledger_outcomes: list[tuple[dict, bool]] = []  # (item, produced_a_file)
    queue_outcomes: list[tuple[dict, bool]] = []  # (queue item, produced_a_file)

    def run_one(item: dict) -> tuple[dict, GenerationResult | None, Exception | None]:
        label = item.get("name") or item.get("topic")
        print(f"[start] {label}", flush=True)
        try:
            res = generate_item(args.model, item)
            print(f"[done ] {label}", flush=True)
            return item, res, None
        except Exception as exc:  # noqa: BLE001
            # One failed item (timeout, rate limit, API error, malformed
            # queue row) must not kill the batch — with --parallel an
            # uncaught exception here would discard every other item's
            # finished model output. Leave state untouched for a retry.
            print(f"[error] {label}: {exc}", flush=True)
            return item, None, exc

    if args.parallel > 1:
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=args.parallel) as pool:
            outcomes = list(pool.map(run_one, items))  # order preserved
    else:
        outcomes = [run_one(item) for item in items]

    # Results are processed sequentially so file writes, validation output,
    # and ledger bookkeeping stay deterministic regardless of concurrency.
    for item, result, error in outcomes:
        label = item.get("name") or item.get("topic")
        if error or result is None:
            all_questions.append(f"{label}: generation errored ({error}) — item left for retry")
            continue
        all_questions.extend(result.open_questions)

        wrote_for_item = 0
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
            wrote_for_item += 1
            print(f"  wrote {target.relative_to(REPO_ROOT)}")

        if not result.files:
            print("  no file produced (unverifiable — see open questions)")
        # Three outcomes per item — only what was actually WRITTEN counts:
        #   published    ≥1 file written to disk
        #   unverifiable model produced no file (evidence missing)
        #   rejected     model produced files but validation refused them all
        #                — left pending for retry, never marked done
        if wrote_for_item:
            status = "published"
        elif result.files:
            status = "rejected"
        else:
            status = "unverifiable"
        if item.get("_ledger_id"):
            ledger_outcomes.append((item, status))
        if item.get("_queue_path"):
            queue_outcomes.append((item, status))

    # Ledger bookkeeping: published candidates flip via sync; unverifiable
    # ones are recorded so they aren't re-selected; rejected drafts keep
    # their status for a retry. Dry runs write NO state — a dry run must
    # never consume queue items or flip ledger rows.
    ledger_paths: list[Path] = []
    if not args.dry_run and args.from_ledger and ledger_outcomes:
        from ledger import checks_file, city_file, load_city, record_check, save_city, sync_published

        places = load_city(args.from_ledger)
        for item, status in ledger_outcomes:
            pid = item["_ledger_id"]
            outcome = {"published": "draft-produced", "rejected": "draft-rejected"}.get(
                status, "unverifiable"
            )
            if status == "unverifiable" and pid in places:
                places[pid]["status"] = "unverifiable"
                places[pid]["note"] = (
                    "Generation run found no publishable evidence — see the PR's open questions."
                )
                places[pid]["last_checked"] = today()
            record_check(args.from_ledger, pid, "generate", outcome, item["name"])
        save_city(args.from_ledger, places)
        sync_published()
        ledger_paths = [city_file(args.from_ledger), checks_file(args.from_ledger)]

    # Queue write-back: a processed item is marked done in its city's queue
    # file — re-running generate must never re-draft it. Unverifiable items
    # are done too (the ledger + PR open questions carry the evidence trail);
    # rejected and errored items stay pending for retry.
    queue_paths: list[Path] = []
    if not args.dry_run and queue_outcomes:
        touched = set()
        for item, status in queue_outcomes:
            path = item.pop("_queue_path")  # item is a live ref into queue_docs
            if status == "rejected":
                continue
            item["done"] = True
            item["done_date"] = today()
            if status == "unverifiable":
                item["done_note"] = "unverifiable — see the PR's open questions"
            touched.add(path)
        for path in sorted(touched):
            save_queue(path, queue_docs[path])
            queue_paths.append(path)

    # Open questions carry the research detail behind every non-published
    # outcome — print them in every mode, or that context is lost.
    if all_questions:
        print("\nOpen questions:")
        for q in all_questions:
            print(f"  - {q}")

    if args.dry_run:
        print("\n--dry-run: content files written for inspection; no state or PR.")
        return 0 if written else 1

    bookkeeping = [p for p in [*ledger_paths, *queue_paths] if p.exists()]
    if not written:
        # The run still moved state (unverifiable flips, check log, done
        # markers) — that MUST land in a PR or an ephemeral runner discards
        # it and next run repeats the whole model spend.
        print("\nNothing verifiable was produced.")
        if bookkeeping:
            question_md = "\n".join(f"- [ ] {q}" for q in all_questions) or "_none_"
            open_pr(
                f"content/generate-{today()}-{os.getpid()}",
                "generate: bookkeeping only — no publishable drafts",
                "No drafts survived verification this run; this PR records the "
                "ledger/queue outcomes so the work isn't repeated.\n\n"
                f"## Open questions\n{question_md}",
                bookkeeping,
            )
        return 1

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
        written + bookkeeping,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
