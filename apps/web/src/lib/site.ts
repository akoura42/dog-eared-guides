// Brand-level configuration. BRAND_NAME is a placeholder per the project
// spec — swap it here (and only here) when the name lands.
export const BRAND_NAME = 'BRAND_NAME';
export const BRAND_TAGLINE = 'City guides where dog-friendly is the whole point.';

export const SITE_URL =
  import.meta.env.SITE_URL ?? 'https://brand-name-placeholder.pages.dev';

// Monetization / analytics wiring. All optional; components no-op when unset.
export const ADSENSE_CLIENT = import.meta.env.PUBLIC_ADSENSE_CLIENT ?? '';
export const GA4_ID = import.meta.env.PUBLIC_GA4_ID ?? '';
export const CF_ANALYTICS_TOKEN = import.meta.env.PUBLIC_CF_ANALYTICS_TOKEN ?? '';
