# Build Spec — Dog-Eared Guides: Lake Tahoe (2027 Edition)

Handoff document for Claude Code. This adds a **book renderer** to the existing
Dog-Eared Guides monorepo. The book is not a new content effort: it is a second
build target of the same verified content graph that powers dogearedguides.com.
If a fact isn't in the site's data layer with a verification record, it does not
exist to the book.

Companion to `dog_friendly_city_guide_project_spec.md`. Everything in that spec's
non-negotiables (sourcing, voice, schema) applies here unchanged.

---

## 1. Goal

Produce a print-ready KDP paperback and a reflowable Kindle epub for a Lake
Tahoe regional guide — the pilot that proves the renderer before state volumes
(California = 25 towns) enter the pipeline. One command builds the whole book
deterministically from repo data:

```
make book BOOK=tahoe-2027
```

Outputs to `dist/books/tahoe-2027/`:
- `interior.pdf` — print interior, black ink, fonts embedded
- `cover.pdf` — full-wrap color cover sized to final page count
- `book.epub` — reflowable Kindle upload
- `preflight-report.txt` — pass/fail gate (see §10)

## 2. Non-negotiables (inherited + print-specific)

1. **No fact without a source.** Every venue fact in print traces to a
   `verification` record (`last_verified`, `method`, `source_url`) in the data
   layer. The renderer refuses to build otherwise.
2. **Voice is `docs/voice.md`, verbatim.** Describe the place, not the
   reader. Conditions, not conclusions. No advice. The book earns no exemption;
   chapter intros follow the same rules as venue copy.
3. **First person appears only via `field_notes`** (human-entered after real
   visits). In print these render as set-off "Field-tested" boxes carrying the
   badge glyph. Never generated.
4. **Print freshness gate:** any *volatile* fact (see §6) that appears in print
   must have `last_verified` within **60 days of the manuscript freeze date**.
   The build fails loudly on violations, listing them. Durable facts are exempt.
5. **Honesty page is mandatory** (front matter): states the edition's freeze
   date, that policies change, and that every chapter's QR code points to a
   page re-verified on a 90-day cycle.

## 3. Repo additions

```
pipeline/book/
  assemble.py        # content graph -> build/book.json (normalized intermediate)
  freshness.py       # freeze-date gate over volatile facts (imports verify.py logic)
  interior.typ       # Typst template: consumes book.json -> interior.pdf
  cover.py           # computes spine width from page count; renders cover.pdf
  epub.py            # book.json -> pandoc-ready markdown -> book.epub
  preflight.py       # §10 checks
  qr.py              # generates QR PNGs for /go/ short links
data/books/
  tahoe-2027.yaml    # the book config (below)
assets/book/
  logo/              # copies of logo-mark.svg, logo-badge.svg, lockup, fold-only
  fonts/             # Fraunces (variable), Literata (variable) — OFL, embed-safe
docs/BOOK-RUNBOOK.md # how to freeze, build, upload to KDP, and cut next edition
```

**Toolchain decision:** interior via **Typst** (deterministic, fast, real book
typography, data-driven from JSON). If Typst fights on any layout requirement
for more than a day of effort, the sanctioned fallback is WeasyPrint with a
paged-media stylesheet — record the switch in `docs/BOOK-RUNBOOK.md` with
reasons. Epub via pandoc from generated markdown; never from the PDF.

**Site-side task (cross-cutting):** implement the `/go/<slug>` short-link
redirect map in `apps/web` (a static JSON map compiled into redirects). Print
never embeds long URLs — every QR resolves `dogearedguides.com/go/<slug>?src=book2027`
so links survive site restructuring and sales attribute to the edition.

## 4. Book config — `data/books/tahoe-2027.yaml`

