// Structured venue seasons (MM-DD open/close from the venue's own
// published dates). The in-season flag is computed at build time, so it
// is as fresh as the last deploy — the 90-day verification cycle keeps
// builds frequent enough for season-scale accuracy.
export type Season = { opens: string; closes: string };

const md = (s: string) => {
  const [m, d] = s.split('-').map(Number);
  return m * 100 + d;
};

export function inSeason(season: Season, date = new Date()): boolean {
  const now = (date.getMonth() + 1) * 100 + date.getDate();
  const o = md(season.opens);
  const c = md(season.closes);
  // Seasons that wrap the new year (e.g. a winter park) have opens > closes.
  return o <= c ? now >= o && now <= c : now >= o || now <= c;
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export function formatMD(s: string): string {
  const [m, d] = s.split('-').map(Number);
  return `${MONTHS[m - 1]} ${d}`;
}
