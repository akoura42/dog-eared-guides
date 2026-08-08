#!/usr/bin/env python3
"""Canonical data-format validation (schemas live in data/schema/).

One source of truth for every pipeline-written format: city configs,
Dog-Eared Index values, zone curation, ledger rows, check-log entries,
and queue items. Pipeline writers call validate() before writing; CI runs
`python pipeline/schemas.py --check-all` over every data file so drift is
caught at PR time, not at read time months later.

The web app's Zod schemas (config.ts, content.config.ts) remain the read
gate; these schemas are the WRITE gate. When a format changes, change the
schema file and both sides in one PR.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

try:
    import jsonschema
except ImportError:  # pragma: no cover
    jsonschema = None

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = REPO_ROOT / "data" / "schema"
CITIES_DIR = REPO_ROOT / "data" / "cities"
LEDGER_DIR = REPO_ROOT / "pipeline" / "ledger"
QUEUE_DIR = REPO_ROOT / "pipeline" / "queue"

_cache: dict[str, dict] = {}


def _schema(kind: str) -> dict:
    if kind not in _cache:
        _cache[kind] = json.loads((SCHEMA_DIR / f"{kind}.schema.json").read_text())
    return _cache[kind]


def _jsonable(obj):
    """YAML gives datetime.date objects and Paths; schemas speak JSON types."""
    return json.loads(json.dumps(obj, default=str))


def validate(kind: str, obj, source: str) -> list[str]:
    """Validate obj against data/schema/<kind>.schema.json.

    Returns a list of error strings (empty = valid). Missing jsonschema
    degrades to a no-op so the pipeline still runs in a minimal env; CI
    always has it installed.
    """
    if jsonschema is None:
        return []
    validator = jsonschema.Draft7Validator(_schema(kind))
    errors = []
    for err in validator.iter_errors(_jsonable(obj)):
        where = "/".join(str(p) for p in err.absolute_path) or "(root)"
        errors.append(f"{source}: {where}: {err.message}")
    return errors


def require_valid(kind: str, obj, source: str) -> None:
    errors = validate(kind, obj, source)
    if errors:
        raise ValueError(f"schema violation ({kind}):\n  " + "\n  ".join(errors))


def check_all() -> int:
    if jsonschema is None:
        print("jsonschema not installed — cannot check", file=sys.stderr)
        return 2
    failures: list[str] = []

    for f in sorted(CITIES_DIR.glob("*.yaml")):
        failures += validate("city", yaml.safe_load(f.read_text()), str(f))
    for f in sorted(CITIES_DIR.glob("*/index.yaml")):
        failures += validate("index", yaml.safe_load(f.read_text()), str(f))
    for f in sorted(CITIES_DIR.glob("*/zones.yaml")):
        failures += validate("zones", yaml.safe_load(f.read_text()), str(f))
    for f in sorted(LEDGER_DIR.glob("*.jsonl")):
        for n, line in enumerate(f.read_text().splitlines(), 1):
            if line.strip():
                failures += validate("ledger-place", json.loads(line), f"{f}:{n}")
    for f in sorted((LEDGER_DIR / "checks").glob("*.jsonl")):
        for n, line in enumerate(f.read_text().splitlines(), 1):
            if line.strip():
                failures += validate("check-entry", json.loads(line), f"{f}:{n}")
    for f in sorted(QUEUE_DIR.glob("*.yaml")):
        doc = yaml.safe_load(f.read_text()) or {}
        for i, item in enumerate(doc.get("items", [])):
            failures += validate("queue-item", item, f"{f} items[{i}]")

    if failures:
        print(f"{len(failures)} schema violation(s):")
        for msg in failures:
            print(f"  {msg}")
        return 1
    print("all data files conform to data/schema/")
    return 0


if __name__ == "__main__":
    if "--check-all" in sys.argv:
        sys.exit(check_all())
    print(__doc__)
    sys.exit(0)
