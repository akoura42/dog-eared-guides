import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import yaml from 'js-yaml';
import { z } from 'astro:content';

// data/ lives at the monorepo root, two levels above apps/web
const here = path.dirname(fileURLToPath(import.meta.url));
export const DATA_DIR = path.resolve(here, '../../../../data');

const emergencyContactSchema = z.object({
  name: z.string(),
  phone: z.string(),
  note: z.string(),
  source_url: z.string().url(),
  // Coordinates make the contact a pin on the explorer's Emergency layer.
  // Phone-first contacts (poison lines, animal control) stay null.
  lat: z.number().nullable().default(null),
  lng: z.number().nullable().default(null),
});

const citySchema = z.object({
  name: z.string(),
  slug: z.string(),
  state: z.string(),
  state_code: z.string(),
  geo: z.object({ lat: z.number(), lng: z.number() }),
  hero: z.object({
    headline: z.string(),
    subhead: z.string(),
  }),
  hero_image: z.string().nullable().default(null),
  hero_image_alt: z.string().nullable().default(null),
  hero_image_credit: z.string().nullable().default(null),
  hero_image_credit_url: z.string().url().nullable().default(null),
  resources: z
    .array(z.object({ label: z.string(), url: z.string().url(), note: z.string() }))
    .default([]),
  intro: z.string(),
  seasonal_notes: z.array(z.string()).default([]),
  regulations: z
    .array(
      z.object({
        summary: z.string(),
        detail: z.string(),
        jurisdiction: z.string(),
        source_url: z.string().url(),
      })
    )
    .default([]),
  categories: z.array(z.string()),
  // Manual override for the explorer map's initial frame radius (km from
  // town center). Unset, the frame self-tunes to the venue distribution.
  map_frame_km: z.number().nullable().default(null),
  // Getting there with a dog: the airport and rail links that serve the
  // town, with verified pet rules (relief areas, Amtrak carry-on policy).
  // Coordinates optional — stored for a future map layer.
  getting_there: z
    .array(
      z.object({
        mode: z.enum(['air', 'rail']),
        name: z.string(),
        note: z.string(),
        source_url: z.string().url(),
        lat: z.number().nullable().default(null),
        lng: z.number().nullable().default(null),
      })
    )
    .default([]),
  // Verified emergency contacts for the /{city}/emergency/ page and the
  // pocket card. Every entry carries the source it was verified against.
  emergency: z
    .object({
      er_vets: z.array(emergencyContactSchema).default([]),
      poison: z.array(emergencyContactSchema).default([]),
      lost_found: z.array(emergencyContactSchema).default([]),
    })
    .nullable()
    .default(null),
  // Area-alias map for the explorer's area chips: lowercase neighborhood
  // token -> visitor-level area name, or null to drop the token. Unknown
  // tokens pass through unchanged, so a new city works before it earns
  // any aliases. Per-city data — a "cherry" in one city must never
  // relabel a "Cherry" in another.
  areas: z.record(z.string(), z.string().nullable()).default({}),
  // Agency domains whose favicon is shared across many venues (county
  // parks dept, state parks, USFS): when such a venue has a licensed
  // photo, the photo takes the card tile instead of the repeated favicon.
  agency_domains: z.array(z.string()).default([]),
  // Optional per-city OSM discovery radius (pipeline/discover.py); unset
  // falls back to 8 km. Metros need more, hamlets less.
  discover_radius_km: z.number().nullable().default(null),
  // Safe polarity for mass onboarding: a city ships nothing until it has
  // passed the QA gate and someone deliberately flips this to true.
  launched: z.boolean().default(false),
});

const categorySchema = z.object({
  key: z.string(),
  slug: z.string(),
  label: z.string(),
  singular: z.string(),
  blurb: z.string(),
});

const attributeSchema = z.object({
  key: z.string(),
  slug: z.string(),
  label: z.string(),
  blurb: z.string(),
  rule: z.object({
    field: z.string(),
    equals: z.union([z.string(), z.boolean()]).optional(),
    includes: z.string().optional(),
  }),
});

export type CityConfig = z.infer<typeof citySchema>;
export type CategoryDef = z.infer<typeof categorySchema>;
export type AttributeDef = z.infer<typeof attributeSchema>;

function readYaml(file: string): unknown {
  return yaml.load(fs.readFileSync(file, 'utf8'));
}

// These loaders are called per page render (header/footer) and per venue
// card, so they must not touch the filesystem on every call. Data files
// never change mid-build; cache for the process lifetime.
let citiesCache: CityConfig[] | null = null;
let cityBySlug: Map<string, CityConfig> | null = null;
let categoriesCache: CategoryDef[] | null = null;
let categoryByKey: Map<string, CategoryDef> | null = null;
let attributesCache: AttributeDef[] | null = null;
let upcomingTownsCache: UpcomingTown[] | null = null;

export function getCities(): CityConfig[] {
  if (citiesCache) return citiesCache;
  const dir = path.join(DATA_DIR, 'cities');
  citiesCache = fs
    .readdirSync(dir)
    .filter((f) => f.endsWith('.yaml') || f.endsWith('.yml'))
    .map((f) => citySchema.parse(readYaml(path.join(dir, f))))
    .sort((a, b) => a.name.localeCompare(b.name));
  return citiesCache;
}

export function getCity(slug: string): CityConfig {
  if (!cityBySlug) {
    cityBySlug = new Map(getCities().map((c) => [c.slug, c]));
  }
  const city = cityBySlug.get(slug);
  if (!city) throw new Error(`Unknown city config: ${slug}`);
  return city;
}

export function getCategories(): CategoryDef[] {
  if (categoriesCache) return categoriesCache;
  const raw = readYaml(path.join(DATA_DIR, 'categories.yaml')) as {
    categories: unknown[];
  };
  categoriesCache = raw.categories.map((c) => categorySchema.parse(c));
  return categoriesCache;
}

export function getCategoryByKey(key: string): CategoryDef {
  if (!categoryByKey) {
    categoryByKey = new Map(getCategories().map((c) => [c.key, c]));
  }
  const cat = categoryByKey.get(key);
  if (!cat) throw new Error(`Unknown category key: ${key}`);
  return cat;
}

export interface UpcomingTown {
  name: string;
  state: string;
  state_code: string;
  tier: number;
  water_body: string;
  lat: number;
  lng: number;
}

/**
 * Waterfront towns queued for future coverage (tiers 1-2 from the CSV,
 * geocoded by pipeline/geocode_towns.py). Shown on the homepage map as
 * "coming soon" dots; excludes towns that already have a launched city.
 */
export function getUpcomingTowns(): UpcomingTown[] {
  if (upcomingTownsCache) return upcomingTownsCache;
  const file = path.join(DATA_DIR, 'waterfront-towns-geo.json');
  if (!fs.existsSync(file)) return (upcomingTownsCache = []);
  const towns = JSON.parse(fs.readFileSync(file, 'utf8')) as UpcomingTown[];
  const launched = new Set(
    getCities().map((c) => `${c.name.toLowerCase()}|${c.state_code}`)
  );
  upcomingTownsCache = towns.filter(
    (t) => !launched.has(`${t.name.toLowerCase()}|${t.state_code}`)
  );
  return upcomingTownsCache;
}

export function getAttributes(): AttributeDef[] {
  if (attributesCache) return attributesCache;
  const raw = readYaml(path.join(DATA_DIR, 'attributes.yaml')) as {
    attributes: unknown[];
  };
  attributesCache = raw.attributes.map((a) => attributeSchema.parse(a));
  return attributesCache;
}
