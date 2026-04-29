"""PDF ingestor — extracts text + DOI from research papers.

Uses the optional ``pypdf`` dependency when present; falls back to a clear
error message if not installed (so the markdown / bibtex / folder ingestors
work even without the figures extras).
"""

from __future__ import annotations

import re
from pathlib import Path

from vaultlab.kb.ingest.dispatcher import URL_PATTERN, IngestError, register
from vaultlab.kb.ingest.models import KbDocument


def matches_pdf(source: str) -> bool:
    if URL_PATTERN.match(source):
        return False
    p = Path(source)
    return p.suffix.lower() == ".pdf" and p.is_file()


_DOI_RE = re.compile(r"\b10\.\d{4,9}/[^\s\"<>]+", re.IGNORECASE)


@register(
    "pdf",
    description="Research-paper PDFs. Extracts full text via pypdf; "
    "auto-detects DOI from the first 2 pages.",
    implemented=True,
)
def ingest_pdf(source: str) -> KbDocument:
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]
    except ImportError as e:
        raise IngestError(
            "PDF ingest requires `pypdf` — install with "
            '`pip install -e ".[research]"` or `pip install pypdf`.'
        ) from e

    p = Path(source)
    reader = PdfReader(str(p))
    pages = [page.extract_text() or "" for page in reader.pages]
    full_text = "\n\n".join(pages)

    # DOI is most reliably found in the first 2 pages
    doi = None
    head = "\n".join(pages[:2])
    m = _DOI_RE.search(head)
    if m:
        doi = m.group(0).rstrip(".,;)")

    metadata_pdf = reader.metadata or {}
    title = (
        (metadata_pdf.get("/Title") if metadata_pdf else None)
        or _first_nonempty_line(head)
        or p.stem
    )

    metadata: dict[str, object] = {
        "ingested_from": str(p.resolve()),
        "n_pages": len(reader.pages),
    }
    if doi:
        metadata["doi"] = doi
    if metadata_pdf:
        for key in ("/Author", "/CreationDate"):
            if key in metadata_pdf:
                metadata[key.lstrip("/").lower()] = str(metadata_pdf[key])

    return KbDocument(
        kind="paper",
        title=str(title),
        body=full_text.strip(),
        source=str(p.resolve()),
        metadata=metadata,
    )


def _first_nonempty_line(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None
