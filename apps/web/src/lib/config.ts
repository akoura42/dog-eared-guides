import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import yaml from 'js-yaml';
import { z } from 'astro:content';

// data/ lives at the monorepo root, two levels above apps/web
const here = path.dirname(fileURLToPath(import.meta.url));
export const DATA_DIR = path.resolve(here, '../../../../data');

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
  launched: z.boolean().default(true),
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

export function getCities(): CityConfig[] {
  const dir = path.join(DATA_DIR, 'cities');
  return fs
    .readdirSync(dir)
    .filter((f) => f.endsWith('.yaml') || f.endsWith('.yml'))
    .map((f) => citySchema.parse(readYaml(path.join(dir, f))))
    .sort((a, b) => a.name.localeCompare(b.name));
}

export function getCity(slug: string): CityConfig {
  const city = getCities().find((c) => c.slug === slug);
  if (!city) throw new Error(`Unknown city config: ${slug}`);
  return city;
}

export function getCategories(): CategoryDef[] {
  const raw = readYaml(path.join(DATA_DIR, 'categories.yaml')) as {
    categories: unknown[];
  };
  return raw.categories.map((c) => categorySchema.parse(c));
}

export function getCategoryByKey(key: string): CategoryDef {
  const cat = getCategories().find((c) => c.key === key);
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
  const file = path.join(DATA_DIR, 'cities', 'waterfront-towns-geo.json');
  if (!fs.existsSync(file)) return [];
  const towns = JSON.parse(fs.readFileSync(file, 'utf8')) as UpcomingTown[];
  const launched = new Set(
    getCities().map((c) => `${c.name.toLowerCase()}|${c.state_code}`)
  );
  return towns.filter(
    (t) => !launched.has(`${t.name.toLowerCase()}|${t.state_code}`)
  );
}

export function getAttributes(): AttributeDef[] {
  const raw = readYaml(path.join(DATA_DIR, 'attributes.yaml')) as {
    attributes: unknown[];
  };
  return raw.attributes.map((a) => attributeSchema.parse(a));
}
