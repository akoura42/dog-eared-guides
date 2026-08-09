# Style guide (versioned — edit as patterns emerge, treat like code)

## Voice

Voice rules live in `docs/voice.md`, which is injected alongside this guide
and is authoritative — including its ban on advice imperatives: never write
"call ahead to confirm"; state the condition instead ("the website doesn't
say whether…", "as of August 2026 the posted policy is…"). In brief:

- Warm, direct, practically minded. A knowledgeable local friend, not a
  listicle farm. Modern trail guide energy.
- Written from the dog owner's point of view: parking, shade, crowds, water,
  what it's actually like to be there with a dog.
- Honest about downsides and unknowns. If a beach bans dogs, say so plainly —
  accuracy is the brand.
- No filler ("nestled in the heart of"), no exclamation-mark tourism copy,
  no "paws-itively" puns.

## Venue files (Markdown)

Path: `src/content/venues/<city-slug>/<venue-slug>.md`

Frontmatter (all fields; use `null` where unknown, never invent). The
schema is STRICT: an unknown or misplaced key fails the build — every field
goes exactly where shown, at exactly this nesting:

```yaml
name: <string>
city: <city-slug>
category: eat | drink | stay | trail | beach | activity | dog-park | shop | pet-supply | daycare | services
neighborhood: <string | null>
address: <street address>
lat: <number>
lng: <number>
phone: <string | null>
website: <url | null>
dog_policy:
  allowed: indoors | patio_only | outdoor_areas | grounds_only | "no"
                                  # "no" ALWAYS quoted (bare no = YAML bool).
                                  # Verified no-dogs venues DO get pages —
                                  # see SYSTEM.md "Verified NO is publishable"
  vaccinations_required: []       # NESTED HERE, never top-level. Proof the
                                  # venue itself requires (daycare, dog parks,
                                  # dog bars), named as the venue states them
  leash_required: <bool | null>
  water_bowls: <bool | null>
  size_or_breed_restrictions: <string | null>
  fee: <string | null>            # e.g. "$40 one-time pet fee per visit, plus tax"
  notes: <string | null>          # quote official policy language where possible
cuisines: []                      # eat/drink only; the venue's own labels for
                                  # itself ("pizzeria", "beer garden") — never inferred
seasonal: []                      # list of strings; critical for seasonal towns
season: null                      # or {opens: MM-DD, closes: MM-DD} — ONLY when
                                  # the venue publishes actual dates; fuzzy
                                  # seasons stay prose in `seasonal`
verification:
  last_verified: YYYY-MM-DD       # today's date
  method: official_website | phone | in_person | other
  source_url: <url>               # REQUIRED — where the policy was verified
  level: official | reported      # official = tier 1 (official source confirms).
                                  # reported = tier 2: NO official source exists
                                  # and ≥2 independent linkable visitor mentions
                                  # back the claim; the page shows it as
                                  # unconfirmed by the venue
  mentions: []                    # tier 2 only, ≥2 entries required:
                                  # {source_url, note, seen: YYYY-MM-DD}
menu: null                        # see Menus section below
field_notes: null                 # HUMAN-EDITOR-ONLY — never write this field;
                                  # it is first-person claimed experience
affiliate: null                   # or {viator_product_code, viator_url, booking_url}
tags: []                          # e.g. [winter-friendly]
google_place_id: null             # optional; only the ID itself, never other
                                  # Google Places data
summary: <one sentence, <160 chars, for cards and meta description>
image: null                       # human-editor-set; licensed only. When set,
                                  # image_alt + image_credit are required
image_alt: null
image_credit: null
image_credit_url: null
```

- Body: **200–400 words** of genuinely useful, specific editorial. Lead with
  what the dog policy means in practice, then the on-the-ground details.
- Quote official policy language verbatim in `dog_policy.notes` when you have it.
- Cross-reference other venues in the same city naturally ("five minutes from
  the 64-Acres trailhead") — no forced link stuffing.

## Menus (eat/drink venues)

When a venue's own website publishes a readable menu, capture it in
frontmatter so dish search works:

```yaml
menu:
  source_url: <url of the official menu page/PDF (archive.org capture of the official site is acceptable)>
  current_url: null               # the venue's LIVE menu page for readers, when
                                  # source_url is an archive capture
  last_verified: YYYY-MM-DD
  items:
    - "SECTION: Starters"          # section headers use the SECTION: prefix
    - Buffalo Wings
    - Spaghetti & Meatballs        # item names exactly as printed — never invented or normalized
```

- Only items actually readable on the official menu. No inference from
  cuisine ("Italian, so probably spaghetti" is exactly what this feature
  exists to avoid). No third-party menu sites (Yelp/DoorDash).
- If no official menu is readable, set `menu: null` and note it in open
  questions.

## Guide files (MDX)

Path: `src/content/guides/<city-slug>/<guide-slug>.mdx`

- **1,200–2,500 words.** Itineraries, best-of roundups, seasonal guides.
- Frontmatter: `title`, `city`, `description`, `date`, `updated: null`,
  `faqs` (3–5 question/answer pairs, each answer self-contained and sourced),
  `has_affiliate_links` (bool), `image: null`.
- Embed venue cards with `<VenueEmbed city="..." slug="..." />` instead of
  restating venue data — venue facts live in one place.
- Rules/regulations sections must name the enforcing agency and match the
  city config's sourced regulations.

## Things editors keep fixing (see EDITORIAL_LOG.md)

The generation script injects recent editorial-log entries into the prompt.
When an entry conflicts with this guide, the log entry wins — then this guide
gets updated to match.
