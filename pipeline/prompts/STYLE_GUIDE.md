# Style guide (versioned — edit as patterns emerge, treat like code)

## Voice

- Warm, direct, practically minded. A knowledgeable local friend, not a
  listicle farm. Modern trail guide energy.
- Written from the dog owner's point of view: parking, shade, crowds, water,
  what it's actually like to be there with a dog.
- Honest about downsides and unknowns. "Call ahead to confirm X" beats
  pretending to know. If a beach bans dogs, say so plainly — accuracy is the
  brand.
- No filler ("nestled in the heart of"), no exclamation-mark tourism copy,
  no "paws-itively" puns.

## Venue files (Markdown)

Path: `src/content/venues/<city-slug>/<venue-slug>.md`

Frontmatter (all fields; use `null` where unknown, never invent):

```yaml
name: <string>
city: <city-slug>
category: eat | drink | stay | trail | beach | activity | shop | pet-supply | daycare | services
neighborhood: <string | null>
address: <street address>
lat: <number>
lng: <number>
phone: <string | null>
website: <url | null>
dog_policy:
  allowed: indoors | patio_only | outdoor_areas | grounds_only | no
  leash_required: <bool | null>
  water_bowls: <bool | null>
  size_or_breed_restrictions: <string | null>
  fee: <string | null>            # e.g. "$40 one-time pet fee per visit, plus tax"
  notes: <string | null>          # quote official policy language where possible
seasonal: []                      # list of strings; critical for Tahoe
verification:
  last_verified: YYYY-MM-DD       # today's date
  method: official_website | phone | in_person | other
  source_url: <url>               # REQUIRED — where the policy was verified
affiliate: null                   # or {viator_product_code, viator_url, booking_url}
tags: []                          # e.g. [winter-friendly]
summary: <one sentence, <160 chars, for cards and meta description>
image: null
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
