# Spec — The Dog-Eared Index, v1

Companion to `dog_friendly_city_guide_project_spec.md` (repo root) and
`docs/kindle-lake-tahoe.md`.
Adds a town-level, fact-composed dog-friendliness index to the content graph.

**What this is:** arithmetic over verified conditions. Every component is a
countable fact with a citable source. **What this is not:** opinion, review
sentiment, or a venue score. Venues never receive a scalar; they render facets
(dog-policy chips + sort keys) only. The index's public tagline, printed on the
methodology page verbatim: *"This counts what exists; it doesn't know your dog."*

---

## 1. Structure

Nine components in four pillars. Each component scores 0–100 against **absolute
bands** (never percentiles — scores must be computable for the first town and
stable as coverage grows), then the composite is the weighted sum, 0–100,
displayed as an integer.

| Pillar | Component | Weight |
|---|---|---|
| Hospitality (30) | Patio share | 15 |
| | Indoor welcome | 5 |
| | Lodging share | 10 |
| Access (35) | Water access | 15 |
| | Trail access | 12 |
| | Off-leash space | 8 |
| Rules (15) | Ordinance regime | 15 |
| Practical (20) | Emergency vet | 10 |
| | Heat risk | 10 |

Town pages display the composite, the four pillar subtotals, and the full
component table with each value, its band score, and its `verified` date.
Showing the work is the product.

## 2. Component definitions and bands

### 2.1 Patio share — weight 15
Share of cataloged food/drink venues with **verified dog-allowed outdoor
seating**. Denominator: all food/drink venues in the town's catalog (a town
where patios don't exist is genuinely harder to visit with a dog; climate is
not double-counted — heat risk measures weather, this measures seating).
Source: venue records (auto-fresh; recomputed on every venue change).

| Share | Score |
|---|---|
| ≥ 50% | 100 |
| 35–49% | 80 |
| 25–34% | 60 |
| 15–24% | 40 |
| 5–14% | 20 |
| < 5% | 0 |

### 2.2 Indoor welcome — weight 5
Share of retail / taproom / tasting-room venues verified dog-allowed **inside**.
Rare and high-signal, hence the low thresholds. Source: venue records.

| Share | Score |
|---|---|
| ≥ 25% | 100 |
| 15–24% | 75 |
| 8–14% | 50 |
| 3–7% | 25 |
| < 3% | 0 |

### 2.3 Lodging share — weight 10
Share of cataloged lodging properties that accept dogs in any room class.
Fees, weight limits, and count limits are **recorded and displayed as data,
never scored**. Source: venue records.

| Share | Score |
|---|---|
| ≥ 60% | 100 |
| 45–59% | 80 |
| 30–44% | 60 |
| 15–29% | 40 |
| 5–14% | 20 |
| < 5% | 0 |

### 2.4 Water access — weight 15
Count and seasonality of **legal dog water-entry points** within the town's
15-minute isochrone (§4). A legal entry point is a named, publicly accessible
shoreline or bank segment where the managing agency's published rule allows
dogs in the water (leashed or off). Source: land-manager rules (USFS, state
parks, county/municipal parks), each point carrying its own citation.

| Condition | Score |
|---|---|
| ≥ 3 points, year-round | 100 |
| ≥ 3 seasonal, or 2 year-round | 80 |
| 2 seasonal, or 1 year-round | 60 |
| 1 seasonal | 40 |
| Legal wading/bank access only (no swim point) | 20 |
| None | 0 |

### 2.5 Trail access — weight 12
Miles of dog-allowed trail within the 15-minute isochrone, from land-manager
GIS layers filtered by published dog rules. Wilderness-area leash rules count
as allowed; dog-prohibited trails (e.g., many NPS trails) excluded.

| Miles | Score |
|---|---|
| ≥ 100 | 100 |
| 50–99 | 85 |
| 25–49 | 70 |
| 10–24 | 50 |
| 3–9 | 30 |
| 1–2 | 15 |
| < 1 | 0 |

### 2.6 Off-leash space — weight 8
Designated off-leash acreage (parks, areas, beaches) within town limits or a
10-minute isochrone. Source: municipal/county park records.

| Condition | Score |
|---|---|
| ≥ 20 acres, or any designated off-leash beach | 100 |
| 5–19.9 acres | 75 |
| 1–4.9 acres | 50 |
| Fenced run under 1 acre | 25 |
| None | 0 |

### 2.7 Ordinance regime — weight 15
A rubric over the actual municipal/county code (and state law where it
controls). Start at 50 points; apply modifiers; floor 0, cap 100. Every
modifier cites the code section it derives from.

| Modifier | Points |
|---|---|
| Patio dining explicitly permitted by state or local rule | +20 |
| Any voice-control / off-leash-under-command areas in code | +15 |
| No shoreline dog ban at the primary shoreline, or a designated dog beach exists | +15 |
| Seasonal ban at the primary shoreline | −10 |
| Year-round ban at the primary shoreline | −25 |
| Breed-specific legislation in force | −40 |

