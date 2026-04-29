"""BibTeX ingestor — emits one KbDocument per ``@entry`` block."""

from __future__ import annotations

import re
from pathlib import Path

from vaultlab.kb.ingest.dispatcher import URL_PATTERN, register
from vaultlab.kb.ingest.models import KbDocument


def matches_bibtex(source: str) -> bool:
    if URL_PATTERN.match(source):
        return False
    p = Path(source)
    return p.suffix.lower() in (".bib", ".bibtex") and p.is_file()


_ENTRY_RE = re.compile(
    r"@(?P<type>\w+)\s*\{\s*(?P<key>[^,\s]+)\s*,(?P<body>.*?)\}(?=\s*(?:@|\Z))",
    re.DOTALL,
)
_FIELD_RE = re.compile(
    r"(?P<name>\w+)\s*=\s*(?:\{(?P<braced>.*?)\}|\"(?P<quoted>.*?)\")", re.DOTALL
)


@register(
    "bibtex",
    description="BibTeX citation files (.bib). One KbDocument per @entry; "
    "useful for bulk-importing a Zotero or Mendeley export.",
    implemented=True,
)
def ingest_bibtex(source: str) -> list[KbDocument]:
    p = Path(source)
    text = p.read_text(encoding="utf-8")

    docs: list[KbDocument] = []
    for entry in _ENTRY_RE.finditer(text):
        kind = entry.group("type").lower()
        cite_key = entry.group("key").strip()
        fields_block = entry.group("body")
        fields: dict[str, str] = {}
        for field_match in _FIELD_RE.finditer(fields_block):
            name = field_match.group("name").lower().strip()
            value = (field_match.group("braced") or field_match.group("quoted") or "").strip()
            # Strip outer braces left over from nested {Foo}
            value = re.sub(r"\s+", " ", value).strip()
            fields[name] = value

        title = fields.get("title", cite_key)
        body = _render_citation_body(cite_key, kind, fields)

        metadata: dict[str, object] = {
            "bibtex_key": cite_key,
            "bibtex_type": kind,
            "ingested_from": str(p.resolve()),
        }
        for k in ("authors", "author", "year", "doi", "pmid", "url", "journal", "booktitle"):
            if k in fields:
                metadata[k] = fields[k]

        docs.append(
            KbDocument(
                kind="citation",
                title=title,
                body=body,
                source=f"{p.resolve()}#{cite_key}",
                metadata=metadata,
            )
        )
    return docs


def _render_citation_body(cite_key: str, kind: str, fields: dict[str, str]) -> str:
    """Compose a sensible markdown body from a BibTeX entry."""
    lines = [f"# {fields.get('title', cite_key)}", ""]
    if "author" in fields:
        lines.append(f"**Authors:** {fields['author']}")
    if "year" in fields:
        lines.append(f"**Year:** {fields['year']}")
    if "journal" in fields:
        lines.append(f"**Journal:** {fields['journal']}")
    elif "booktitle" in fields:
        lines.append(f"**In:** {fields['booktitle']}")
    if "doi" in fields:
        lines.append(f"**DOI:** {fields['doi']}")
    if "url" in fields:
        lines.append(f"**URL:** {fields['url']}")
    lines.append("")
    if "abstract" in fields:
        lines.append("## Abstract")
        lines.append("")
        lines.append(fields["abstract"])
        lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("<!-- Add reading notes here. -->")
    lines.append("")
    return "\n".join(lines)
