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

// Government/agency-run venues share their agency's favicon (TCPUD,
// State Parks, USFS) — informative, but repetitive across cards. When
// such a venue has a licensed photo, the photo takes the tile instead.
const AGENCY_DOMAINS = ['tcpud.org', 'parks.ca.gov', 'placer.ca.gov', 'fs.usda.gov'];

export function isAgencyWebsite(website: string | null): boolean {
  if (!website) return false;
  try {
    const host = new URL(website).hostname;
    return AGENCY_DOMAINS.some((d) => host === d || host.endsWith(`.${d}`));
  } catch {
    return false;
  }
}

export function venueLogoUrl(venue: Venue): string | null {
  const slug = venueSlug(venue);
  for (const ext of EXTS) {
    if (fs.existsSync(path.join(LOGOS_DIR, venue.data.city, slug + ext))) {
      return `/venue-logos/${venue.data.city}/${slug}${ext}`;
    }
  }
  return null;
}
