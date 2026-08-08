// Area filter derived from venue `neighborhood` values. Neighborhoods are
// free text, often compound ("Downtown / Commons Beach"); this splits them
// into tokens and collapses sub-spots and street descriptors into the
// areas a visitor navigates by. Unknown tokens pass through unchanged, so
// a new town works before it earns any aliases.
const AREA_ALIASES: Record<string, string | null> = {
  // sub-spots → their area
  'truckee river outlet': 'Truckee River',
  'truckee river canyon': 'Truckee River',
  'fanny bridge': 'Truckee River',
  'west lake': 'West Shore',
  'blackwood canyon': 'West Shore',
  'ward avenue': 'West Shore',
  'commons beach': 'Downtown',
  'tahoe vista': 'North Shore',
  'burton creek': 'Highlands',
  // street descriptors → dropped (the other token carries the area)
  'hwy 89': null,
  'highway 28': null,
  'grove street': null,
  'west river st': null,
  '64-acres': null,
};

export function venueAreas(neighborhood: string | null): string[] {
  if (!neighborhood) return [];
  const out = new Set<string>();
  for (const raw of neighborhood.split('/')) {
    const token = raw.trim();
    if (!token) continue;
    const mapped = AREA_ALIASES[token.toLowerCase()];
    if (mapped === null) continue;
    out.add(mapped ?? token);
  }
  return [...out];
}
