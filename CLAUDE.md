# Dog-Eared Guides — repo guide

Verified dog-friendly city guides. Two launched cities (tahoe-city,
charlotte); the plan is hundreds. Accuracy is the product: every dog-policy
claim carries a source URL and a verification tier. **Never invent, never
impute** — a missing fact renders as missing; that honesty is the brand.

## Layout

- `apps/web/` — Astro static site. Content collections in
  `src/content/venues/<city>/` and `src/content/guides/<city>/`; the venue
  schema (`src/content.config.ts`) is STRICT — unknown/misplaced frontmatter
  keys fail the build. City configs are Zod-validated by `src/lib/config.ts`.
- `data/cities/<slug>.yaml` — per-city editorial config, including
  `areas:` (explorer area aliases), `agency_domains:`, and
  `discover_radius_km`. `launched: false` (the default) until the QA gate
  passes; flipping it is the launch step.
- `data/cities/<slug>/` — computed artifacts: Dog-Eared Index
  (`index.yaml`), map zones (`zones.yaml` + `zones.geojson`).
- `data/schema/` — canonical JSON Schemas for every data format. The
  pipeline validates on write; CI runs `schemas.py --check-all` on every
  PR. Format changes touch the schema and both readers in one PR.
- `pipeline/` — Python research/generation pipeline. Everything is
  per-city: ledgers `pipeline/ledger/<city>.jsonl`, check logs
  `pipeline/ledger/checks/<city>.jsonl`, work queues
  `pipeline/queue/<city>.yaml` (generate.py writes `done:` markers back
  automatically after each run).
- `pipeline/prompts/` — SYSTEM.md, STYLE_GUIDE.md, voice.md injections.
  **Prompts are code**: when a human corrects generated output, log the
  correction in `EDITORIAL_LOG.md` (recent entries are injected into every
  generation prompt).

## Read these before city work

1. `docs/CITY_PLAYBOOK.md` — the phase-by-phase new-city checklist.
2. `docs/RUNBOOK.md` — commands, ledger statuses, PR review checklist.
3. `docs/RESEARCH_CRAFT.md` — how to actually verify a dog policy
   (tier tests, blocked-site workarounds, chain/lodging rules).
4. `docs/dog-eared-index.md` — index methodology.
5. `docs/voice.md` — voice rules; bans advice imperatives ("call ahead").

## The tier contract

- **Tier 1 (`level: official`)** — an official source states the policy;
  `source_url` points at it.
- **Tier 2 (`level: reported`)** — no official source exists AND ≥2
  genuinely independent, linkable visitor mentions agree (`mentions:`,
  schema-enforced minimum of 2). The page labels it unconfirmed.
- **Tier 3** — evidence insufficient: not published. Log it in the ledger
  (`unverifiable` + note with the phone number) instead.

## Command crib sheet

```
python pipeline/discover.py --city <city>            # OSM sweep (radius from city yaml)
python pipeline/discover.py --all-launched
python pipeline/discover_overture.py --city <city>   # Overture places sweep (businesses)
python pipeline/discover_recent.py --city <city>     # model sweep for recent openings -> queue
python pipeline/generate.py --city <city> [--limit N]        # queue items
python pipeline/generate.py --from-ledger <city> [--parallel 2-3] [--model M]
python pipeline/ledger.py stats|list|set-status|sync
python pipeline/verify.py [--city <city>] [--limit N] [--max-age 90] [--dry-run]
python pipeline/index/compute.py <slug> [--check|--rescore]
python pipeline/index/compute.py --export-bands      # refresh data/index-bands.json
python pipeline/index/zones.py <slug>
python pipeline/fetch_logos.py <slug>
python pipeline/schemas.py --check-all               # data vs data/schema/
cd apps/web && npm run check && npm run build        # the machine gate
python -m pytest pipeline/index/test_compute.py -q
```

## Conventions

- Branches: `content/<city>-batch-N` for venue batches — one city per
  branch. Pipeline PRs branch from `origin/main`, never from a working
  branch.
- Merging a PR **is** the approval step; nothing auto-merges.
- `field_notes` and `image*` frontmatter are human-editor-only — the
  pipeline never writes them.
- Env vars: see `apps/web/.env.example` (every var silently defaults to
  empty — a missing var drops the feature, not the build).
