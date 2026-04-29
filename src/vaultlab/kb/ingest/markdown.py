"""Markdown ingestor — passes through ``.md`` files preserving frontmatter."""

from __future__ import annotations

import re
from pathlib import Path

from vaultlab.kb.ingest.dispatcher import URL_PATTERN, register
from vaultlab.kb.ingest.models import KbDocument


def matches_markdown(source: str) -> bool:
    if URL_PATTERN.match(source):
        return False
    p = Path(source)
    return p.suffix.lower() == ".md" and p.is_file()


@register(
    "markdown",
    description="Local .md files. Preserves existing frontmatter; auto-fills "
    "title from first H1 if frontmatter title is missing.",
    implemented=True,
)
def ingest_markdown(source: str) -> KbDocument:
    p = Path(source)
    text = p.read_text(encoding="utf-8")

    frontmatter, body = _split_frontmatter(text)
    title = frontmatter.get("title") or _first_h1(body) or p.stem

    metadata = dict(frontmatter)
    metadata.setdefault("ingested_from", str(p.resolve()))
    metadata.pop("title", None)  # title is a top-level field on KbDocument

    return KbDocument(
        kind=str(metadata.get("type", "note")),
        title=str(title),
        body=body.strip(),
        source=str(p.resolve()),
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


_FRONT_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def _split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Return (parsed_frontmatter, body) — minimal YAML-flavored parser.

    Only handles ``key: value`` pairs (one per line, no nested structures).
    Sufficient for vaultlab note templates; full YAML adds a dependency for
    little gain.
    """
    m = _FRONT_RE.match(text)
    if not m:
        return {}, text
    raw = m.group(1)
    body = text[m.end() :]
    parsed: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            key, _, value = line.partition(":")
            parsed[key.strip()] = value.strip().strip("\"'")
    return parsed, body


def _first_h1(body: str) -> str | None:
    for line in body.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("# ") and not stripped.startswith("##"):
            return stripped[2:].strip()
    return None
