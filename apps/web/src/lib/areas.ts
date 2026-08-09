// Area filter derived from venue `neighborhood` values. Neighborhoods are
// free text, often compound ("Downtown / Commons Beach"); this splits them
// into tokens and collapses sub-spots and street descriptors into the
// areas a visitor navigates by. The alias map is per-city data
// (data/cities/<slug>.yaml `areas:`) — city launches must not require
// code deploys, and one city's aliases must never relabel another's.
// Unknown tokens pass through unchanged, so a new city works before it
// earns any aliases.
import { getCity } from './config';

// Alias keys are matched lowercase; normalize once per city so a
// "NoDa:" key in the yaml still matches instead of silently never firing.
const normalizedAliases = new Map<string, Record<string, string | null>>();

function aliasesFor(city: string): Record<string, string | null> {
  let aliases = normalizedAliases.get(city);
  if (!aliases) {
    aliases = Object.fromEntries(
      Object.entries(getCity(city).areas).map(([k, v]) => [k.toLowerCase(), v])
    );
    normalizedAliases.set(city, aliases);
  }
  return aliases;
}

export function venueAreas(city: string, neighborhood: string | null): string[] {
  if (!neighborhood) return [];
  const aliases = aliasesFor(city);
  const out = new Set<string>();
  for (const raw of neighborhood.split('/')) {
    const token = raw.trim();
    if (!token) continue;
    const mapped = aliases[token.toLowerCase()];
    if (mapped === null) continue;
    out.add(mapped ?? token);
  }
  return [...out];
}
