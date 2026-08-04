// @ts-check
import { defineConfig } from 'astro/config';
import mdx from '@astrojs/mdx';
import sitemap from '@astrojs/sitemap';

// Cloudflare Pages static deployment. Set SITE_URL in the Pages project
// (or in .env) once the production domain exists — it drives canonical
// URLs, the sitemap, and OG image URLs.
const SITE_URL = process.env.SITE_URL ?? 'https://brand-name-placeholder.pages.dev';

export default defineConfig({
  site: SITE_URL,
  output: 'static',
  trailingSlash: 'always',
  integrations: [mdx(), sitemap({ filter: (page) => !page.includes('/og/') })],
});
