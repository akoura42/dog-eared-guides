// Dog-Eared Index (docs/dog-eared-index.md) — read side.
// Scores are computed by pipeline/index/compute.py; this module only reads
// data/cities/<slug>/index.yaml and data/index-bands.json (the band tables
// exported by the same code that scores, so display can't drift).
import fs from 'node:fs';
import path from 'node:path';
import yaml from 'js-yaml';
import { DATA_DIR } from './config';

export type IndexSource = {
  url?: string;
  method?: string;
  note?: string;
  date?: string;
};

export type IndexComponentData = {
  value?: number | string | null;
  modifiers?: string[] | null;
  basis?: { numerator: number; denominator: number };
  sources: IndexSource[];
  last_verified: string | null;
  score: number | null;
};

export type PillarSubtotal = {
  components_verified: number;
  components_total: number;
  score: number | null;
};

export type TownIndex = {
  version: string;
  town: string;
  computed: string;
  components: Record<string, IndexComponentData>;
  pillars: Record<string, PillarSubtotal>;
  composite: {
    components_verified: number;
    components_total: number;
    score: number | null;
    provisional: boolean | null;
  };
};

export type BandDef = {
  key: string;
  label: string;
  pillar: string;
  weight: number;
  kind: 'share' | 'number' | 'number-max' | 'condition' | 'rubric';
  unit: string;
  auto?: boolean;
  bands?: { key?: string; label: string; score: number }[];
  modifiers?: { key: string; label: string; points: number }[];
  base?: number;
};

export type IndexBands = {
  version: string;
  tagline: string;
  publish_gate: number;
  pillars: string[];
  components: BandDef[];
};

export function getIndexBands(): IndexBands {
  return JSON.parse(fs.readFileSync(path.join(DATA_DIR, 'index-bands.json'), 'utf8'));
}

export function getTownIndex(slug: string): TownIndex | null {
  const file = path.join(DATA_DIR, 'cities', slug, 'index.yaml');
  if (!fs.existsSync(file)) return null;
  return yaml.load(fs.readFileSync(file, 'utf8')) as TownIndex;
}

export function getPublishedTownIndexes(): TownIndex[] {
  // data/cities holds <slug>.yaml configs alongside <slug>/ artifact dirs;
  // only the dirs can carry an index.yaml, and getTownIndex filters those.
  const citiesDir = path.join(DATA_DIR, 'cities');
  if (!fs.existsSync(citiesDir)) return [];
  return fs
    .readdirSync(citiesDir, { withFileTypes: true })
    .filter((e) => e.isDirectory())
    .map((e) => getTownIndex(e.name))
    .filter((t): t is TownIndex => t !== null && t.composite.score !== null);
}

/** Human display for a component's measured value, or null when unverified. */
export function formatComponentValue(
  def: BandDef,
  data: IndexComponentData
): string | null {
  if (def.kind === 'rubric') {
    if (data.modifiers == null) return null;
    return `${data.score} points (base ${def.base ?? 50}, ${data.modifiers.length} ${
      data.modifiers.length === 1 ? 'modifier' : 'modifiers'
    })`;
  }
  if (data.value == null) return null;
  if (def.kind === 'share') {
    const pct = `${Math.round((data.value as number) * 100)}%`;
    return data.basis ? `${pct} (${data.basis.numerator} of ${data.basis.denominator})` : pct;
  }
  if (def.kind === 'condition') {
    return def.bands?.find((b) => b.key === data.value)?.label ?? String(data.value);
  }
  return String(data.value);
}
