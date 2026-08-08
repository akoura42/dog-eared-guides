// Area filter derived from venue `neighborhood` values. Neighborhoods are
// free text, often compound ("Downtown / Commons Beach"); this splits them
// into tokens and collapses sub-spots and street descriptors into the
// areas a visitor navigates by. Unknown tokens pass through unchanged, so
// a new town works before it earns any aliases.
const AREA_ALIASES: Record<string, string | null> = {
  // --- Tahoe City ---
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

  // --- Charlotte ---
  // the wards are Uptown
  'first ward': 'Uptown',
  'second ward': 'Uptown',
  'third ward': 'Uptown',
  'fourth ward': 'Uptown',
  'brooklyn village': 'Uptown',
  // LoSo folds into South End for visitors
  'loso': 'South End',
  'loso (lower south end)': 'South End',
  'lower south end (loso)': 'South End',
  // Camp North End's named yards, and the corridor around it
  'camp north end (keswick)': 'Camp North End',
  'camp north end (boileryard)': 'Camp North End',
  'north end': 'Camp North End',
  // adjacency folds
  'the pass': 'NoDa',
  'chantilly': 'Plaza Midwood',
  'cherry': 'Midtown',
  'montford drive': 'Madison Park',
  'montclaire south': 'Madison Park',
  'colonial village': 'Madison Park',
  'oakhurst': 'Cotswold',
  'seversville': 'West Charlotte',
  'clanton park': 'West Charlotte',
  'west boulevard': 'West Charlotte',
  'city park': 'West Charlotte',
  'four seasons': 'East Charlotte',
  'allen hills': 'North Charlotte',
  'derita': 'North Charlotte',
  'brightwalk': 'North Charlotte',
  'druid hills': 'North Charlotte',
  'airport': 'Airport Area',
  // sub-spots that don't carry a visitor-level area of their own
  'parkdale': null,
  'grier heights': null,
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
