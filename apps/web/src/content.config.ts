import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

export const CATEGORY_KEYS = [
  'eat',
  'drink',
  'stay',
  'trail',
  'beach',
  'activity',
  'shop',
  'services',
] as const;

const dogPolicySchema = z.object({
  allowed: z.enum(['indoors', 'patio_only', 'outdoor_areas', 'grounds_only', 'no']),
  leash_required: z.boolean().nullable().default(null),
  water_bowls: z.boolean().nullable().default(null),
  size_or_breed_restrictions: z.string().nullable().default(null),
  fee: z.string().nullable().default(null),
  notes: z.string().nullable().default(null),
});

// Verification is required on every venue and has three tiers:
//   official  — the policy is confirmed by an official source (tier 1)
//   reported  — no official source exists; ≥2 independent, linkable
//               visitor/customer mentions back the claim (tier 2), and the
//               page labels it unconfirmed by the venue
//   (tier 3 — no evidence at all — is simply not published)
// verify.py re-checks anything older than 90 days either way.
const verificationSchema = z
  .object({
    last_verified: z.coerce.date(),
    method: z.enum(['official_website', 'phone', 'in_person', 'other']),
    // Tier 1: the official source. Tier 2: the strongest mention link.
    source_url: z.string().url(),
    level: z.enum(['official', 'reported']).default('official'),
    mentions: z
      .array(
        z.object({
          source_url: z.string().url(),
          note: z.string(),
          seen: z.coerce.date(),
        })
      )
      .default([]),
  })
  .refine((v) => v.level !== 'reported' || v.mentions.length >= 2, {
    message: 'reported-tier verification requires at least 2 mentions',
  });

// Verified menu: real items read from the venue's own published menu —
// never inferred from cuisine. Powers dish search ("who has spaghetti?").
const menuSchema = z.object({
  // Where we read the menu (may be an archive capture when the live site
  // blocks readers).
  source_url: z.string().url(),
  // The venue's live menu page for readers — falls back to source_url.
  current_url: z.string().url().nullable().default(null),
  last_verified: z.coerce.date(),
  items: z.array(z.string()).min(1),
});

const venues = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/venues' }),
  schema: z.object({
    name: z.string(),
    // city slug is derived from the directory (id = "<city>/<slug>"),
    // but stored explicitly too so pipeline output is self-describing
    city: z.string(),
    category: z.enum(CATEGORY_KEYS),
    neighborhood: z.string().nullable().default(null),
    address: z.string(),
    lat: z.number(),
    lng: z.number(),
    phone: z.string().nullable().default(null),
    website: z.string().url().nullable().default(null),
    dog_policy: dogPolicySchema,
    // Cuisine labels for eat/drink venues, grounded in the venue's own
    // published copy (e.g. "pizzeria", "beer garden") — powers the cuisine
    // filter on the city explorer. Never inferred beyond what the venue
    // says about itself.
    cuisines: z.array(z.string()).default([]),
    seasonal: z.array(z.string()).default([]),
    // Structured operating season (MM-DD), only when the venue publishes
    // actual dates — fuzzy seasons ("closes at first snow") stay in the
    // free-text `seasonal` notes and never get a computed flag.
    season: z
      .object({
        opens: z.string().regex(/^\d{2}-\d{2}$/),
        closes: z.string().regex(/^\d{2}-\d{2}$/),
      })
      .nullable()
      .default(null),
    verification: verificationSchema,
    menu: menuSchema.nullable().default(null),
    // First-person observations from an actual visit — human-editor-only
    // (never pipeline-written). The one channel for claimed experience;
    // presence earns the "Field-tested" badge. See docs/voice.md §6.
    field_notes: z.string().nullable().default(null),
    affiliate: z
      .object({
        viator_product_code: z.string().nullable().default(null),
        viator_url: z.string().url().nullable().default(null),
        booking_url: z.string().url().nullable().default(null),
      })
      .nullable()
      .default(null),
    tags: z.array(z.string()).default([]),
    // Google Place ID (ToS allows caching IDs, unlike other Places data).
    // Optional — when absent the reviews panel resolves it at runtime via
    // the free IDs-only text search.
    google_place_id: z.string().nullable().default(null),
    summary: z.string(),
    // Path under src/assets/photos/, e.g. "tahoe-city/truckee-river.jpg".
    // Licensed/owner-supplied only — never hot-linked. Credit is required
    // whenever an image is set.
    image: z.string().nullable().default(null),
    image_alt: z.string().nullable().default(null),
    image_credit: z.string().nullable().default(null),
    image_credit_url: z.string().url().nullable().default(null),
  }),
});

const guides = defineCollection({
  loader: glob({ pattern: '**/*.mdx', base: './src/content/guides' }),
  schema: z.object({
    title: z.string(),
    city: z.string(),
    description: z.string(),
    date: z.coerce.date(),
    updated: z.coerce.date().nullable().default(null),
    faqs: z
      .array(z.object({ question: z.string(), answer: z.string() }))
      .default([]),
    has_affiliate_links: z.boolean().default(false),
    image: z.string().nullable().default(null),
    image_alt: z.string().nullable().default(null),
    image_credit: z.string().nullable().default(null),
    image_credit_url: z.string().url().nullable().default(null),
  }),
});

export const collections = { venues, guides };