```yaml
book: tahoe-2027
title: "Dog-Eared Guides: Lake Tahoe"
subtitle: "City guides. Dogs allowed."
edition: "2027 Edition"
imprint: "Dog-Eared Guides"
byline: "Christopher Bryan"        # human byline; imprint is the author brand
isbn: kdp-assigned                  # pilot uses KDP ISBN; state volumes: Bowker block under imprint
trim: { width_in: 5.5, height_in: 8.5 }
interior: black-ink                 # full-color cover only; see §7
target_pages: [160, 220]
price_usd: { paperback: 18.99, kindle: 9.99 }
freeze_date: null                   # set at manuscript freeze; drives §2.4 gate
chapters:
  - slug: tahoe-city
    title: "Tahoe City"
    folds_in: [sunnyside, dollar-point]
  - slug: kings-beach-tahoe-vista
    title: "Kings Beach & Tahoe Vista"
    folds_in: [carnelian-bay]
  - slug: incline-village
    title: "Incline Village"
    folds_in: [crystal-bay]
  - slug: east-shore
    title: "The East Shore"
    folds_in: [glenbrook, cave-rock, spooner]
  - slug: zephyr-cove
    title: "Zephyr Cove"
    folds_in: [round-hill]
  - slug: stateline
    title: "Stateline"
  - slug: south-lake-tahoe
    title: "South Lake Tahoe"
    folds_in: [camp-richardson, meyers]
  - slug: west-shore
    title: "The West Shore"
    folds_in: [homewood, tahoma, meeks-bay]
  - slug: truckee
    title: "Truckee"
    gateway: true                   # rendered with an explicit off-lake label
    folds_in: [olympic-valley]
```

Chapter order is fixed (clockwise from the flagship; gateway last). A chapter
is **book-ready** when its towns jointly clear the site's density bar (≥4
verified venues per rendered category; Tahoe City at its 50-venue MVP). The
build supports `--allow-draft-chapters` for proofs, but the preflight fails a
release build if any chapter is below density.

## 5. Content assembly (`assemble.py`)

Reads the same sources as the site — venue records, MDX guides, `field_notes`
— and emits `build/book.json`:

```
{ meta, chapters: [ { slug, title, gateway, intro_mdx,
    sections: [ { kind: durable|venues|field_note|qr_callout, ... } ],
    venues: [ <full venue records incl. verification> ] } ],
  indexes: { towns, venues } }
```

Rules:
- Chapter intros come from the town's existing MDX guide content where it
  exists; gaps are generated through the standard pipeline (VOICE.md prompts,
  PR review) — **never inline in the renderer**. The renderer renders; it does
  not write.
- Venue entries render: name, address, one-line spatial anchor, dog policy,
  conditions block, seasonal notes, `verified <date>` stamp. No prices, no
  hours tables (volatile-dense; the QR carries them — see §6).
- `folds_in` towns render as labeled subsections inside the chapter, not as
  separate chapters.

## 6. Durable vs. volatile — what is allowed on paper

| Class | Examples | In print? |
|---|---|---|
| Durable | geography, town character, trail systems, leash law (county/state), water access norms, spatial anchors | Yes, freely |
| Semi-durable | venue existence, dog policy in force, seasonal patterns ("lot fills by midday in July") | Yes, with `verified <date>` stamp + §2.4 gate |
| Volatile | hours, prices, menus, event dates, temporary closures | **Never in print.** QR callout only |

Each chapter ends with a QR callout box: the pin mark, "Policies change —
this chapter's live page is re-verified every 90 days," and the QR to
`/go/<chapter-slug>`. This is the book's answer to staleness and its funnel to
the site in one element.

## 7. Design spec

- **Trim 5.5" × 8.5"**, no interior bleed. Margins: outer 0.5", top 0.6",
  bottom 0.65", **gutter 0.75"** (recompute per KDP table if page count > 300).
- **Black-ink interior** on white. The brand's ink-on-paper aesthetic is
  deliberately one-color-native: green elements render as solid black or a
  tint ≥ 25% gray. Full color appears only on the cover. (Color interior at
  this page count destroys unit margin; this is a costing decision, not a
  style preference.)
- Type: **Fraunces** (display/heads, the logo instance axes: wght 600, SOFT 60)
  and **Literata** (body, ~10.5/14.5). Both OFL — embedding in the PDF is
  license-clean. Hyphenation on, widow/orphan control on.
