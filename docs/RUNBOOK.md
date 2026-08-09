# RUNBOOK — operating Dog-Eared Guides day-to-day

## The one workflow that matters

```
discover (monthly, OSM) ──▶ research ledger ──▶ generate.py ──▶ PR ──▶ you review & merge ──▶ Cloudflare deploys
                                   ▲                                          │
                                   └────────── outcomes recorded ◀───────────┘
```

**Merging a PR is the entire approval step.** Nothing ships without it;
there is no other publish mechanism. The `Build check` GitHub Action runs
the Astro build (strict Zod schemas) on every PR, so malformed content
cannot merge green. Merges to `main` deploy to https://dogearedguides.com
via Cloudflare Pages.

---

## Local setup (once)

```sh
# Site
cd apps/web && npm install

# Pipeline
python3 -m venv .venv && source .venv/bin/activate
pip install -r pipeline/requirements.txt

# Auth — two engines, chosen automatically:
#   Claude subscription (default): the pipeline shells out to the Claude
#   Code CLI, using the login you already have on this machine. Nothing to
#   configure locally.
#   API billing (alternative): export ANTHROPIC_API_KEY=sk-ant-... and the
#   pipeline switches to direct SDK calls. Force either with
#   PIPELINE_ENGINE=claude-code|api.
gh auth login   # (or SSH keys — pushing and `gh pr create` both need GitHub auth)
```

Run the site locally: `cd apps/web && npm run dev` → http://localhost:4321

## The verification tiers (the product)

Every published venue carries one of two verification levels, enforced by
the Zod schema and shown to readers:

