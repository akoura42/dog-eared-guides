# Monetization — reference and sequencing

Status doc, 2026-08-08. Strategy context: build Tahoe City to completion,
then replicate to other cities. Monetize depth before traffic.

## The constraint that governs everything

The moat is verified trust. The index spec (§6.6) already states the
rule publicly: advertising and affiliate relationships exist at the
venue layer only, nothing influences listings or scores, and the
methodology page says so before anyone asks. Every idea below stays
inside that line — the moment a reader suspects pay-to-play, the "we
checked" positioning collapses. Affiliate modules are always labeled
(`AffiliateDisclosure` renders wherever an `AffiliateCTA` appears), and
voice rules apply to monetized copy: state conditions, never "you'll
want."

## Tier 1 — ready now (works at low traffic, compounds)

1. **Dog-friendly lodging affiliate.** The highest-intent commercial
   query in the niche. Rails: `affiliate.booking_url` in the venue
   schema, `AffiliateCTA kind="lodging"` already rendered by the venue
   template, `/disclosure/` page live. Verified fee / size-limit /
   room-class data beside a "Check rates" button is a conversion story
   OTA pages can't match. Program: Booking.com Affiliate Partner
   (aid parameter), Expedia/Travelpayouts as alternates, BringFido
   partnership as the niche play. Campgrounds (recreation.gov,
   ReserveCalifornia) have no affiliate programs — link direct, no
   commission, keep the reader served.
2. **Pet insurance on emergency content.** The emergency-vet page's
   honest message is "the ER is an hour away in Reno" — the one context
   where insurance referral ($15–40/lead; Embrace, Lemonade, Healthy
   Paws via affiliate networks) is genuinely relevant. One labeled
   module on emergency-vet venue pages and high-fee lodging pages.
3. **The book.** `docs/kindle-lake-tahoe.md` is the full spec: KDP
   paperback + epub rendered from the same verified content graph, index
   included. Monetizes depth, not traffic; regional-gift-shop shelvable;
   every copy carries a QR back to the site. Also validates the renderer
   before state volumes. Biggest build item, most defensible product.
4. **Activities affiliate.** `viator_product_code` / `viator_url`
   already in schema. Dog-friendly boat rentals and tours exist in
   Tahoe. Modest revenue, near-zero marginal effort during content
   passes.
5. **Email capture now, monetize later.** The 90-day re-verification
   engine produces unique change data: "what changed for dogs in Tahoe
   this month" (policy flips, seasonal closures, the Nov 1 ski-trail
   ban). Free newsletter; builds the audience that makes the book launch
   and each new city cheaper. Sponsorship revenue at scale.

## Tier 2 — at traffic thresholds

6. **Display ads, premium track only.** `AdSlot` placements exist.
   Sequence: Journey by Mediavine at ~10k sessions/mo → Mediavine or
   Raptive at ~50k (travel RPMs $20–40, 5–10× AdSense). Until then keep
   slots sparse and never adjacent to dog-policy blocks.
7. **Contextual gear modules.** Chewy / REI / Amazon tied to conditions
   the pages already state (life jackets for lake days, paw wax when the
   winter pages say the pavement freezes). Labeled, voice-compliant.

## Tier 3 — at multi-city scale

8. **The Dog-Eared Index as a licensable data product.** Once 20+ towns
   carry same-version, sourced, CSV-exportable scores, this is Walk
   Score for dogs — licensable to relocation tools, real-estate sites,
   travel platforms. The show-your-work methodology page is what makes
   it licensable. Action now: none except version discipline; the asset
   accrues as towns publish.
9. **State book volumes** (California = 25 towns per the book spec) and
   **labeled non-endorsement sponsorships** (regional vet group on the
   newsletter) once audience justifies.
10. **Merch** — brand play, not revenue. Print-on-demand link from the
    About page using `images/logo_tshirt/`; set and forget.

## Sequencing

Now: lodging affiliate (rails exist — see below), insurance module,
email capture. Next big build: the book. At 10k sessions: Journey ads.
Long game: the index as licensed data.

## Lodging affiliate — implementation notes

- Affiliate wrapping is centralized in `apps/web/src/lib/affiliate.ts`:
  Booking.com URLs get the `aid` appended at render when
  `BOOKING_AFFILIATE_AID` is set in the environment; unset, links render
  unwrapped (site works, no commission). Non-Booking URLs pass through
  untouched, so a venue's own booking engine can live in the same field.
- To activate: join the Booking.com Affiliate Partner Programme, put the
  aid in `BOOKING_AFFILIATE_AID` at build time. That's the whole switch.
- `affiliate.booking_url` should point at the property's Booking.com
  page when one exists, else the property's own booking page (direct,
  no commission, still useful). Verify the property identity before
  linking — wrong-property links burn trust faster than no link.
