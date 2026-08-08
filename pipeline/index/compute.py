"""Dog-Eared Index v1 — yaml -> scores -> composite (docs/dog-eared-index.md).

Bands and weights live HERE, in code. Measured values live in
data/towns/<slug>/index.yaml. Hospitality components are computed live from
venue records on every run and are never hand-entered. If a stored score
disagrees with the band recomputation the run fails (band drift): a band
change requires a version bump and an explicit --rescore.

Usage:
  python pipeline/index/compute.py <town-slug>            # compute + write
  python pipeline/index/compute.py <town-slug> --check    # verify only (CI)
  python pipeline/index/compute.py <town-slug> --rescore  # accept new bands
                                                          # after a v-bump

Every run also refreshes data/index-bands.json, which the methodology page
renders — the band tables on the site come from this file, so display and
scoring can't drift apart.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
VENUES_DIR = REPO_ROOT / "apps" / "web" / "src" / "content" / "venues"
TOWNS_DIR = REPO_ROOT / "data" / "towns"
BANDS_JSON = REPO_ROOT / "data" / "index-bands.json"

VERSION = "index-v1"
TAGLINE = "This counts what exists; it doesn't know your dog."

# Composite publishes only at >= 7 of 9 verified components; at 7-8 the
# weights renormalize and the score is labeled provisional.
PUBLISH_GATE = 7

# --- Component definitions -------------------------------------------------
# kind:
#   share       value is a 0-1 fraction; bands are descending minimums
#   number      value is a number; bands are descending minimums
#   number-max  value is a number; bands are ascending maximums
#   condition   value is a band key chosen by the verifier
#   rubric      value derives from a list of cited modifier keys
COMPONENTS = [
    {
        "key": "patio_share",
        "label": "Patio share",
        "pillar": "Hospitality",
        "weight": 15,
        "kind": "share",
        "unit": "% of food/drink venues",
        "auto": True,
        "bands": [
            {"label": "≥ 50%", "min": 0.50, "score": 100},
            {"label": "35–49%", "min": 0.35, "score": 80},
            {"label": "25–34%", "min": 0.25, "score": 60},
            {"label": "15–24%", "min": 0.15, "score": 40},
            {"label": "5–14%", "min": 0.05, "score": 20},
            {"label": "< 5%", "min": None, "score": 0},
        ],
    },
    {
        "key": "indoor_welcome",
        "label": "Indoor welcome",
        "pillar": "Hospitality",
        "weight": 5,
        "kind": "share",
        "unit": "% of retail/taproom venues",
        "auto": True,
        "bands": [
            {"label": "≥ 25%", "min": 0.25, "score": 100},
            {"label": "15–24%", "min": 0.15, "score": 75},
            {"label": "8–14%", "min": 0.08, "score": 50},
            {"label": "3–7%", "min": 0.03, "score": 25},
            {"label": "< 3%", "min": None, "score": 0},
        ],
    },
    {
        "key": "lodging_share",
        "label": "Lodging share",
        "pillar": "Hospitality",
        "weight": 10,
        "kind": "share",
        "unit": "% of lodging properties",
        "auto": True,
        "bands": [
            {"label": "≥ 60%", "min": 0.60, "score": 100},
            {"label": "45–59%", "min": 0.45, "score": 80},
            {"label": "30–44%", "min": 0.30, "score": 60},
            {"label": "15–29%", "min": 0.15, "score": 40},
            {"label": "5–14%", "min": 0.05, "score": 20},
            {"label": "< 5%", "min": None, "score": 0},
        ],
    },
    {
        "key": "water_access",
        "label": "Water access",
        "pillar": "Access",
        "weight": 15,
        "kind": "condition",
        "unit": "legal dog water-entry points, 15-min isochrone",
        "bands": [
            {"key": "three-plus-yearround", "label": "≥ 3 points, year-round", "score": 100},
            {"key": "three-seasonal-or-two-yearround", "label": "≥ 3 seasonal, or 2 year-round", "score": 80},
            {"key": "two-seasonal-or-one-yearround", "label": "2 seasonal, or 1 year-round", "score": 60},
            {"key": "one-seasonal", "label": "1 seasonal", "score": 40},
            {"key": "wading-only", "label": "Legal wading/bank access only (no swim point)", "score": 20},
            {"key": "none", "label": "None", "score": 0},
        ],
    },
    {
        "key": "trail_access",
        "label": "Trail access",
        "pillar": "Access",
        "weight": 12,
        "kind": "number",
        "unit": "dog-allowed trail miles, 15-min isochrone",
        "bands": [
            {"label": "≥ 100", "min": 100, "score": 100},
            {"label": "50–99", "min": 50, "score": 85},
            {"label": "25–49", "min": 25, "score": 70},
            {"label": "10–24", "min": 10, "score": 50},
            {"label": "3–9", "min": 3, "score": 30},
            {"label": "1–2", "min": 1, "score": 15},
            {"label": "< 1", "min": None, "score": 0},
        ],
    },
    {
        "key": "off_leash",
        "label": "Off-leash space",
        "pillar": "Access",
        "weight": 8,
        "kind": "condition",
        "unit": "designated off-leash acreage",
        "bands": [
            {"key": "twenty-acres-or-beach", "label": "≥ 20 acres, or any designated off-leash beach", "score": 100},
            {"key": "five-to-twenty-acres", "label": "5–19.9 acres", "score": 75},
            {"key": "one-to-five-acres", "label": "1–4.9 acres", "score": 50},
            {"key": "fenced-run", "label": "Fenced run under 1 acre", "score": 25},
            {"key": "none", "label": "None", "score": 0},
        ],
    },
    {
        "key": "ordinance",
        "label": "Ordinance regime",
        "pillar": "Rules",
        "weight": 15,
        "kind": "rubric",
        "unit": "points (base 50, floor 0, cap 100)",
        "modifiers": [
            {"key": "patio-permitted", "label": "Patio dining explicitly permitted by state or local rule", "points": 20},
            {"key": "voice-control-areas", "label": "Any voice-control / off-leash-under-command areas in code", "points": 15},
            {"key": "shoreline-open", "label": "No shoreline dog ban at the primary shoreline, or a designated dog beach exists", "points": 15},
            {"key": "shoreline-seasonal-ban", "label": "Seasonal ban at the primary shoreline", "points": -10},
            {"key": "shoreline-yearround-ban", "label": "Year-round ban at the primary shoreline", "points": -25},
            {"key": "bsl", "label": "Breed-specific legislation in force", "points": -40},
        ],
    },
    {
        "key": "emergency_vet",
        "label": "Emergency vet",
        "pillar": "Practical",
        "weight": 10,
        "kind": "number-max",
        "unit": "minutes to nearest 24/7 or after-hours ER vet",
        "bands": [
            {"label": "≤ 15", "max": 15, "score": 100},
            {"label": "16–30", "max": 30, "score": 80},
            {"label": "31–45", "max": 45, "score": 60},
            {"label": "46–60", "max": 60, "score": 40},
            {"label": "61–90", "max": 90, "score": 20},
            {"label": "> 90", "max": None, "score": 0},
        ],
    },
    {
        "key": "heat_risk",
        "label": "Heat risk",
        "pillar": "Practical",
        "weight": 10,
        "kind": "number-max",
        "unit": "days/year with normal high ≥ 90°F (NOAA 1991–2020)",
        "bands": [
            {"label": "≤ 5", "max": 5, "score": 100},
            {"label": "6–15", "max": 15, "score": 85},
            {"label": "16–30", "max": 30, "score": 70},
            {"label": "31–60", "max": 60, "score": 50},
            {"label": "61–100", "max": 100, "score": 30},
            {"label": "> 100", "max": None, "score": 10},
        ],
    },
]

PILLARS = ["Hospitality", "Access", "Rules", "Practical"]


class BandDrift(Exception):
    pass


def band_score(component: dict, value) -> int | None:
    """Map a stored value to its band score. None value -> None (missing)."""
    if value is None:
        return None
    kind = component["kind"]
    if kind in ("share", "number"):
        for band in component["bands"]:
            if band["min"] is not None and value >= band["min"]:
                return band["score"]
        return component["bands"][-1]["score"]
    if kind == "number-max":
        for band in component["bands"]:
            if band["max"] is not None and value <= band["max"]:
                return band["score"]
        return component["bands"][-1]["score"]
    if kind == "condition":
        for band in component["bands"]:
            if band["key"] == value:
                return band["score"]
        raise ValueError(f"{component['key']}: unknown condition {value!r}")
    if kind == "rubric":
        points = 50
        known = {m["key"]: m["points"] for m in component["modifiers"]}
        for mod in value:
            if mod not in known:
                raise ValueError(f"{component['key']}: unknown modifier {mod!r}")
            points += known[mod]
        return max(0, min(100, points))
    raise ValueError(f"unknown kind {kind!r}")


# --- Hospitality: live from venue records ----------------------------------

def normalize_allowed(raw) -> str:
    # YAML 1.1 parses bare `no`/`yes` as booleans; venue frontmatter uses
    # the string enum from content.config.ts.
    if raw is False:
        return "no"
    if raw is True:
        return "yes"
    return str(raw)


def load_venue_records(slug: str) -> list[dict]:
    town_dir = VENUES_DIR / slug
    records = []
    for f in sorted(town_dir.glob("*.md")):
        text = f.read_text()
        if not text.startswith("---"):
            continue
        front = yaml.safe_load(text.split("---", 2)[1])
        records.append(
            {
                "file": f.name,
                "category": front.get("category"),
                "allowed": normalize_allowed((front.get("dog_policy") or {}).get("allowed")),
            }
        )
    return records


OUTDOOR_SEATING = {"patio_only", "outdoor_areas", "indoors"}

def hospitality_values(venues: list[dict]) -> dict[str, dict]:
    """The three auto components, each with its measured share and basis."""
    def share(denom_pred, numer_pred):
        denom = [v for v in venues if denom_pred(v)]
        numer = [v for v in denom if numer_pred(v)]
        if not denom:
            return {"value": None, "basis": {"numerator": 0, "denominator": 0}}
        return {
            "value": round(len(numer) / len(denom), 4),
            "basis": {"numerator": len(numer), "denominator": len(denom)},
        }

    return {
        # Dog-allowed outdoor seating at food/drink venues. `indoors` counts:
        # a venue verified dog-allowed inside admits dogs at its seating.
        "patio_share": share(
            lambda v: v["category"] in ("eat", "drink"),
            lambda v: v["allowed"] in OUTDOOR_SEATING,
        ),
        # Verified dog-allowed *inside* at retail/taproom venues.
        "indoor_welcome": share(
            lambda v: v["category"] in ("shop", "pet-supply", "drink"),
            lambda v: v["allowed"] == "indoors",
        ),
        # Lodging properties accepting dogs in any room class.
        "lodging_share": share(
            lambda v: v["category"] == "stay",
            lambda v: v["allowed"] != "no",
        ),
    }


# --- Composite --------------------------------------------------------------

def compute_composite(scores: dict[str, int | None]) -> dict:
    verified = {k: s for k, s in scores.items() if s is not None}
    n = len(verified)
    result = {"components_verified": n, "components_total": len(COMPONENTS)}
    if n < PUBLISH_GATE:
        result.update({"score": None, "provisional": None})
        return result
    weights = {c["key"]: c["weight"] for c in COMPONENTS}
    total_w = sum(weights[k] for k in verified)
    weighted = sum(weights[k] * s for k, s in verified.items())
    result.update(
        {
            "score": round(weighted / total_w),
            "provisional": n < len(COMPONENTS),
        }
    )
    return result


def pillar_subtotals(scores: dict[str, int | None]) -> dict:
    out = {}
    for pillar in PILLARS:
        comps = [c for c in COMPONENTS if c["pillar"] == pillar]
        verified = [c for c in comps if scores.get(c["key"]) is not None]
        entry = {"components_verified": len(verified), "components_total": len(comps)}
        if verified:
            total_w = sum(c["weight"] for c in verified)
            entry["score"] = round(
                sum(c["weight"] * scores[c["key"]] for c in verified) / total_w
            )
        else:
            entry["score"] = None
        out[pillar.lower()] = entry
    return out


# --- IO ---------------------------------------------------------------------

def default_component_entry() -> dict:
    return {"value": None, "sources": [], "last_verified": None}


def run(slug: str, check: bool = False, rescore: bool = False) -> dict:
    index_file = TOWNS_DIR / slug / "index.yaml"
    stored = {}
    if index_file.exists():
        stored = yaml.safe_load(index_file.read_text()) or {}
    if stored.get("version", VERSION) != VERSION:
        raise SystemExit(
            f"{index_file}: version {stored.get('version')!r} != {VERSION}; "
            "recompute after reconciling the version bump"
        )

    components_out = {}
    scores: dict[str, int | None] = {}
    today = dt.date.today().isoformat()

    auto_values = hospitality_values(load_venue_records(slug))

    for comp in COMPONENTS:
        key = comp["key"]
        prior = (stored.get("components") or {}).get(key) or {}
        if comp.get("auto"):
            measured = auto_values[key]
            entry = {
                "value": measured["value"],
                "basis": measured["basis"],
                "sources": [
                    {
                        "method": "venue-records",
                        "note": (
                            f"computed from {measured['basis']['denominator']} "
                            "published venue records"
                        ),
                        "date": today,
                    }
                ],
                "last_verified": today,
            }
        else:
            entry = {
                "value": prior.get("modifiers") if comp["kind"] == "rubric" else prior.get("value"),
                "sources": prior.get("sources", []),
                "last_verified": prior.get("last_verified"),
            }
            if comp["kind"] == "rubric":
                entry = {
                    "modifiers": prior.get("modifiers"),
                    "sources": prior.get("sources", []),
                    "last_verified": prior.get("last_verified"),
                }
            # Spec §4: isochrone-fallback measurements carry a geometry flag.
            if prior.get("geometry"):
                entry["geometry"] = prior["geometry"]
        raw_value = entry.get("modifiers") if comp["kind"] == "rubric" else entry["value"]
        score = band_score(comp, raw_value)

        # Band-drift gate: a stored score may only disagree with the
        # recomputation when the operator explicitly accepts new bands.
        if prior.get("score") is not None and prior["score"] != score and not rescore:
            raise BandDrift(
                f"{slug}/{key}: stored score {prior['score']} != recomputed "
                f"{score}. Bands changed? Bump the version and rerun with "
                "--rescore."
            )
        entry["score"] = score
        scores[key] = score
        components_out[key] = entry

    out = {
        "version": VERSION,
        "town": slug,
        "computed": today,
        "components": components_out,
        "pillars": pillar_subtotals(scores),
        "composite": compute_composite(scores),
    }

    if check:
        prior_composite = (stored.get("composite") or {}).get("score")
        if prior_composite != out["composite"]["score"]:
            raise SystemExit(
                f"--check: stored composite {prior_composite} != recomputed "
                f"{out['composite']['score']}"
            )
        print(f"{slug}: check ok ({out['composite']['components_verified']}/9 verified)")
        return out

    index_file.parent.mkdir(parents=True, exist_ok=True)
    index_file.write_text(yaml.safe_dump(out, sort_keys=False, allow_unicode=True))
    export_bands()
    c = out["composite"]
    label = (
        f"composite {c['score']}" + (" (provisional)" if c["provisional"] else "")
        if c["score"] is not None
        else "composite unpublished"
    )
    print(f"{slug}: {c['components_verified']}/9 components verified — {label}")
    return out


def export_bands() -> None:
    """The methodology page renders exactly this file — no copy drift."""
    payload = {
        "version": VERSION,
        "tagline": TAGLINE,
        "publish_gate": PUBLISH_GATE,
        "pillars": PILLARS,
        "components": [
            {
                k: comp[k]
                for k in ("key", "label", "pillar", "weight", "kind", "unit")
            }
            | (
                {"modifiers": comp["modifiers"], "base": 50}
                if comp["kind"] == "rubric"
                else {"bands": [
                    {"label": b["label"], "score": b["score"]} for b in comp["bands"]
                ]}
            )
            | ({"auto": True} if comp.get("auto") else {})
            for comp in COMPONENTS
        ],
    }
    BANDS_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:]]
    if "--export-bands" in args:
        export_bands()
        print(f"wrote {BANDS_JSON}")
        sys.exit(0)
    slugs = [a for a in args if not a.startswith("--")]
    if not slugs:
        sys.exit("usage: compute.py <town-slug> [--check|--rescore]")
    run(slugs[0], check="--check" in args, rescore="--rescore" in args)
