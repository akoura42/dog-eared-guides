# Dog-Eared Guides

A deeply informative visitor-guide network where **dog-friendly is the
brand, not a filter**. Live at https://dogearedguides.com. Launched:
Tahoe City, CA and Charlotte, NC, with 11 more cities configured
(`launched: false` until their QA gate passes) and ~1,250 waterfront
towns queued on the map. Verified accuracy is the product: every dog-policy
claim carries a source and a "Verified" date, everything is re-checked on
a schedule, and evidence quality is shown to readers as a three-tier badge
system (official / visitor-reported / unpublished).

## Layout

```
apps/web/            # Astro 5 static site → Cloudflare Pages
  src/content/       # venues (md) + guides (mdx) — the published layer, git-reviewed
  src/components/    # DogPolicyBlock, VerifiedBadge, DishSearch, maps, planner, ...
data/
  cities/            # per-city: <slug>.yaml config + <slug>/ computed artifacts (index, zones)
  schema/            # canonical JSON Schemas for every data format (CI-enforced)
  categories.yaml    # category + attribute definitions
pipeline/            # Python: generation, verification, discovery, geocoding
  index/             # Dog-Eared Index: compute.py (bands as code), zones.py (map geometry)
  ledger/            # research ledger: every known place per city + check history
  prompts/           # versioned system prompt, style guide, editorial log
docs/
  RUNBOOK.md         # how to operate everything  ← start here
  CITY_PLAYBOOK.md   # the phase-by-phase recipe for launching a city
  RESEARCH_CRAFT.md  # how to actually verify a dog policy (read before researching)
  dog-eared-index.md # spec for the town-level dog-friendliness index
  monetization.md    # tiered monetization plan + implementation notes
  voice.md           # the house voice, injected into every generation prompt
.github/workflows/   # PR build+schema gate, per-city verify cron, monthly OSM discovery, gated CF deploy
```

## Quick start

```sh
cd apps/web && npm install && npm run dev          # site at localhost:4321
pip install -r pipeline/requirements.txt           # pipeline (auth: your Claude
                                                   # subscription via Claude Code,
                                                   # or ANTHROPIC_API_KEY)
python pipeline/ledger.py stats                    # research coverage dashboard
python pipeline/generate.py --from-ledger tahoe-city --list-only
```

## The rules that make this work

1. **Evidence tiers, enforced.** Tier 1: official source (green badge).
   Tier 2: ≥2 agreeing, linkable visitor mentions (amber badge, labeled
   unconfirmed). Neither: not published — tracked in the ledger instead.
   The Zod schema makes unverified venues unbuildable.
2. **Sign-off = PR merge.** The pipeline only opens PRs; merge to `main`
   deploys via Cloudflare Pages. CI runs the strict-schema build on every PR.
3. **The ledger remembers everything.** Published, rejected-no-dogs,
   unverifiable-with-evidence, closed — nothing gets researched twice.
   Monthly OSM discovery refills the candidate pool; weekly verification
   re-checks anything older than 90 days.
4. **Cities are config + content.** A new city is one YAML file plus
   pipeline runs — components never change. Category hubs index only at
   ≥4 venues (no thin pages); maps, planner, and picker update themselves.
5. **Voice is code.** `docs/voice.md` (conditions, not advice; no invented
   experience) is injected into every generation prompt; human corrections
   accumulate in the editorial log and feed back into future drafts.
6. **Free-tier by default.** Maps, reviews links, and search all work with
   zero paid APIs; setting `PUBLIC_GMAPS_API_KEY` upgrades maps to Google
   and enables the click-to-reveal reviews panel, with cost guardrails
   documented in the runbook.

Full operations guide: [`docs/RUNBOOK.md`](docs/RUNBOOK.md)
