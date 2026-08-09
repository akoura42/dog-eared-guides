# Research craft — verifying dog policies in practice

The tier *contract* lives in RUNBOOK.md and the venue schema. This is the
*methodology*: the tests and workarounds that make the contract executable
on a real city, learned the hard way across Tahoe City and Charlotte. Add
to it as new patterns emerge — this file is how the craft survives a
change of operator or machine.

## The independence test (tier 2's load-bearing rule)

Two mentions only count as two when they have separate origins. Shared or
near-shared phrasing means one origin laundered through aggregators — one
Google review routinely reappears on five "sources." BringFido rows are
mirrored wholesale across directory sites; N copies of the same row are
one mention. Aggregator *attributes* are never mentions at all: the
Google/Yelp/OpenTable "dogs allowed" checkbox, AI-generated summaries, and
Roadtrippers-style tags are feed data with no observable origin. If you
can't tell WHO observed the policy and WHEN, it isn't a mention.

## Blocked and unreadable sites

- A 403 or TLS/handshake error does not mean the business is gone. Try
  `https://r.jina.ai/<url>` — it renders many blocked or JS-only sites
  (including HTTP-only sites and several .gov domains). Try it before
  writing any site off.
- Some brands block their homepage but leave a policy subpage or subdomain
  readable — probe the specific policy URL, not just the root.
- archive.org: the availability API responds, but capture pages are
  blocked from automated readers. An archive capture of an official menu
  is acceptable as `menu.source_url`; set `current_url` to the live page.
- "Image-only PDF" is often wrong — download the PDF and read the saved
  file before declaring a menu unreadable.
- A dropped domain gets repurposed: a live-looking site at the venue's old
  URL can be an SEO blog squatting on the name. Check content, not just
  HTTP 200. Directory listings and even the venue's own stale site can
  survive closure — corroborate existence before researching policy.

## Chains and multi-property brands

- A brand-level "pet-friendly" page is **never tier 1 for one property**
  when policies vary by location (all hotel chains: Marriott, Hilton,
  Hyatt, Wyndham, Choice, Best Western…). Property-page policy VALUES
  (fee, weight cap) on the property's own page are tier 1; brand labels
  without values are not.
- The inverse also exists: a corporate policy that explicitly covers every
  store (e.g. Petco's) IS tier 1 chain-wide. Read what the page actually
  claims scope over.
- Chain "pet-friendly hotels in <city>" landing pages are often unfiltered
  SEO lists — test any filter page against a second filter before trusting.
- Never substitute a live sibling store for a closed one — different
  premises, different row.

## Lodging is structurally tier 3

Hotels publish policies in booking engines, not on crawlable pages, so
`stay` rows almost always end at a phone call. Make ONE pass for an
independent official source, then log `unverifiable` with the number.
OTA fee/weight numbers (Expedia, BringFido, etc.) are feed data — they
conflict constantly and are never tier 2. An OTA "no pets" line is the
same feed data as a fee. Multiple aggregators agreeing proves only that
they share a feed.

## Multi-tenant premises

- A food hall's own FAQ can be tier 1 for every stall (Optimist Hall
  pattern); a hall with no policy makes all its stalls tier 3 at once.
- Commissary/ghost-kitchen addresses have no visitable premises — check
  whether the queue row's address is a real storefront before researching.
- Mall food-court counters and contract cafeterias have no independent
  policy; the landlord's rules govern. Usually drop, don't call.

## OSM candidates (discover.py output)

- Check `access=private` before sourcing any `dog_park` — HOA and
  apartment amenities are mistagged as public parks constantly.
- Descriptor-only names ("Chinese Fast Food") are OSM placeholder nodes —
  resolve the real business via Overpass/street view or drop the row.
- `trail` rows are often mistagged parks: `leisure=pitch` (courts,
  diamonds) means re-type the row.
- Same-name venues in other cities poison search results — always bind
  evidence to the address, not the name. A dog-friendly mention for a
  same-name venue elsewhere is worthless.
- County/city parks with no per-park page can still clear tier 1 via the
  ordinance + official parks GIS layer.

## Phone follow-up hygiene

- Prefer the number on the venue's own site; aggregator numbers go stale
  and sometimes point at a different business entirely.
- Establish the premise first ("do you have a patio?") before asking about
  dogs — a confident "no dogs" from a venue with no outdoor space answers
  the wrong question.
- Log every outcome:
  `python pipeline/ledger.py set-status --city <city> --id <id> --status <status> --note "..."`
  and a phone-verified policy becomes tier 1 with `method: phone`.

## When a venue turns out closed/rebranded/moved

Don't silently drop it: set the ledger status (`closed`), note the
successor if any, and check whether the successor publishes its own
policy (new row, new research). Queue rows pointing at stale coordinates
(moved venues, converted buildings) get re-pointed or dropped in the
queue file with a note.
