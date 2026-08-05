#!/usr/bin/env python3
"""Re-verify venue dog policies older than 90 days and open an update PR.

Usage:
  python pipeline/verify.py                # check all stale venues
  python pipeline/verify.py --max-age 30   # stricter window
  python pipeline/verify.py --dry-run      # report only, no writes/PR

Runs on a GitHub Actions cron (see .github/workflows/verify.yml). For each
stale venue the model re-checks the recorded source (and searches for closure
or policy-change signals). Outcomes:
  unchanged  -> bump verification.last_verified
  changed    -> full updated file proposed
  closed     -> flagged for removal in the PR description
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys
from pathlib import Path

from common import (
    DEFAULT_MODEL,
    REPO_ROOT,
    VENUES_DIR,
    call_model,
    model_engine,
    open_pr,
    split_frontmatter,
    today,
    validate_venue_file,
)

VERDICT_RE = re.compile(r"===VERDICT:\s*(?P<verdict>unchanged|changed|closed)\s*===")
FILE_RE = re.compile(r"===FILE===\n(?P<body>.*?)\n===END FILE===", re.DOTALL)

SYSTEM = """You re-verify dog policies for a published city guide.

You are given the current published venue file. Re-check the dog policy
against the venue's official website (start with verification.source_url,
then search for the venue's current official pages). Also check for signs the
venue has permanently closed.

Respond with exactly one verdict marker:
===VERDICT: unchanged===   (policy matches what's published)
===VERDICT: changed===     (policy differs, or source moved)
===VERDICT: closed===      (venue appears permanently closed)

For `unchanged`: nothing else needed.
For `changed`: also output the FULL corrected file between ===FILE=== and
===END FILE=== — same frontmatter schema, updated policy/body text, and
verification.last_verified set to today. Only change what the sources
support; do not invent facts.
For `closed`: briefly state the evidence after the verdict marker.

Tier note: if the file has verification.level: reported (visitor-reported,
no official source), FIRST search for a newly published official policy. If
one now exists, that's a `changed` verdict — upgrade the file to
verification.level: official with the official source_url and adjust the
body's evidential language. Otherwise re-check that the recorded mention
links still stand; if the venue now officially disallows dogs, that's also
`changed`.
"""


def is_stale(path: Path, max_age_days: int) -> tuple[bool, dict]:
    data, _ = split_frontmatter(path.read_text())
    last = data.get("verification", {}).get("last_verified")
    if isinstance(last, dt.datetime):
        last = last.date()
    if not isinstance(last, dt.date):
        return True, data  # unparseable -> treat as stale
    return (dt.date.today() - last).days > max_age_days, data


def reverify(model: str, path: Path) -> tuple[str, str | None, str]:
    """Returns (verdict, new_content|None, raw_text)."""
    prompt = (
        f"Today's date: {today()}\n\n"
        f"Current published file ({path.relative_to(REPO_ROOT)}):\n\n"
        f"{path.read_text()}"
    )
    text = call_model(SYSTEM, prompt, model, max_tokens=16000)
    vm = VERDICT_RE.search(text)
    verdict = vm.group("verdict") if vm else "changed"  # unclear -> human review
    fm = FILE_RE.search(text)
    return verdict, (fm.group("body") if fm else None), text


def bump_verified_date(path: Path) -> None:
    text = path.read_text()
    updated = re.sub(
        r"(last_verified:\s*)[\d-]+",
        rf"\g<1>{today()}",
        text,
        count=1,
    )
    path.write_text(updated)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-age", type=int, default=90)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--model", default=os.environ.get("MODEL", DEFAULT_MODEL))
    args = parser.parse_args()

    stale = []
    for path in sorted(VENUES_DIR.glob("*/*.md")):
        try:
            needs_check, _ = is_stale(path, args.max_age)
        except ValueError as exc:
            print(f"WARNING {path}: {exc}")
            continue
        if needs_check:
            stale.append(path)

    if not stale:
        print(f"No venues older than {args.max_age} days. Done.")
        return 0
    print(f"{len(stale)} venue(s) need re-verification.")

    if args.dry_run:
        for p in stale:
            print(f"  stale: {p.relative_to(REPO_ROOT)}")
        return 0

    from ledger import CHECKS_FILE, record_check

    print(f"Engine: {model_engine()}")
    touched: list[Path] = []
    report: list[str] = []

    for path in stale:
        rel = path.relative_to(REPO_ROOT)
        print(f"\n=== Re-verifying {rel} ===")
        verdict, new_content, raw = reverify(args.model, path)
        record_check(path.parent.name, path.stem, "verify", verdict, str(rel))
        print(f"  verdict: {verdict}")
        if verdict == "unchanged":
            bump_verified_date(path)
            touched.append(path)
            report.append(f"- ✅ `{rel}` — unchanged, verification date bumped")
        elif verdict == "changed" and new_content:
            problems = validate_venue_file(new_content)
            if problems:
                report.append(f"- ⚠️ `{rel}` — change detected but draft invalid: {'; '.join(problems)}")
            else:
                path.write_text(new_content)
                touched.append(path)
                report.append(f"- ✏️ `{rel}` — **policy changed**, updated file proposed")
        elif verdict == "closed":
            evidence = raw.split("===", 3)[-1].strip()[:300]
            report.append(f"- 🚫 `{rel}` — **appears permanently closed**; remove after confirming. {evidence}")
        else:
            report.append(f"- ⚠️ `{rel}` — needs manual review (model output unclear)")

    if not touched:
        print("\nNo file changes; report:")
        print("\n".join(report))
        return 0

    branch = f"verify/recheck-{today()}"
    body = (
        "Scheduled 90-day re-verification. **Merging this PR is the approval step.**\n\n"
        + "\n".join(report)
    )
    files = touched + ([CHECKS_FILE] if CHECKS_FILE.exists() else [])
    open_pr(branch, f"verify: re-checked {len(stale)} stale venue(s)", body, files)
    return 0


if __name__ == "__main__":
    sys.exit(main())