Standard leash laws are the assumed baseline and score no modifier. BSL is the
only component fact important enough to also surface as a labeled flag on the
town page independent of the score.

### 2.8 Emergency vet — weight 10
Drive time from town center to the nearest 24/7 or after-hours emergency
veterinary hospital (verified listing with hours evidence).

| Minutes | Score |
|---|---|
| ≤ 15 | 100 |
| 16–30 | 80 |
| 31–45 | 60 |
| 46–60 | 40 |
| 61–90 | 20 |
| > 90 | 0 |

### 2.9 Heat risk — weight 10
Days per year with a normal high ≥ 90°F (pavement-burn proxy), from NOAA
1991–2020 climate normals for the nearest station. Cold is deliberately not
penalized — v1 takes the position that heat is the acute paw hazard; revisit
in v2 if reader feedback argues otherwise, via the versioning process (§6).

| Days ≥ 90°F | Score |
|---|---|
| ≤ 5 | 100 |
| 6–15 | 85 |
| 16–30 | 70 |
| 31–60 | 50 |
| 61–100 | 30 |
| > 100 | 10 |

## 3. Excluded on principle

Review sentiment, staff friendliness, venue quality, fee levels, "vibe,"
anything scraped without a citable source, and any venue-level scalar. If a
future component can't be phrased as "count of X per published rule Y," it
doesn't enter the index.

## 4. Geometry definitions

- **Town center:** the lat/lng already in the town record.
- **15-minute isochrone:** drive-time polygon computed once per town via
  OpenRouteService (or OSRM), stored with computation date. Fallback if
  routing is unavailable: 10 road-mile radius, flagged as `geometry: fallback`.
- Recompute isochrones only on major road-network changes or v-bumps.

## 5. Data model and computation

```
data/towns/<slug>/index.yaml
  version: index-v1
  components:
    patio_share:
      value: 0.41            # measured quantity
      score: 80              # band score (computed, stored for audit)
      sources: [{url, method, date}]
      last_verified: 2027-03-02
    ...
  composite: 78              # computed; provisional flag if 7–8 components
pipeline/index/
  compute.py                 # yaml -> scores -> composite; fails on band drift
  test_compute.py            # golden-file tests, every band edge
  zones.py                   # OSM polygons -> zones.geojson for the map
  sensitivity.py             # PLANNED, not built — see §6 rule 3
  isochrone.py               # PLANNED, not built
```

- Hospitality components derive **live from venue records** — they are never
  hand-entered and are always as fresh as the catalog.
- All other components re-verify on a **180-day cycle** (ordinances and GIS
  move slower than venues; the site's venue cycle stays 90).
- `compute.py` recomputes band scores from stored values on every run and
  fails if a stored score disagrees — bands live in code, values live in data.

## 6. Publication rules

1. **Publish gate:** composite appears only when ≥ 7 of 9 components carry
   verified data. At 7–8, weights renormalize over available components and
   the score is labeled **"provisional (7/9 components verified)"**. Never
   impute; missing is missing. A town without an index is the marketing.
2. **Versioning:** bands and weights are frozen as `index-v1`. Any change
   bumps the version, logs rationale in `prompts/EDITORIAL_LOG.md`, and
   triggers recomputation of every published town so cross-town comparisons
   are always same-version.
3. **Sensitivity requirement (PLANNED — `sensitivity.py` is not yet
   built):** before any weight change, run a ±20% weight perturbation
   across all scored towns. If it flips town rankings, the flagged
   components are too correlated; prune or merge before publishing. Until
   the script exists, weight changes require the same analysis by hand,
   logged in `prompts/EDITORIAL_LOG.md`.
4. **Methodology page:** public, complete — every band table above, the
   tagline, the exclusion list, and a changelog. A downloadable CSV of all
   published town indexes (with component values) is the press/link asset.
5. **Book integration:** the index prints as a semi-durable fact under the
   book spec's §6 rules — composite + pillar bars, `computed <date>` stamp,
   QR to `/go/index`.
6. **Independence line:** the methodology page states that advertising and
   affiliate relationships exist at the venue layer and that no index
   component measures venues individually — the structural answer to
   pay-to-play suspicion, stated before anyone asks.

## 7. Build order

1. Schema + `compute.py` with bands as code and a golden-file test per band
   edge.
2. Tahoe City end-to-end: hospitality components from live venue records;
   hand-verify the six external components with citations.
3. `sensitivity.py` across Tahoe City + two neighbor towns as soon as they
   reach 7/9.
4. Methodology page + town-page component table in `apps/web`.
5. CSV export endpoint.

## 8. Definition of done

Tahoe City publishes a full 9/9 index with every component citing a source;
`test_compute.py` and `compute.py --check` run in CI (`ci.yml`, pipeline
job); the methodology page renders the
band tables from the same code that scores (no copy drift); and deleting any
component's data flips the town to a correctly labeled provisional state
without human intervention.