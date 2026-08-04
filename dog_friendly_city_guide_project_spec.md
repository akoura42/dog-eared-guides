# Project Spec — Dog-Friendly City Guide (Launch City: Tahoe City)

Handoff spec for Claude Code. Build this as a production project, not a prototype.

## 1. Vision

A deeply informative visitor guide where **dog-friendly is the brand**, not a filter. Launch city: Tahoe City, CA. The architecture must treat "Tahoe City" as configuration + content so that additional cities can be added later without touching components.

Positioning: the incumbent in this space (BringFido) is a broad, shallow directory. We win on **depth per city** and **verified accuracy of dog policies** — policies change constantly (seasonal beach rules, patio policies, leash laws), so verification metadata is a first-class feature, shown to readers as a trust signal.

Brand name: **TBD — use `BRAND_NAME` placeholder** in config, copy, and metadata so it can be swapped in one place.

## 2. Stack

- **Astro** (static output, content collections) deployed on **Cloudflare Pages**
- Content lives in the repo as Markdown/MDX + JSON/YAML data — no CMS, no database for v1
- Pipeline scripts in **Python** under `pipeline/` (owner's standard stack)
- Monorepo layout:

```
apps/web/            # Astro site
  src/content/       # content collections (venues, guides, cities)
  src/components/
pipeline/            # Python: generation, verification, maintenance
  prompts/           # versioned prompt + style-guide files
data/                # city configs, category definitions
docs/RUNBOOK.md      # how to operate the site day-to-day
```

## 3. Content model

### City config (`data/cities/tahoe-city.yaml`)
All city-specific values: name, slug, state, geo center, hero copy hooks, seasonal notes, local regulations summary, category list. **Zero hardcoded city references in components** — this is the multi-city contract.

### Venue schema (the core asset)
Astro content collection with strict Zod schema. Fields:

- `name`, `slug`, `category` (eat | drink | stay | trail | beach | activity | shop | services), `neighborhood`
- `address`, `lat`, `lng`, `phone`, `website`
- `dog_policy`: `allowed` (indoors | patio_only | outdoor_areas | grounds_only | no), `leash_required`, `water_bowls`, `size_or_breed_restrictions`, `fee`, `notes`
- `seasonal`: free-text array (critical for Tahoe: winter closures, summer-only beach rules)
- `verification`: `last_verified` (date), `method` (official_website | phone | in_person | other), `source_url` — **required fields; the site displays "Verified <date>" on every venue**
- `affiliate`: optional `viator_product_code`, optional lodging booking link
- `body`: 200–400 words of genuinely useful, specific editorial (what it's like to be there with a dog, parking, shade, crowds)

### Guides
Long-form MDX (1,200–2,500 words): itineraries, "best of" roundups, seasonal guides. Guides embed venue cards by slug so venue data stays single-sourced.

## 4. Content pipeline (AI-drafted, human-approved, self-improving)

**Hard rule: no AI-authored fact about a specific venue ships without a source.** Generation prompts must require the model to cite the venue's official website/social page for every dog-policy claim, captured in `verification`. Anything unverifiable goes in the PR description as an open question, not in the content.

- `pipeline/generate.py` — takes a work queue (venue list or guide topic), drafts content via the Claude API using `pipeline/prompts/` (system prompt + style guide + few-shot examples from approved pages), writes files into `src/content/`, opens a **pull request**. Never commits to main.
- `pipeline/verify.py` — scheduled (GitHub Actions cron): finds venues with `last_verified` older than 90 days, re-checks official sources, opens update PRs (including "policy changed" and "permanently closed" cases).
- **Sign-off = PR merge.** Merge to main triggers Cloudflare Pages deploy. This is the entire approval workflow — build nothing else for it.
- **Improvement loop** (the "gets better over time" requirement):
    - `pipeline/prompts/EDITORIAL_LOG.md` — every human correction made during PR review gets a one-line entry; the generation script injects recent entries into future prompts.
    - Style guide and prompts are versioned files, edited as patterns emerge — treat prompt changes like code changes.
    - Monthly: pull top/bottom pages from analytics into a content queue file (`pipeline/queue.yaml`) so generation effort follows demand.

## 5. Site structure & SEO

URL scheme (umbrella brand, city sections):

```
/                                  # brand home: city picker + flagship guides
/tahoe-city/                       # city hub
/tahoe-city/venues/{slug}/
/tahoe-city/{category}/            # e.g. /tahoe-city/dog-friendly-restaurants/
/tahoe-city/guides/{slug}/
/about/  /how-we-verify/  /editorial-policy/
```

- Category and attribute pages (e.g., off-leash, heated patios, winter-friendly) are generated **only when ≥4 venues qualify** — no thin programmatic pages.
- JSON-LD on every page: `LocalBusiness`/`Restaurant`/`LodgingBusiness` with `petsAllowed` and `amenityFeature` where applicable, `BreadcrumbList`, `FAQPage` on guides.
- XML sitemap, canonical tags, OG images (template-generated per page).
- `/how-we-verify/` is a real page explaining the verification process — it's both E-E-A-T signal and brand differentiator.
- Analytics: GA4 + Cloudflare Web Analytics.

## 6. Monetization

- **Display ads:** build an `<AdSlot>` component with reserved heights (zero CLS), lazy-loaded, placed: below-hero, mid-content (guides), end-of-content. Implement AdSense-ready but network-agnostic so a premium network (Ezoic/Mediavine-class) can be swapped in when traffic qualifies. Include `ads.txt` handling.
- **Affiliate:** `<AffiliateCTA>` component. Launch integrations: **Viator** links/widgets on activity venues and guides (product codes stored in venue frontmatter); dog-friendly lodging booking links on stay venues; gear recommendations inside relevant guides.
- **Compliance:** site-wide FTC affiliate disclosure component rendered on any page containing affiliate links; privacy policy + cookie consent (required for AdSense); disclosure page linked in footer.

## 7. Design direction

Warm, outdoorsy, trustworthy — think modern trail guide, not listicle farm. Real photography treated as a priority (owner-supplied and properly licensed only; **do not hot-link or store Google Places photos**). Venue pages lead with the dog-policy block — a scannable card showing policy, leash rules, water bowls, fee, and the "Verified" date. Mobile-first; these pages get read in parking lots. Use the frontend-design skill; avoid template-y AI aesthetics.

## 8. MVP scope (Tahoe City launch)

- City hub + 6 category hubs
- **50 venue pages** (spread across trails, beaches, restaurants/patios, lodging, activities, shops)
- **10 guides**, including: dog-friendly hikes near Tahoe City; dog beaches & lake access rules; winter in Tahoe with a dog; dog-friendly patios; where to stay with a dog; a 48-hour itinerary
- About, How We Verify, Editorial Policy, disclosure/privacy pages
- Pipeline operational end-to-end: generate → PR → merge → deploy, plus the 90-day verify cron

## 9. Build order

1. Scaffold: Astro + Cloudflare Pages, content collections with strict schemas, city config system
2. Components: venue card, dog-policy block, guide layout, AdSlot, AffiliateCTA, disclosure, verified badge
3. Pipeline: prompts + style guide, `generate.py`, PR automation, `verify.py` + cron
4. Seed batch: run pipeline for first 15 venues + 3 guides → owner reviews PRs (this review calibrates the style guide before scaling to full MVP scope)
5. SEO + monetization wiring: JSON-LD, sitemaps, OG images, ad slots, affiliate components, consent/disclosures
6. `docs/RUNBOOK.md`: how to add a venue, run the pipeline, review PRs, add a new city

## 10. Definition of done for v1

- Lighthouse ≥95 performance/SEO on venue and guide templates
- A new city can be added with: one city config file + pipeline runs — no component edits
- Every published venue has complete `dog_policy` and `verification` fields
- No AI-generated venue fact without a recorded source