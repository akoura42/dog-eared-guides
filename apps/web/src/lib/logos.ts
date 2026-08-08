// Venue logos fetched from each venue's own website by
// pipeline/fetch_logos.py into public/venue-logos/<city>/<slug>.<ext>.
// A logo renders only when a file exists — no file, no logo, no fallback.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import type { Venue } from './venues';
import { venueSlug } from './venues';

const here = path.dirname(fileURLToPath(import.meta.url));
const LOGOS_DIR = path.resolve(here, '../../public/venue-logos');

const EXTS = ['.png', '.svg', '.webp', '.jpg', '.gif', '.ico'];

export function venueLogoUrl(venue: Venue): string | null {
  const slug = venueSlug(venue);
  for (const ext of EXTS) {
    if (fs.existsSync(path.join(LOGOS_DIR, venue.data.city, slug + ext))) {
      return `/venue-logos/${venue.data.city}/${slug}${ext}`;
    }
  }
  return null;
}
