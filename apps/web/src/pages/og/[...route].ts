// Template-generated OG images for every page type, rendered at build time.
import { OGImageRoute } from 'astro-og-canvas';
import { getCollection } from 'astro:content';
import { getCities } from '~/lib/config';
import { venueSlug, guideSlug } from '~/lib/venues';
import { BRAND_NAME } from '~/lib/site';

const pages: Record<string, { title: string; description: string }> = {
  home: {
    title: 'Take the dog. We checked.',
    description: 'Verified dog-friendly city guides.',
  },
};

for (const city of getCities()) {
  pages[city.slug] = {
    title: `Dog-Friendly ${city.name}, ${city.state_code}`,
    description: city.hero.subhead,
  };
}

for (const venue of await getCollection('venues')) {
  pages[`${venue.data.city}-${venueSlug(venue)}`] = {
    title: venue.data.name,
    description: venue.data.summary,
  };
}

for (const guide of await getCollection('guides')) {
  pages[`${guide.data.city}-guide-${guideSlug(guide)}`] = {
    title: guide.data.title,
    description: guide.data.description,
  };
}

export const { getStaticPaths, GET } = OGImageRoute({
  param: 'route',
  pages,
  getImageOptions: (_path, page) => ({
    title: page.title,
    description: page.description,
    logo: { path: './src/assets/logo-mark.png', size: [84, 84] },
    bgGradient: [
      [20, 52, 39],
      [31, 77, 58],
    ],
    border: { color: [232, 161, 60], width: 14, side: 'inline-start' },
    padding: 72,
    font: {
      title: { size: 64, weight: 'SemiBold', color: [255, 255, 255] },
      description: { size: 32, weight: 'Normal', color: [206, 224, 213] },
    },
    footer: BRAND_NAME,
  }),
});