- Running heads: chapter title outer, book title inner. Folios bottom-outer.
- "Field-tested" boxes: rule-framed, badge glyph at 10 mm, field note set in
  Literata italic. Never restyle the note's content.
- Maps (pilot scope): one lake overview map (chapter locator) + one simple
  per-chapter locator strip. Grayscale, generated from town lat/lngs already
  in data — schematic dots-and-shoreline, not cartography. Full street maps
  are **out of scope** for the pilot; note as a 2028-edition candidate.
- Front matter: half-title, title, copyright/colophon (fonts, edition, imprint,
  dogearedguides.com), **honesty page** (§2.5), how-to-use spread (explains
  dog-policy line format, `verified` stamps, QR system, Field-tested badge),
  leash-law overview (Placer / El Dorado / Washoe / Douglas / Carson City in
  plain condition statements), lake overview map.
- Back matter: "About Dog-Eared Guides" page (lockup + URL + one paragraph in
  house voice), town index, alphabetical venue index (auto-generated),
  affiliate disclosure page **only if** any QR target carries affiliate links.
- Cover (`cover.py`): full-wrap at 300 dpi + 0.125" bleed. Front: badge or
  lockup on PAPER `#F4EEDF` field, title in Fraunces, "2027 Edition" flag.
  Spine: computed width = pages × 0.002252" (KDP white paper); spine text only
  if width ≥ 0.25". Back: tagline, three-sentence description in house voice,
  QR to `/go/book`, ISBN box clear zone. Colors: INK `#20302A`, GREEN
  `#2F6047`, PAPER `#F4EEDF` only.

## 8. Epub (`epub.py`)

Reflowable, not fixed-layout. Same `book.json`; venue entries become definition
lists; QR callouts become plain hyperlinks (same `/go/` URLs, `?src=kindle2027`).
Cover JPG derived from the front panel. No fonts embedded (Kindle ignores
them); the voice survives without the typography.

## 9. Build order

1. `/go/` redirect map in `apps/web` + `qr.py` (site task first — everything
   downstream references the slugs).
2. `assemble.py` → `book.json` against current Tahoe City data; fixture data
   for not-yet-dense chapters behind `--allow-draft-chapters`.
3. `interior.typ` — render the Tahoe City chapter alone to proof typography;
   iterate against a printed sample (paper kills layouts screens forgive).
4. `freshness.py` gate + `preflight.py`.
5. `cover.py` with live page count.
6. `epub.py`.
7. `docs/BOOK-RUNBOOK.md` — freeze → build → KDP upload → proof order →
   release; plus the annual-edition procedure (bump edition, re-freeze,
   rebuild — the content graph does the rest).

## 10. Preflight (release build fails unless all pass)

- Page count within `target_pages`; final count even.
- All fonts embedded and subset (verify with pikepdf); PDF has no RGB objects
  in the interior.
- Every printed volatile-class string caught by lint = build error (§6 table
  drives a denylist: `$`, "am–", "pm", "open ", "closed Mondays" patterns —
  tune the lint, keep it loud).
- Every §2.4 semi-durable fact within the 60-day window of `freeze_date`.
- Every QR decodes (pyzbar) and its `/go/` slug exists in the redirect map;
  live HTTP check returns 301 to a 200.
- Every chapter at density, or build was explicitly `--allow-draft-chapters`
  (release mode rejects the flag).
- Spine width recomputed from the final PDF's page count matches `cover.pdf`.

## 11. Out of scope (pilot)

Street-level maps; audiobook; hardcover; non-Tahoe chapters; any new prose
written outside the standard pipeline+PR flow; ads of any kind inside the book;
fixed-layout epub.

## 12. Definition of done

`make book BOOK=tahoe-2027` runs clean on a machine with Typst + pandoc
installed, preflight passes in release mode, a KDP proof copy has been ordered
from the artifacts without manual file edits, and the runbook lets a future
session cut the 2028 edition without reading this spec.