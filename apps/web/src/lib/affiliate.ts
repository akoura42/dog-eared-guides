// Affiliate link wrapping (docs/monetization.md). All optional: with no
// affiliate ID configured, links render unwrapped and the site behaves
// identically — commission is a build-time switch, never a content change.

// Booking.com Affiliate Partner id. Set BOOKING_AFFILIATE_AID in the
// build environment to activate; venue content never embeds it.
const BOOKING_AID = import.meta.env.BOOKING_AFFILIATE_AID ?? '';

/**
 * Wrap a lodging booking URL with our affiliate id where the partner
 * supports it. Booking.com property URLs get `aid=`; anything else
 * (a property's own booking engine, recreation.gov, …) passes through
 * untouched.
 */
export function lodgingAffiliateUrl(url: string): string {
  if (!BOOKING_AID) return url;
  try {
    const u = new URL(url);
    if (/(^|\.)booking\.com$/.test(u.hostname)) {
      u.searchParams.set('aid', BOOKING_AID);
      return u.toString();
    }
  } catch {
    // malformed URL in content — surface it unchanged rather than crash
  }
  return url;
}
