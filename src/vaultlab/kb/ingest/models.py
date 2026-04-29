"""Normalized output type for all ingestors."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class KbDocument:
    """Normalized output of any ingestor.

    Every ingestor (markdown, pdf, bibtex, …) returns one of these. The
    KB writer converts them into ``Sources/<kind>/<slug>.md`` files with
    frontmatter populated from the dataclass fields.

    Attributes
    ----------
    kind
        High-level category — ``"paper"``, ``"note"``, ``"article"``, ``"citation"``.
        Maps to the destination subdirectory under ``Sources/``.
    title
        Display title.
    body
        Markdown body. May be empty for citation-only entries.
    source
        Original input — file path, URL, DOI, etc. — for provenance.
    metadata
        Frontmatter-bound fields beyond title/source. Common keys:
        ``authors``, ``year``, ``doi``, ``pmid``, ``url``, ``ingested``, ``tags``.
    slug
        Filesystem slug (kebab-case). Auto-derived from title if not supplied.
    """

    kind: str
    title: str
    body: str
    source: str
    metadata: dict[str, Any] = field(default_factory=dict)
    slug: str = ""

    def __post_init__(self) -> None:
        if not self.slug:
            self.slug = _slugify(self.title)


def _slugify(text: str) -> str:
    """Convert a title to a filesystem-safe kebab-case slug."""
    out = []
    prev_dash = False
    for ch in text.lower().strip():
        if ch.isalnum():
            out.append(ch)
            prev_dash = False
        elif ch in (" ", "-", "_", "/", "."):
            if not prev_dash and out:
                out.append("-")
                prev_dash = True
        # else: drop punctuation
    slug = "".join(out).strip("-")
    return slug or "untitled"


__all__ = ["KbDocument"]


# Re-export the slugify helper for ingestors that need it
def _public_slugify(text: str) -> str:  # pragma: no cover - thin re-export
    return _slugify(text)


# Public name (no leading underscore) for use by sibling modules
slugify = _slugify
