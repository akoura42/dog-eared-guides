import type { Venue, Guide } from './venues';
import { venuePath, guidePath } from './venues';
import type { CityConfig } from './config';
import { BRAND_NAME, SITE_URL } from './site';

const SCHEMA_TYPE_BY_CATEGORY: Record<string, string> = {
  eat: 'Restaurant',
  drink: 'BarOrPub',
  stay: 'LodgingBusiness',
  trail: 'TouristAttraction',
  beach: 'Beach',
  activity: 'TouristAttraction',
  shop: 'Store',
  services: 'LocalBusiness',
};

export function venueJsonLd(venue: Venue, city: CityConfig) {
  const d = venue.data;
  const amenities: object[] = [];
  if (d.dog_policy.water_bowls) {
    amenities.push({
      '@type': 'LocationFeatureSpecification',
      name: 'Dog water bowls',
      value: true,
    });
  }
  if (d.dog_policy.allowed === 'patio_only' || d.dog_policy.allowed === 'outdoor_areas') {
    amenities.push({
      '@type': 'LocationFeatureSpecification',
      name: 'Dog-friendly outdoor seating',
      value: true,
    });
  }
  return {
    '@context': 'https://schema.org',
    '@type': SCHEMA_TYPE_BY_CATEGORY[d.category] ?? 'LocalBusiness',
    name: d.name,
    url: `${SITE_URL}${venuePath(venue)}`,
    address: {
      '@type': 'PostalAddress',
      streetAddress: d.address,
      addressLocality: city.name,
      addressRegion: city.state_code,
      addressCountry: 'US',
    },
    geo: { '@type': 'GeoCoordinates', latitude: d.lat, longitude: d.lng },
    ...(d.phone ? { telephone: d.phone } : {}),
    ...(d.website ? { sameAs: [d.website] } : {}),
    petsAllowed: d.dog_policy.allowed !== 'no',
    ...(amenities.length ? { amenityFeature: amenities } : {}),
  };
}

export function breadcrumbJsonLd(crumbs: { name: string; url: string }[]) {
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: crumbs.map((c, i) => ({
      '@type': 'ListItem',
      position: i + 1,
      name: c.name,
      item: `${SITE_URL}${c.url}`,
    })),
  };
}

export function guideJsonLd(guide: Guide, city: CityConfig) {
  const d = guide.data;
  const article = {
    '@context': 'https://schema.org',
    '@type': 'Article',
    headline: d.title,
    description: d.description,
    datePublished: d.date.toISOString().slice(0, 10),
    ...(d.updated ? { dateModified: d.updated.toISOString().slice(0, 10) } : {}),
    author: { '@type': 'Organization', name: BRAND_NAME },
    publisher: { '@type': 'Organization', name: BRAND_NAME },
    mainEntityOfPage: `${SITE_URL}${guidePath(guide)}`,
    about: `Dog-friendly travel in ${city.name}, ${city.state_code}`,
  };
  const faq = d.faqs.length
    ? {
        '@context': 'https://schema.org',
        '@type': 'FAQPage',
        mainEntity: d.faqs.map((f) => ({
          '@type': 'Question',
          name: f.question,
          acceptedAnswer: { '@type': 'Answer', text: f.answer },
        })),
      }
    : null;
  return { article, faq };
}
