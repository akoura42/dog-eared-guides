# Dog-Friendly City Guides

A deeply informative visitor-guide network where **dog-friendly is the brand,
not a filter**. Launch city: Tahoe City, CA. Verified accuracy of dog policies
is the product: every policy claim carries an official source and a
"Verified" date, and everything is automatically re-checked every 90 days.

Brand name is TBD — `BRAND_NAME` placeholder lives in `apps/web/src/lib/site.ts`.

## Layout

```
apps/web/            # Astro 5 static site (deployed on Cloudflare Pages)
  src/content/       # content collections: venues (md), guides (mdx)
  src/components/    # VenueCard, DogPolicyBlock, VerifiedBadge, AdSlot, ...
data/                # city configs, category & attribute definitions
pipeline/            # Python: generation, verification, maintenance
  prompts/           # versioned system prompt, style guide, editorial log
.github/workflows/   # PR build check + weekly 90-day re-verification cron
docs/RUNBOOK.md      # how to operate the site day-to-day  ← start here
```

## Quick start

```sh
cd apps/web && npm install && npm run dev     # site at localhost:4321
pip install -r pipeline/requirements.txt      # content pipeline
python pipeline/generate.py --dry-run         # draft queued content locally
```

## The rules that make this work

1. **No AI-authored venue fact ships without a source** — enforced by the
   generation prompt contract, `validate_venue_file()`, and the required
   `verification` block in the Zod schema.
2. **Sign-off = PR merge.** The pipeline only opens PRs; merge to `main`
   triggers the Cloudflare Pages deploy. That's the whole approval workflow.
3. **Cities are config + content.** Adding a city touches `data/cities/` and
   the content pipeline — never components.
4. **Hubs need ≥4 venues.** Category and attribute pages generate only when
   enough venues qualify; no thin programmatic pages.

Full operations guide: [`docs/RUNBOOK.md`](docs/RUNBOOK.md)
