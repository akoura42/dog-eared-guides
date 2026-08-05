"""Shared helpers for the content pipeline."""

from __future__ import annotations

import datetime as dt
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = REPO_ROOT / "pipeline" / "prompts"
VOICE_FILE = REPO_ROOT / "docs" / "voice.md"
CONTENT_DIR = REPO_ROOT / "apps" / "web" / "src" / "content"
VENUES_DIR = CONTENT_DIR / "venues"
GUIDES_DIR = CONTENT_DIR / "guides"

# Default model per the Claude API guidance; override with MODEL env var.
DEFAULT_MODEL = "claude-opus-5"

WEB_TOOLS = [
    {"type": "web_search_20260209", "name": "web_search"},
    {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 20},
]

# ---------------------------------------------------------------------------
# Model engines
#
# claude-code (default): shells out to the Claude Code CLI, which
#   authenticates with the operator's Claude subscription (local login, or
#   CLAUDE_CODE_OAUTH_TOKEN from `claude setup-token` in CI). No API key,
#   no per-token billing — usage draws on the subscription.
# api: direct Anthropic SDK calls; requires ANTHROPIC_API_KEY (or an
#   `ant auth login` profile) with API billing.
#
# Selection: PIPELINE_ENGINE=claude-code|api wins; otherwise claude-code
# when no ANTHROPIC_API_KEY is set, api when one is.
# ---------------------------------------------------------------------------


def model_engine() -> str:
    engine = os.environ.get("PIPELINE_ENGINE")
    if engine in ("claude-code", "api"):
        return engine
    return "api" if os.environ.get("ANTHROPIC_API_KEY") else "claude-code"


def _call_claude_code(system: str, prompt: str, model: str) -> str:
    cmd = [
        "claude",
        "-p",
        prompt,
        "--append-system-prompt",
        system,
        "--model",
        model,
        "--allowedTools",
        "WebSearch,WebFetch",
        "--max-turns",
        "50",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    if proc.returncode != 0:
        raise RuntimeError(
            f"claude CLI failed (exit {proc.returncode}): {proc.stderr.strip()[:2000]}"
        )
    return proc.stdout


def _call_api(system: str, prompt: str, model: str, max_tokens: int) -> str:
    import anthropic  # imported lazily so the claude-code engine needs no SDK

    client = anthropic.Anthropic()
    messages: list[dict] = [{"role": "user", "content": prompt}]
    for _ in range(6):
        with client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            system=system,
            tools=WEB_TOOLS,
            messages=messages,
        ) as stream:
            response = stream.get_final_message()
        if response.stop_reason == "refusal":
            raise RuntimeError("model refused the request")
        if response.stop_reason == "pause_turn":
            messages = [messages[0], {"role": "assistant", "content": response.content}]
            continue
        break
    else:
        raise RuntimeError("still paused after max continuations")
    return "".join(b.text for b in response.content if b.type == "text")


def call_model(system: str, prompt: str, model: str = DEFAULT_MODEL, max_tokens: int = 32000) -> str:
    """Run one research-and-write task; returns the model's final text."""
    if model_engine() == "claude-code":
        return _call_claude_code(system, prompt, model)
    return _call_api(system, prompt, model, max_tokens)

FILE_RE = re.compile(
    r"===FILE:\s*(?P<path>[^=\n]+?)\s*===\n(?P<body>.*?)\n===END FILE===",
    re.DOTALL,
)
QUESTIONS_RE = re.compile(
    r"===OPEN QUESTIONS===\n(?P<body>.*?)\n===END OPEN QUESTIONS===",
    re.DOTALL,
)


@dataclass
class GeneratedFile:
    rel_path: str  # relative to src/content/
    content: str


@dataclass
class GenerationResult:
    files: list[GeneratedFile] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)


def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text()


def recent_editorial_log(max_entries: int = 20) -> str:
    """Most recent correction lines from EDITORIAL_LOG.md."""
    text = load_prompt("EDITORIAL_LOG.md")
    lines = [
        line
        for line in text.splitlines()
        if re.match(r"^\d{4}-\d{2}-\d{2}\s*\|", line)
    ]
    return "\n".join(lines[:max_entries])


def few_shot_examples(city: str, limit: int = 2) -> str:
    """Approved (merged-to-main) venue pages as few-shot examples."""
    examples = []
    city_dir = VENUES_DIR / city
    candidates = sorted(city_dir.glob("*.md")) if city_dir.is_dir() else []
    if not candidates:  # fall back to any city
        candidates = sorted(VENUES_DIR.glob("*/*.md"))
    for path in candidates[:limit]:
        examples.append(f"--- APPROVED EXAMPLE ({path.name}) ---\n{path.read_text()}")
    return "\n\n".join(examples) if examples else "(no approved examples yet)"


def existing_venue_slugs(city: str) -> list[str]:
    city_dir = VENUES_DIR / city
    if not city_dir.is_dir():
        return []
    return sorted(p.stem for p in city_dir.glob("*.md"))


def parse_generation_output(text: str) -> GenerationResult:
    result = GenerationResult()
    for m in FILE_RE.finditer(text):
        result.files.append(GeneratedFile(m.group("path").strip(), m.group("body")))
    qm = QUESTIONS_RE.search(text)
    if qm:
        for line in qm.group("body").splitlines():
            line = line.strip().lstrip("- ").strip()
            if line and line.lower() != "none":
                result.open_questions.append(line)
    return result


def split_frontmatter(text: str) -> tuple[dict, str]:
    """Parse a markdown file's YAML frontmatter. Raises on malformed files."""
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not m:
        raise ValueError("missing frontmatter block")
    data = yaml.safe_load(m.group(1))
    if not isinstance(data, dict):
        raise ValueError("frontmatter is not a mapping")
    return data, m.group(2)


def validate_venue_file(text: str) -> list[str]:
    """Cheap pre-PR validation. The Astro build (Zod) is the real gate."""
    problems: list[str] = []
    try:
        data, body = split_frontmatter(text)
    except ValueError as exc:
        return [f"frontmatter: {exc}"]
    for key in ("name", "city", "category", "address", "dog_policy", "verification", "summary"):
        if key not in data:
            problems.append(f"missing frontmatter field: {key}")
    verification = data.get("verification") or {}
    if not verification.get("source_url"):
        problems.append("verification.source_url is required — no unsourced venue facts")
    if not verification.get("last_verified"):
        problems.append("verification.last_verified is required")
    word_count = len(body.split())
    if word_count < 150:
        problems.append(f"body too short ({word_count} words; target 200-400)")
    return problems


def run(cmd: list[str], cwd: Path = REPO_ROOT, check: bool = True) -> subprocess.CompletedProcess:
    print(f"$ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=cwd, check=check, capture_output=True, text=True)


def git_current_branch() -> str:
    return run(["git", "rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()


def open_pr(branch: str, title: str, body: str, files: list[Path]) -> None:
    """Commit files on a new branch and open a PR. Never commits to main."""
    base = git_current_branch()
    run(["git", "checkout", "-b", branch])
    try:
        run(["git", "add", *[str(f) for f in files]])
        run(["git", "commit", "-m", title, "-m", body])
        run(["git", "push", "-u", "origin", branch])
        run(["gh", "pr", "create", "--title", title, "--body", body, "--base", "main"])
        print(f"Opened PR from {branch}")
    finally:
        run(["git", "checkout", base], check=False)


def today() -> str:
    return dt.date.today().isoformat()
