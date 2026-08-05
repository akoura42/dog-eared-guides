// Brand-level configuration. The name flows from here through copy,
// metadata, JSON-LD, and OG images — change it in one place only.
export const BRAND_NAME = 'Dog-Eared Guides';
export const BRAND_TAGLINE = 'City guides where dog-friendly is the whole point.';

export const SITE_URL =
  import.meta.env.SITE_URL ?? 'https://dogearedguides.com';

// Monetization / analytics wiring. All optional; components no-op when unset.
export const ADSENSE_CLIENT = import.meta.env.PUBLIC_ADSENSE_CLIENT ?? '';
// Google Maps Platform key — enables the click-to-reveal Google reviews
// panel on venue pages. Leave unset to keep the site fully Google-free
// (deep links still work). Restrict the key by HTTP referrer + to the
// Maps JavaScript API before setting it.
export const GMAPS_API_KEY = import.meta.env.PUBLIC_GMAPS_API_KEY ?? '';
export const GA4_ID = import.meta.env.PUBLIC_GA4_ID ?? '';
export const CF_ANALYTICS_TOKEN = import.meta.env.PUBLIC_CF_ANALYTICS_TOKEN ?? '';
