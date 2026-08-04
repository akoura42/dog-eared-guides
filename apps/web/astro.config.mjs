// @ts-check
import { defineConfig } from 'astro/config';
import mdx from '@astrojs/mdx';
import sitemap from '@astrojs/sitemap';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import yaml from 'js-yaml';

// Cloudflare Pages static deployment. Set SITE_URL in the Pages project
// (or in .env) once the production domain exists — it drives canonical
// URLs, the sitemap, and OG image URLs.
const SITE_URL = process.env.SITE_URL ?? 'https://brand-name-placeholder.pages.dev';

// Category hub pages exist from 1 venue up so browsing works, but hubs
// below the indexing bar (4 venues — the spec's no-thin-pages rule) are
// noindexed and must also stay out of the sitemap. Counting venues here
// mirrors MIN_HUB_VENUES in src/lib/venues.ts.
const MIN_INDEXABLE_HUB_VENUES = 4;

function thinHubPaths() {
  const here = path.dirname(fileURLToPath(import.meta.url));
  const venuesDir = path.join(here, 'src/content/venues');
  const categoriesFile = path.resolve(here, '../../data/categories.yaml');
  if (!fs.existsSync(venuesDir) || !fs.existsSync(categoriesFile)) return [];
  const categories = /** @type {{categories: {key: string, slug: string}[]}} */ (
    yaml.load(fs.readFileSync(categoriesFile, 'utf8'))
  ).categories;

  /** @type {Record<string, Record<string, number>>} */
  const counts = {};
  for (const cityDirName of fs.readdirSync(venuesDir)) {
    const cityDir = path.join(venuesDir, cityDirName);
    if (!fs.statSync(cityDir).isDirectory()) continue;
    for (const file of fs.readdirSync(cityDir).filter((f) => f.endsWith('.md'))) {
      const text = fs.readFileSync(path.join(cityDir, file), 'utf8');
      const m = text.match(/^---\n([\s\S]*?)\n---/);
      if (!m) continue;
      const fm = /** @type {{city?: string, category?: string}} */ (yaml.load(m[1]));
      if (!fm?.city || !fm?.category) continue;
      counts[fm.city] ??= {};
      counts[fm.city][fm.category] = (counts[fm.city][fm.category] ?? 0) + 1;
    }
  }

  const thin = [];
  for (const [city, cats] of Object.entries(counts)) {
    for (const [key, n] of Object.entries(cats)) {
      if (n > 0 && n < MIN_INDEXABLE_HUB_VENUES) {
        const slug = categories.find((c) => c.key === key)?.slug;
        if (slug) thin.push(`/${city}/${slug}/`);
      }
    }
  }
  return thin;
}

const THIN_HUBS = thinHubPaths();

export default defineConfig({
  site: SITE_URL,
  output: 'static',
  trailingSlash: 'always',
  integrations: [
    mdx(),
    sitemap({
      filter: (page) =>
        !page.includes('/og/') && !THIN_HUBS.some((p) => page.endsWith(p)),
    }),
  ],
});
