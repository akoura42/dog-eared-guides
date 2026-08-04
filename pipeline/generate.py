#!/usr/bin/env python3
"""Draft venue/guide content from the work queue and open a PR.

Usage:
  python pipeline/generate.py                 # process pending queue items
  python pipeline/generate.py --limit 3       # first 3 pending items
  python pipeline/generate.py --dry-run       # write files, no branch/PR

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

import anthropic
import yaml

from common import (
    CONTENT_DIR,
    DEFAULT_MODEL,
    REPO_ROOT,
    WEB_TOOLS,
    GenerationResult,
    existing_venue_slugs,
    few_shot_examples,
    load_prompt,
    open_pr,
    parse_generation_output,
    recent_editorial_log,
    today,
    validate_venue_file,
)

QUEUE_FILE = REPO_ROOT / "pipeline" / "queue.yaml"
MAX_PAUSE_TURN_CONTINUATIONS = 5


def build_system_prompt() -> str:
    parts = [load_prompt("SYSTEM.md"), "\n\n# STYLE GUIDE\n\n" + load_prompt("STYLE_GUIDE.md")]
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


def generate_item(client: anthropic.Anthropic, model: str, item: dict) -> GenerationResult:
    system = build_system_prompt()
    messages: list[dict] = [{"role": "user", "content": build_user_prompt(item)}]

    for _ in range(MAX_PAUSE_TURN_CONTINUATIONS + 1):
        with client.messages.stream(
            model=model,
            max_tokens=32000,
            system=system,
            tools=WEB_TOOLS,
            messages=messages,
        ) as stream:
            response = stream.get_final_message()
        if response.stop_reason == "refusal":
            raise RuntimeError(f"model refused work item: {item}")
        if response.stop_reason == "pause_turn":
            # Server-side tool loop paused; re-send to resume.
            messages = [messages[0], {"role": "assistant", "content": response.content}]
            continue
        break
    else:
        raise RuntimeError("still paused after max continuations")

    text = "".join(b.text for b in response.content if b.type == "text")
    return parse_generation_output(text)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--model", default=os.environ.get("MODEL", DEFAULT_MODEL))
    args = parser.parse_args()

    queue = yaml.safe_load(QUEUE_FILE.read_text()) or {}
    items = [i for i in queue.get("items", []) if not i.get("done")]
    if args.limit:
        items = items[: args.limit]
    if not items:
        print("Queue is empty — nothing to generate.")
        return 0

    client = anthropic.Anthropic()
    written: list[Path] = []
    all_questions: list[str] = []
    titles: list[str] = []

    for item in items:
        label = item.get("name") or item.get("topic")
        print(f"\n=== Generating: {label} ===")
        result = generate_item(client, args.model, item)
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
    open_pr(branch, f"content: {len(written)} drafted page(s) for review", body, written)
    return 0


if __name__ == "__main__":
    sys.exit(main())
