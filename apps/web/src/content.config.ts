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

// Verification is required on every venue: the site shows "Verified <date>"
// as a trust signal, and verify.py re-checks anything older than 90 days.
const verificationSchema = z.object({
  last_verified: z.coerce.date(),
  method: z.enum(['official_website', 'phone', 'in_person', 'other']),
  source_url: z.string().url(),
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
    seasonal: z.array(z.string()).default([]),
    verification: verificationSchema,
    affiliate: z
      .object({
        viator_product_code: z.string().nullable().default(null),
        viator_url: z.string().url().nullable().default(null),
        booking_url: z.string().url().nullable().default(null),
      })
      .nullable()
      .default(null),
    tags: z.array(z.string()).default([]),
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
