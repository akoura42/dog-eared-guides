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
- `data/cities/<slug>.yaml` — per-city editorial config. `launched: false`
  (the default) until the QA gate passes; flipping it is the launch step.
- `data/towns/<slug>/` — computed artifacts: Dog-Eared Index
  (`index.yaml`), map zones (`zones.yaml` + `zones.geojson`).
- `pipeline/` — Python research/generation pipeline. Per-city research
  ledgers in `pipeline/ledger/<city>.jsonl`; global check log
  `checks.jsonl`; work queue `queue.yaml` (hand-maintained: mark rows
  `done: true` yourself — nothing writes back automatically).
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
python pipeline/discover.py <city> [--radius-km N]   # OSM candidate sweep
python pipeline/discover.py --all-launched
python pipeline/generate.py --from-ledger <city> [--parallel 2-3] [--model M]
python pipeline/ledger.py stats|list|set-status|sync
python pipeline/verify.py [--city <city>] [--limit N] [--max-age 90] [--dry-run]
python pipeline/index/compute.py <slug> [--check|--rescore]
python pipeline/index/zones.py <slug>
python pipeline/fetch_logos.py <slug>
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
