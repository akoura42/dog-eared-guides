# CITY PLAYBOOK — the systematic path from zero to a launched city

The repeatable recipe, proven end-to-end on Tahoe City (36 venues, 9/9
index, zones, emergency layer). Work the phases in order; each phase's
output is the next phase's input. Companion docs: `RUNBOOK.md` (daily
operations), `dog-eared-index.md` (index spec), `monetization.md`,
`voice.md` (all copy).

Everything here is data-driven — launching a city touches `data/` and
`content/` almost exclusively. The only code files a new city may touch:
`apps/web/src/lib/areas.ts` (area aliases) and the agency-domain list in
`apps/web/src/lib/logos.ts`.

## Phase 0 — city config (`data/cities/<slug>.yaml`)

Copy `tahoe-city.yaml` as the template. Required before anything else:

- `name/slug/state/geo` — geo is the town center; it anchors the map, the
  index isochrone, and drive-time measurements. Pick the actual center.
- `hero` + `intro` — voice.md applies. The intro states the regulatory
  landscape in one breath (whose rules apply where).
- `regulations` — every entry cites `source_url`. The research set, in
  the order that worked: (1) county/municipal animal code (leash / at
  large definition — this also feeds the index's ordinance rubric),
  (2) the parks agency's beach/park rules (TCPUD-equivalent: city parks
  dept, county parks), (3) state parks district dog orders if any units
  sit in town, (4) USFS/BLM rules if federal land abuts, (5) transit
  agency pet policy (fixed-route + microtransit — almost no guide
  verifies this; it's cheap distinction).
- `seasonal_notes` — winter bans, HAB/water advisories, giardia. Facts
  with jurisdictions, not advice.
- `emergency` block — see Phase 6; can land later but the page and
  pocket card render only when present.
- `categories` — full list; hubs only generate at ≥4 venues so listing
  extras is harmless.
- `launched: false` until Phase 9.

## Phase 1 — discovery (ledger fill)

```
python pipeline/discover.py --city <slug>     # OSM sweep → ledger candidates
python pipeline/ledger.py stats               # coverage dashboard
```

Large cities return hundreds of candidates. Do NOT drain the ledger
linearly — rank batches: (1) the dog-famous anchors (breweries, dog
bars, signature parks), (2) each category to ≥4 for hub generation,
(3) demand-driven from search data monthly. Small towns: just work the
whole pool like Tahoe (77 candidates → 36 published, 23 unverifiable).

## Phase 2 — venues (batches through the ledger)

```
python pipeline/generate.py --from-ledger <slug>   # drafts a batch → PR
```

Per-venue rules beyond STYLE_GUIDE.md, learned the hard way:

- **Tiers**: official source → tier 1; ≥2 independent linkable mentions
  → tier 2 (labeled); neither → ledger `unverifiable`, not published.
- **`cuisines`** on eat/drink venues: only labels the venue uses for
  itself ("gourmet comfort food" → Comfort food). Never inferred.
- **`season`** (structured MM-DD): only when the venue publishes real
  dates. "Closes at first snow" stays free-text in `seasonal` — no
  computed badge from fuzz.
- **`tags`**: `water-access` on venues that are cited legal water-entry
  points (feeds the index filter), `emergency-vet` on vet venues (routes
  them to the map's Emergency layer instead of regular pins, and places
  the insurance module).
- **Similar-name trap**: rival businesses share names (two Truckee raft
  companies with different dog policies). Never mix facts across
  operators; verify identity by address before citing anything.
- **Out-of-town venues** (nearest daycare, ER vet) are allowed in the
  catalog; the map's initial frame self-tunes to the venue distribution
  (90th percentile +15%), so outliers don't wreck the opening view.
  `map_frame_km` in the city config overrides when the distribution
  fools the formula (e.g., twin clusters).

## Phase 3 — geo layers (zones + trails + areas)

1. `data/towns/<slug>/zones.yaml` — curate the dog-policy zones: no-dogs
   beaches, the off-leash park, leashed day-use areas, restricted parks.
   POLICY COMES FROM VERIFIED RECORDS, never OSM tags. Per zone: `near`
   coords, `osm_name`, `max_match_m` for big parks (nearest-vertex
   matching), `approx_radius_m` fallback when OSM has no polygon (renders
   a dashed circle), `venue` link when a catalog page exists.
   `trails:` config draws the dog-legal trail lines (cycleway + named
   paths), with `exclude_zone_ids` dropping trails inside no-dog parks.
2. `python pipeline/index/zones.py <slug>` — fetches geometry from
   Overpass, simplifies, computes acreage/mileage, writes
   `zones.geojson`. Rerun any time; watch the MISSING/REJECTED lines —
   a REJECTED match is usually a same-named place elsewhere (good) or a
   bad `near` guess (fix the yaml).
3. Area aliases — `lib/areas.ts`: the Area filter derives from venue
   neighborhoods; add aliases collapsing sub-spots into the areas locals
   navigate by, and null-mapping street descriptors. Unknown tokens pass
   through, so this can trail the content. Big cities NEED this pass —
   neighborhood taxonomy (NoDa, South End, Plaza Midwood…) is how
   readers filter a large catalog.

## Phase 4 — the Dog-Eared Index (`data/towns/<slug>/index.yaml`)

Copy the Tahoe skeleton; hospitality components fill themselves from
venue records. The six external components, with the verification
recipes that worked:

| Component | Recipe |
|---|---|
| Water access | Managing-agency published rules per entry point (parks dept FAQ, state-parks order, USFS). Count only points with a rule allowing dogs in the water; year-round only if closure-free. |
| Trail access | Overpass sum (path + non-sidewalk footway + cycleway) in the radius, minus state-park trail miles; `geometry: fallback` flag until real isochrones. Conservative haircuts are fine when the band has margin. |
| Off-leash | Official park page for existence/size; directories are tier-2 for fenced/off-leash claims; band conservatively when acreage is unpublished. No OSM-polygon acreage unless the polygon is verifiably the park. |
| Ordinance | Read the actual code: state patio statute (CA: HSC 114259.5), shoreline rules at the PRIMARY shoreline, voice-control provisions, BSL. Each modifier cites its section. |
| Emergency vet | Local clinic's referral page names the ER chain → verify each ER's hours on ITS OWN site (tier the ones that block readers) → OSRM drive time from town center to the nearest verified 24/7. |
| Heat risk | NOAA 1991–2020 normals, nearest station, `ANN-TMAX-AVGNDS-GRTH090` via the NCEI data API; confirm station identity/coords. |

Then: `python pipeline/index/compute.py <slug>` (+ `--check` in CI;
`test_compute.py` must stay green). Composite publishes at ≥7/9,
provisional to 8/9. Never impute — a missing component is the honest
state and renders as such.

## Phase 5 — emergency block + pocket card

City-config `emergency:` — `er_vets`, `poison`, `lost_found`; every
contact carries `note` + `source_url`; add `lat/lng` only for locations
someone drives to (they become the map's red-cross Emergency layer;
phone-first contacts stay list-only). Research recipe: local vet's
after-hours referral page → each ER's own site → county page naming the
contracted shelter → ASPCA poison control. `/{slug}/emergency/` and
`/{slug}/pocket-card/` render automatically once the block exists.

## Phase 6 — logos and photos

```
python pipeline/fetch_logos.py <slug>     # idempotent; delete a file to refetch
```

Card tile priority: business's own logo → licensed photo → agency
favicon → text. Add new agency domains to `AGENCY_DOMAINS` in
`lib/logos.ts` so photos beat repetitive government favicons. Photos:
licensed/owner-supplied only, credit required, set in venue frontmatter.

## Phase 7 — monetization pass

Per `monetization.md`. City-launch checklist: identity-verify Booking.com
property URLs for each lodging venue (match street address before
linking; campgrounds/rec.gov have no programs — link direct);
insurance module places itself (emergency-vet tag + fee lodging); Viator
only when the product is verifiably the SAME operator.

## Phase 8 — QA gate (all must pass)

```
cd apps/web && npx astro check && npx astro build   # 0 errors
python pipeline/index/compute.py <slug> --check
python pipeline/index/test_compute.py
```

Then LOOK at the pages (screenshot, both map modes, mobile width):
initial map frame shows the town core; toolbar counts sane; zones/trails
where expected; Emergency toggle refits correctly; index block matches
`index.yaml`; pocket card prints on one sheet.

## Phase 9 — launch

Flip `launched: true` → the city joins the homepage map/state list,
header menu, sitemap, OG images, CSV export. Commit style: content
batches as `content: <n> drafted <city> venues from ledger batch <k>`;
features/data as themselves. Merging the PR is the approval step.

## Small town vs. big city — what actually changes

Nothing structural; everything is data-scaled. The knobs that matter at
Charlotte scale:

- **Ledger discipline** (Phase 1 ranking) replaces "drain the pool".
- **Areas taxonomy** becomes the primary navigation — invest early.
- **Hubs**: with hundreds of venues, category and attribute hub pages
  (≥4 threshold) generate en masse — they're the SEO surface; make sure
  category coverage is even instead of 200 restaurants and 3 trails.
- **Index denominators** get robust automatically (shares over hundreds
  beat shares over nine); external components get EASIER (a 24/7 ER
  in-town scores 100 where Tahoe scored 40).
- **Map payload**: markers JSON grows linearly. Fine into the low
  hundreds; past ~300 venues move the payload to a fetched asset and
  consider marker clustering — both are noted, neither is built. Don't
  build them before a city needs them.
- **Zones**: city parks department + county + state parks replace the
  utility district; the yaml recipe is identical.
