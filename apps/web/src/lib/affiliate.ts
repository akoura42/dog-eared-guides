// Affiliate link wrapping (docs/monetization.md). All optional: with no
// affiliate ID configured, links render unwrapped and the site behaves
// identically — commission is a build-time switch, never a content change.

// Booking.com Affiliate Partner id. Set BOOKING_AFFILIATE_AID in the
// build environment to activate; venue content never embeds it.
const BOOKING_AID = import.meta.env.BOOKING_AFFILIATE_AID ?? '';

// Viator partner id (format P00xxxxx). Set VIATOR_PARTNER_ID to activate.
const VIATOR_PID = import.meta.env.VIATOR_PARTNER_ID ?? '';

// Pet-insurance referral link + partner display name. Both required for
// the PetInsuranceCTA module to render at all — no partner, no module.
export const PET_INSURANCE_URL = import.meta.env.PET_INSURANCE_URL ?? '';
export const PET_INSURANCE_PARTNER = import.meta.env.PET_INSURANCE_PARTNER ?? '';

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

/**
 * Wrap a Viator product URL with our partner id (their standard link
 * params). Non-Viator URLs pass through untouched.
 */
export function viatorAffiliateUrl(url: string): string {
  if (!VIATOR_PID) return url;
  try {
    const u = new URL(url);
    if (/(^|\.)viator\.com$/.test(u.hostname)) {
      u.searchParams.set('pid', VIATOR_PID);
      u.searchParams.set('mcid', '42383');
      u.searchParams.set('medium', 'link');
      return u.toString();
    }
  } catch {
    // malformed URL in content — surface it unchanged rather than crash
  }
  return url;
}
