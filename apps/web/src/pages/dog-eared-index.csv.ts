// Downloadable CSV of all published town indexes with component values —
// the press/link asset from the index spec (§6.4).
import type { APIRoute } from 'astro';
import { getIndexBands, getPublishedTownIndexes } from '~/lib/dogEaredIndex';

export const GET: APIRoute = () => {
  const bands = getIndexBands();
  const towns = getPublishedTownIndexes();

  const header = [
    'town',
    'version',
    'computed',
    'composite',
    'provisional',
    'components_verified',
    ...bands.components.flatMap((c) => [`${c.key}_value`, `${c.key}_score`]),
  ];

  const rows = towns.map((t) => [
    t.town,
    t.version,
    t.computed,
    t.composite.score,
    t.composite.provisional,
    t.composite.components_verified,
    ...bands.components.flatMap((c) => {
      const data = t.components[c.key];
      const value = c.kind === 'rubric' ? data?.modifiers?.join('; ') : data?.value;
      return [value ?? '', data?.score ?? ''];
    }),
  ]);

  const esc = (cell: unknown) => {
    const s = String(cell ?? '');
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const csv = [header, ...rows].map((r) => r.map(esc).join(',')).join('\n') + '\n';

  return new Response(csv, {
    headers: { 'Content-Type': 'text/csv; charset=utf-8' },
  });
};
