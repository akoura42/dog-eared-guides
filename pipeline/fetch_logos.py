"""Fetch venue logos from each venue's own website for the venue cards.

For every venue with a `website`, downloads the site's best self-declared
icon — apple-touch-icon first (usually the logo mark at 180px), then the
largest `rel=icon`, then /apple-touch-icon.png and /favicon.ico probes —
and stores it under apps/web/public/venue-logos/<city>/<slug>.<ext>.
The web app renders a logo only when a file exists here, so a failed or
blocked fetch simply means no logo on that card.

Idempotent: existing files are kept (delete one to refetch it).

Usage: python pipeline/fetch_logos.py <city-slug>
"""

from __future__ import annotations

import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
VENUES_DIR = REPO_ROOT / "apps" / "web" / "src" / "content" / "venues"
LOGOS_DIR = REPO_ROOT / "apps" / "web" / "public" / "venue-logos"

UA = {"User-Agent": "Mozilla/5.0 (compatible; DogEaredGuides/1.0; +https://dogearedguides.com)"}
MIN_BYTES = 500  # tiny files are usually placeholder favicons

MAGIC = {
    b"\x89PNG": ".png",
    b"\xff\xd8\xff": ".jpg",
    b"GIF8": ".gif",
    b"RIFF": ".webp",
    b"\x00\x00\x01\x00": ".ico",
    b"<svg": ".svg",
    b"<?xm": ".svg",
}


def fetch(url: str, timeout: int = 20) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception:
        return None


def icon_candidates(html: str, base: str) -> list[str]:
    """Icon URLs from <link> tags, best first."""
    links = re.findall(r"<link\s[^>]*>", html, re.I)
    scored: list[tuple[int, str]] = []
    for tag in links:
        rel = re.search(r'rel=["\']?([^"\'>]+)', tag, re.I)
        href = re.search(r'href=["\']?([^"\'\s>]+)', tag, re.I)
        if not rel or not href or "icon" not in rel.group(1).lower():
            continue
        rel_v = rel.group(1).lower()
        sizes = re.search(r'sizes=["\']?(\d+)', tag, re.I)
        size = int(sizes.group(1)) if sizes else 0
        # apple-touch-icon is usually the logo mark; prefer it, then size.
        score = (1000 if "apple-touch" in rel_v else 0) + size
        scored.append((score, urllib.parse.urljoin(base, href.group(1))))
    return [u for _, u in sorted(scored, reverse=True)]


def best_icon(website: str) -> tuple[bytes, str] | None:
    html_bytes = fetch(website)
    candidates: list[str] = []
    if html_bytes:
        try:
            candidates = icon_candidates(html_bytes.decode("utf-8", "ignore"), website)
        except Exception:
            candidates = []
    origin = "{0.scheme}://{0.netloc}".format(urllib.parse.urlparse(website))
    candidates += [f"{origin}/apple-touch-icon.png", f"{origin}/favicon.ico"]
    for url in candidates:
        data = fetch(url)
        if not data or len(data) < MIN_BYTES:
            continue
        for magic, ext in MAGIC.items():
            if data.lstrip()[:8].startswith(magic) or data[:8].startswith(magic):
                return data, ext
    return None


def run(slug: str) -> None:
    out_dir = LOGOS_DIR / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    got = skipped = missed = 0
    for f in sorted((VENUES_DIR / slug).glob("*.md")):
        front = yaml.safe_load(f.read_text().split("---", 2)[1])
        website = front.get("website")
        stem = f.stem
        if not website:
            continue
        if any(out_dir.glob(f"{stem}.*")):
            skipped += 1
            continue
        result = best_icon(website)
        if result is None:
            print(f"  no logo: {stem} ({website})")
            missed += 1
            continue
        data, ext = result
        (out_dir / f"{stem}{ext}").write_bytes(data)
        print(f"  {stem}{ext} ({len(data) // 1024} KB)")
        got += 1
    print(f"{slug}: {got} fetched, {skipped} already present, {missed} without a usable icon")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: fetch_logos.py <city-slug>")
    run(sys.argv[1])
