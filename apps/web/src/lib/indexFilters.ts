// Venue-level filters derived from Dog-Eared Index components. A component
// that contributed positively to a town's score (verified score > 0) and
// has a venue mapping becomes a filter chip on the explorer, so a reader
// can see exactly which venues are behind that part of the score.
//
// Predicates mirror pipeline/index/compute.py's hospitality semantics;
// evidence-linked components (water access, emergency vet) key off the
// tags carried by the venues cited in the component's sources. Town-level
// components with no venue mapping (ordinance regime, heat risk) are
// deliberately absent.
import type { Venue } from './venues';

type VenueData = Venue['data'];

export const INDEX_VENUE_FILTERS: Record<string, (d: VenueData) => boolean> = {
  patio_share: (d) =>
    ['eat', 'drink'].includes(d.category) &&
    ['patio_only', 'outdoor_areas', 'indoors'].includes(d.dog_policy.allowed),
  indoor_welcome: (d) =>
    ['shop', 'drink'].includes(d.category) && d.dog_policy.allowed === 'indoors',
  lodging_share: (d) => d.category === 'stay' && d.dog_policy.allowed !== 'no',
  water_access: (d) => d.tags.includes('water-access'),
  trail_access: (d) => d.category === 'trail',
  off_leash: (d) => d.dog_policy.leash_required === false,
  emergency_vet: (d) => d.tags.includes('emergency-vet'),
};

export const INDEX_FILTERABLE_KEYS = Object.keys(INDEX_VENUE_FILTERS);
