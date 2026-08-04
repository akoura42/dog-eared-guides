import { getCollection, type CollectionEntry } from 'astro:content';
import type { AttributeDef } from './config';

export type Venue = CollectionEntry<'venues'>;
export type Guide = CollectionEntry<'guides'>;

/** Venue URL slug: the filename portion of the entry id ("<city>/<slug>"). */
export function venueSlug(venue: Venue): string {
  return venue.id.split('/').pop()!;
}

export function venuePath(venue: Venue): string {
  return `/${venue.data.city}/venues/${venueSlug(venue)}/`;
}

export function guideSlug(guide: Guide): string {
  return guide.id.split('/').pop()!.replace(/\.mdx$/, '');
}

export function guidePath(guide: Guide): string {
  return `/${guide.data.city}/guides/${guideSlug(guide)}/`;
}

export async function venuesForCity(city: string): Promise<Venue[]> {
  const all = await getCollection('venues', (v) => v.data.city === city);
  return all.sort((a, b) => a.data.name.localeCompare(b.data.name));
}

export async function guidesForCity(city: string): Promise<Guide[]> {
  const all = await getCollection('guides', (g) => g.data.city === city);
  return all.sort((a, b) => b.data.date.getTime() - a.data.date.getTime());
}

export async function findVenue(city: string, slug: string): Promise<Venue | undefined> {
  const venues = await venuesForCity(city);
  return venues.find((v) => venueSlug(v) === slug);
}

/** Minimum venues before a category or attribute hub page is generated. */
export const MIN_HUB_VENUES = 4;

function getByPath(obj: unknown, dotted: string): unknown {
  return dotted
    .split('.')
    .reduce<any>((acc, key) => (acc == null ? undefined : acc[key]), obj);
}

export function matchesAttribute(venue: Venue, attr: AttributeDef): boolean {
  const value = getByPath(venue.data, attr.rule.field);
  if (attr.rule.equals !== undefined) return value === attr.rule.equals;
  if (attr.rule.includes !== undefined)
    return Array.isArray(value) && value.includes(attr.rule.includes);
  return false;
}

export function formatVerifiedDate(date: Date): string {
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    timeZone: 'UTC',
  });
}

export const ALLOWED_LABELS: Record<string, string> = {
  indoors: 'Dogs allowed inside',
  patio_only: 'Dogs on the patio only',
  outdoor_areas: 'Dogs in outdoor areas',
  grounds_only: 'Dogs on the grounds only',
  no: 'Dogs not allowed',
};
