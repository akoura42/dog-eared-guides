# RUNBOOK — operating the site day-to-day

## The one workflow that matters

```
queue item → generate.py → PR → you review & merge → Cloudflare Pages deploys
```

**Merging a PR is the entire approval step.** Nothing ships without it; there
is no other publish mechanism. The `Build check` GitHub Action runs the Astro
build (strict Zod schemas) on every PR, so malformed content cannot merge green.

---

## Local setup (once)

```sh
# Site
cd apps/web && npm install

# Pipeline
python3 -m venv .venv && source .venv/bin/activate
pip install -r pipeline/requirements.txt

# Auth: the pipeline uses the Anthropic SDK and the GitHub CLI
export ANTHROPIC_API_KEY=sk-ant-...   # or `ant auth login`
gh auth login
```

Run the site locally: `cd apps/web && npm run dev` → http://localhost:4321

## Add a venue (via pipeline — the normal path)

1. Add an item to `pipeline/queue.yaml`:
   ```yaml
   - type: venue
     city: tahoe-city
     name: Some Tavern
     category: eat
     notes: anything useful (candidate URLs, phone, warnings)
   ```
2. `python pipeline/generate.py --limit 1`
3. Review the PR it opens:
   - Check every `verification.source_url` actually supports the claim.
   - Fix wording; **for each correction, add one line to
     `pipeline/prompts/EDITORIAL_LOG.md`** (this is the improvement loop —
     recent entries are injected into every future generation prompt).
   - Resolve "Open questions" in the PR body (usually a phone call), or leave
     them unchecked and strip the unverified claims.
4. Merge → deployed. Mark the queue item `done: true`.

## Add a venue (by hand)

Copy an existing file in `apps/web/src/content/venues/<city>/`, follow the
schema in `pipeline/prompts/STYLE_GUIDE.md`, and open a PR. The build enforces
the schema — `verification` fields are required, so a venue physically cannot
ship without a dated source.

## Add a guide

Same as venues with `type: guide` + `topic:` in the queue. Guides live in
`apps/web/src/content/guides/<city>/*.mdx` and embed venues with
`<VenueEmbed city="..." slug="..." />` so venue data stays single-sourced.

## The 90-day re-verification cron

`.github/workflows/verify.yml` runs `pipeline/verify.py` every Monday. It
finds venues whose `verification.last_verified` is older than 90 days,
re-checks official sources, and opens one PR containing:

- ✅ unchanged venues → date bumped
- ✏️ changed policies → full updated file for review
- 🚫 apparently-closed venues → flagged for your confirmation and removal

Requires the `ANTHROPIC_API_KEY` repository secret. Run it manually anytime
from the Actions tab (workflow_dispatch) or locally:
`python pipeline/verify.py --dry-run`.

## Monthly: point generation at demand

Pull the top and bottom pages from GA4/Cloudflare Analytics and add queue
items accordingly: expand what's winning (more venues in a hot category, a
deeper guide) and refresh or improve what's losing. The queue file is the
editorial calendar.

## Prompts are code

`pipeline/prompts/` is versioned deliberately:

- `SYSTEM.md` — the hard rules (sourcing contract, output format)
- `STYLE_GUIDE.md` — voice + schemas; update it when patterns emerge
- `EDITORIAL_LOG.md` — one line per human correction; newest first

Change them in PRs like any code change. If an editorial-log entry becomes
permanent doctrine, promote it into the style guide.

## Add a new city (the multi-city contract)

Zero component edits required. The whole procedure:

1. Create `data/cities/<slug>.yaml` (copy `tahoe-city.yaml`): name, slug,
   geo, hero copy, intro, sourced regulations, seasonal notes, category list.
2. Add queue items for the city's first ~15 venues and 3 guides; run the
   pipeline; review the PRs.
3. Merge. The city picker, hub pages, category hubs (once ≥4 venues qualify),
   sitemap, and OG images all generate from config + content.

## Deploy (Cloudflare Pages)

- Create a Pages project pointed at this repo.
- Build command: `npm run build` · Build output: `dist` · Root dir: `apps/web`
- Production branch: `main` (merge = deploy).
- Environment variables (optional until monetization is live):
  - `SITE_URL` — production URL (canonicals/sitemap/OG)
  - `PUBLIC_ADSENSE_CLIENT` — AdSense publisher ID (also update `apps/web/public/ads.txt`)
  - `PUBLIC_GA4_ID` — GA4 measurement ID
  - `PUBLIC_CF_ANALYTICS_TOKEN` — Cloudflare Web Analytics token

## Monetization notes

- Ad slots are consent-gated, lazy, and height-reserved (zero CLS). They render
  nothing until `PUBLIC_ADSENSE_CLIENT` is set. Swapping to a premium network
  later = replacing the loader inside `AdSlot.astro` — placements stay put.
- Affiliate links: set `affiliate.viator_url` / `booking_url` in venue
  frontmatter (store the Viator product code alongside in
  `viator_product_code`). Pages with affiliate links automatically render the
  FTC disclosure; links carry `rel="sponsored nofollow"`.
- `apps/web/public/ads.txt` must carry your real publisher line before ads go live.

## Maps

Decision (2026-08-04): stay on the free stack. City-hub venue maps are
Leaflet + OpenStreetMap tiles (no key, no billing); "Google reviews" links
on markers and venue pages are free Google Maps deep links (Maps URLs).

Upgrade path if wanted later: a native embedded Google map needs a Maps
JavaScript API key with billing (Dynamic Maps SKU: 10K free loads/month,
then $7/1K as of 2026). The swap is contained to
`apps/web/src/components/CityVenueMap.astro`. Showing star ratings inline
would need the Places API ($17/1K, no caching allowed by ToS) — not
recommended for a static site; the deep link is the compliant pattern.

## Brand name

Still `BRAND_NAME`. When it lands, change `BRAND_NAME` (and tagline) in
`apps/web/src/lib/site.ts` — it flows through copy, metadata, JSON-LD, and OG
images from there.
