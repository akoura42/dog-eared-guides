import type { ImageMetadata } from 'astro';

// All site photography lives under src/assets/photos/<city>/… and is
// referenced from frontmatter/config by that relative path. Licensed or
// owner-supplied only — never hot-linked.
const photos = import.meta.glob<{ default: ImageMetadata }>(
  '/src/assets/photos/**/*.{jpg,jpeg,png,webp}',
  { eager: true }
);

export function resolvePhoto(path: string | null | undefined): ImageMetadata | null {
  if (!path) return null;
  const entry = photos[`/src/assets/photos/${path}`];
  if (!entry) {
    throw new Error(
      `Photo not found: src/assets/photos/${path} (referenced in content/config)`
    );
  }
  return entry.default;
}