- **Tier 1 — `official` (green badge)**: the dog policy is confirmed by an
  official source (venue's own site/social, or the managing agency), with
  `verification.source_url` linked on the page.
- **Tier 2 — `reported` (amber badge)**: no official source exists, but at
  least **two independent, openly linkable visitor mentions agree**. The
  page lists every mention with a link and date and states plainly that
  the venue hasn't confirmed. Google Maps reviews may NOT be used as
  mentions (API terms); openly linkable pages only.
- **Tier 3 — neither**: not published. Tracked in the ledger as
  `unverifiable` with the evidence trail, so the research isn't repeated.

Tier-2 listings upgrade to tier 1 when an official policy appears or a
phone call confirms (`method: phone`). `/how-we-verify/` explains all of
this to readers — it's a trust asset, keep it accurate.

How to actually execute these tiers on a real city — the mention
independence test, blocked-site workarounds, chain and lodging rules, OSM
candidate hygiene — lives in `docs/RESEARCH_CRAFT.md`. Read it before
researching any queue batch.

## The research ledger (pipeline/ledger/)

The ledger is the pipeline's memory of every known place per city —
published or not. One JSONL file per city (PR-diffable on purpose) plus an
append-only per-city check history (`checks/<city>.jsonl`). Statuses:
`unchecked`, `queued`,
`published-official`, `published-reported`, `unverifiable`,
`rejected-no-dogs` (verified no — saves re-researching), `closed`,
`duplicate`.

```sh
python pipeline/ledger.py stats                      # coverage dashboard
python pipeline/ledger.py list --city tahoe-city --status unchecked
python pipeline/ledger.py set-status --city tahoe-city --id X --status queued
python pipeline/ledger.py sync                       # reconcile with published files
```

- **Discovery is three layers** (Google Places is off-limits — its terms
  forbid storing the data; all three below have storage-permitting
  licenses or produce leads, not stored data):
  1. `discover.py --city <slug>` — OpenStreetMap (© OSM contributors,
     ODbL). Best for parks, trails, beaches, public land.
  2. `discover_overture.py --city <slug>` — Overture Maps places
     (CDLA-Permissive 2.0; Meta-fed, monthly releases). Best for
     businesses; catches openings years before OSM. Bump the release
     with `--release` as new monthly versions publish.
  3. `discover_recent.py --city <slug>` — model + web search for venues
     opened/rebranded in the last 18 months → sourced queue rows (the
     only layer that catches last month's opening; the evo Hotel case).
  The monthly `discover.yml` GitHub Action runs the OSM sweep for all
  launched cities and opens a PR with new candidates.
- Phone-call outcomes and manual findings go in with `set-status` (with a
  `--note`); the check history records who/when/why.

## Add venues (the normal path: from the ledger)

```sh
python pipeline/generate.py --from-ledger tahoe-city --list-only   # preview batch
python pipeline/generate.py --from-ledger tahoe-city --limit 5     # run it
```

The model researches each candidate against the tier rules, drafts pages
for the ones that verify (tier 1 or 2), marks the rest `unverifiable` in
the ledger, and opens one PR containing the drafts + the ledger update.
Then review:

- Check every `verification.source_url` / mention actually supports the claim.
- Fix wording; **for each correction, add one line to
  `pipeline/prompts/EDITORIAL_LOG.md`** — recent entries are injected into
  every future generation prompt (the improvement loop).
- Resolve "Open questions" in the PR body (usually a phone call), or strip
  the unverified claims and merge without them.
- Merge → deployed, and `ledger.py sync` (or the next generate run)
  reconciles statuses.

`pipeline/queue/<city>.yaml` still works for named work — guides especially
(`type: guide` + `topic:`) — and for venues you want researched that
discovery hasn't surfaced.

## Add a venue or guide by hand

Copy an existing file in `apps/web/src/content/venues/<city>/` (schema
reference: `pipeline/prompts/STYLE_GUIDE.md`) and open a PR. The build
enforces the schema — `verification` fields are required, so a venue
physically cannot ship without a dated source. Guides live in
`src/content/guides/<city>/*.mdx` and embed venues with
`<VenueEmbed city="..." slug="..." />` so venue data stays single-sourced.

Special frontmatter worth knowing:

- `field_notes` — **human-editor-only** first-person observations from an
  actual visit; the only channel allowed to claim experience (voice.md §6).
  Presence renders the "Field-tested" badge.
- `menu` — real menu items from the venue's own published menu (never
  inferred from cuisine): `source_url` (where verified — archive.org
  captures of the official site are acceptable), `current_url` (live menu
  for readers), `last_verified`, `items` (with `"SECTION: Name"` headers).
  Powers dish search on category hubs.
- `google_place_id` — optional; pins the Google reviews panel to the exact
  listing (place IDs are the one thing Google's ToS lets you cache).

## The scheduled jobs

| Workflow | Cadence | What it does |
|---|---|---|
| `ci.yml` | every PR/push | Astro build = the schema gate |
| `verify.yml` | Mondays | Per-city matrix jobs re-check venues verified >90 days ago (25/city/week, oldest first); one PR per city (✅ date bumps, ✏️ policy changes, 🚫 closures). Also tries upgrading tier-2 listings to tier 1. Logs to `checks/<city>.jsonl`. |
| `discover.yml` | monthly | OSM candidate sweep for all launched cities → PR of new `unchecked` ledger rows |
| `deploy.yml` | push to main | Builds with production env vars and deploys to Cloudflare Pages via wrangler. Gated on the `CF_PAGES_PROJECT` repo variable — until that's set (and the CF dashboard git integration disconnected), shipping stays on the dashboard integration. |

### Repo secrets and variables (one-time setup, all workflows depend on these)

| Name | Kind | Why |
|---|---|---|
| `PIPELINE_PAT` | secret | Fine-grained PAT (this repo; Contents + Pull requests write). **Required for CI to run on bot-opened PRs** — GitHub suppresses workflow triggers on events created with the default `GITHUB_TOKEN`. Without it, verify/discover PRs show zero checks. |
| `CLAUDE_CODE_OAUTH_TOKEN` | secret | Model auth on the Claude subscription (mint with `claude setup-token`). Alternative: `ANTHROPIC_API_KEY` for API billing. |
| `CF_DEPLOY_ENABLED` | variable | Set `true` to activate `deploy.yml` (unset = the workflow skips). |
| `CLOUDFLARE_API_TOKEN` / `CLOUDFLARE_ACCOUNT_ID` | secrets | Wrangler deploy credentials (token needs Workers Scripts: Edit + Zone → Workers Routes: Edit). |
| `SITE_URL`, `PUBLIC_*`, affiliate vars | vars/secrets | Production env for the deploy build — see `apps/web/.env.example` for the full inventory. Missing vars ship a working site with monetization/analytics silently off. |

All jobs can be run manually from the Actions tab or locally
(`--dry-run` supported).

## Monthly: point generation at demand

Pull the top and bottom pages from GA4/Cloudflare Analytics, then aim the
next `--from-ledger` batches and queue items accordingly: expand what's
winning, refresh what's losing. The ledger's `unchecked` counts per city
are the backlog dashboard.

## Prompts are code

- `pipeline/prompts/SYSTEM.md` — the hard rules: tier contract, output format
- `pipeline/prompts/STYLE_GUIDE.md` — schemas + craft rules (incl. menus)
- `docs/voice.md` — the house voice; injected into every generation prompt
  as binding; conditions-not-advice, no reader-modeling, honesty guardrails
- `pipeline/prompts/EDITORIAL_LOG.md` — one line per human correction;
  newest first; injected into future prompts

Change them in PRs like any code change. If an editorial-log entry becomes
permanent doctrine, promote it into the style guide or voice doc.

## Add a new city (the multi-city contract)

**Follow `docs/CITY_PLAYBOOK.md`** — the phase-by-phase recipe proven on
Tahoe City, covering city config, discovery, venue batches, the
zones/trails layer, the Dog-Eared Index, the emergency block + pocket
card, logos/photos, the monetization pass, and the QA gate. The short
version: it's all data — `data/cities/<slug>.yaml` (config, plus optional
`areas:` aliases and `agency_domains:`), the ledger, and
`data/cities/<slug>/` computed artifacts. Everything downstream is
automatic once `launched: true`:
city picker + map pin, hub pages (≥4-venue thin-page guard), explorer
with filters/zones/emergency layer, index block, emergency + pocket-card
pages, itinerary planner, sitemap, OG images, CSV export.

"Coming soon" dots on the homepage map come from
`data/waterfront-towns.csv` (tiers 1–2), geocoded by
`python pipeline/geocode_towns.py` (US Census Gazetteer + Nominatim
fallback) into `waterfront-towns-geo.json`. Re-run only when the CSV
changes.

## Deploy (Cloudflare Workers, static assets)

The site is a Cloudflare **Workers** project named `dog-eared-guides` —
config (name, assets dir, custom domains dogearedguides.com + www) lives
in `apps/web/wrangler.jsonc`. Custom-domain bindings are created by the
deploy itself; no hand-managed DNS records for the apex/www (a stale A
record there took the whole site down with 522s once — 2026-08-09).

- Manual deploy (works from any machine with `wrangler login`):
  `cd apps/web && npm run build && npx wrangler@4 deploy`
- Automated: `deploy.yml` on push to main, activated by setting the
  `CF_DEPLOY_ENABLED=true` repo variable + `CLOUDFLARE_API_TOKEN` /
  `CLOUDFLARE_ACCOUNT_ID` secrets.
- The dashboard "Workers Builds" git integration never produced a working
  build — leave it disconnected; exactly one deployer.
- Environment variables (Production + Preview):
  - `NODE_VERSION` — `22`
  - `SITE_URL` — `https://dogearedguides.com` (canonicals/sitemap/OG; also
    the in-repo default)
  - `PUBLIC_GMAPS_API_KEY` — enables Google Maps mode + reviews panel
  - `PUBLIC_CF_ANALYTICS_TOKEN` — Cloudflare Web Analytics (cookieless)
  - `PUBLIC_GA4_ID` — GA4 (consent-gated)
  - `PUBLIC_ADSENSE_CLIENT` — AdSense (consent-gated; also update
    `apps/web/public/ads.txt`)
  - `BOOKING_AFFILIATE_AID` — Booking.com partner id; unset, lodging CTAs
    render unwrapped (activation is an env switch, not a content change)
  - `VIATOR_PARTNER_ID` — Viator partner id (P00xxxxx), same pattern
  - `PET_INSURANCE_URL` + `PET_INSURANCE_PARTNER` — pet-insurance
    referral link + display name; both required or the module renders
    nothing (see docs/monetization.md for placement rules)

## Maps & Google integration

All three maps (homepage US picker, city venue map, itinerary plan map)
are **dual-mode**: Google Maps when `PUBLIC_GMAPS_API_KEY` is set, free
stack (build-time SVG / Leaflet+OSM) when it isn't — the site works
identically either way, and Google load failures fall back gracefully.

Google Cloud setup for the key: enable **Maps JavaScript API** and
**Places API (New)**; restrict the key by HTTP referrer
(`https://dogearedguides.com/*`, `https://*.pages.dev/*`, localhost) and
to those two APIs; set a budget alert. Costs as of 2026: Dynamic Maps 10K
free loads/month then $7/1K; Place Details with reviews ~$40/1K with 1K
free/month.

**Click-to-reveal Google reviews** (venue pages): absent without the key;
with it, nothing loads or bills until a reader expands the panel — the
place-ID lookup uses the free IDs-only search and the single billed call
is the rating/reviews fetch. Expect ≈ $0.04 × (expands beyond 1,000/mo).
"Google reviews" deep links (free, no key) exist regardless.

## Monetization notes

**`docs/monetization.md` is the reference** — tiered plan, the
trust constraint (venue layer only, labeled, never touching listings or
scores), and per-channel implementation notes. Operational summary:

- Ad slots are consent-gated, lazy, and height-reserved (zero CLS); render
  nothing until `PUBLIC_ADSENSE_CLIENT` is set. Swapping to a premium
  network later = replacing the loader inside `AdSlot.astro`.
- Affiliate links: set `affiliate.viator_url` / `booking_url` (+
  `viator_product_code`) in venue frontmatter; partner ids are appended
  at render by `lib/affiliate.ts` when the env vars above are set.
  Identity-verify property URLs (address match) before linking. Pages
  with affiliate links auto-render the FTC disclosure; links carry
  `rel="sponsored nofollow"`.
- Pet-insurance module places itself on emergency-vet venue pages, the
  emergency page, and pet-fee lodging pages once its env vars are set.
- `apps/web/public/ads.txt` must carry the real publisher line before ads
  go live.
- Decision (2026-08-04): reviews/maps stay on the free deep-link pattern
  until the Google key is provisioned; inline always-visible reviews were
  ruled out (cost exceeds page revenue — see git history for the math).

## Brand name

Dog-Eared Guides, set once in `apps/web/src/lib/site.ts`; flows through
copy, metadata, JSON-LD, and OG images.
