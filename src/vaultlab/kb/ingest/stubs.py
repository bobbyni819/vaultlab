"""Stub ingestors — register match patterns + raise NotImplementedError.

Reserves the URL / DOI / PMID / Zotero / NotebookLM source types so the
dispatcher gives clear error messages instead of "no ingestor matches" when
a user tries them. Each stub will be replaced by a real implementation in
later phases.
"""

from __future__ import annotations

import re
from pathlib import Path

from vaultlab.kb.ingest.dispatcher import (
    DOI_PATTERN,
    PMID_PATTERN,
    URL_PATTERN,
    register,
)
from vaultlab.kb.ingest.models import KbDocument


def matches_url(source: str) -> bool:
    return bool(URL_PATTERN.match(source))


@register(
    "url",
    description="Web URLs (http / https). Fetches HTML; converts to markdown. Planned in phase 4b.",
    implemented=False,
)
def ingest_url(source: str) -> KbDocument:  # pragma: no cover - stub
    raise NotImplementedError(
        "URL ingest is planned but not yet wired. Use `vaultlab.context.google.docs` "
        "for Google-hosted articles in the meantime."
    )


def matches_doi(source: str) -> bool:
    return bool(DOI_PATTERN.match(source.strip()))


@register(
    "doi",
    description="DOI strings (e.g. 10.1038/s41586-023-05915-x). Fetches "
    "metadata via vaultlab.research.* APIs. Planned after research module.",
    implemented=False,
)
def ingest_doi(source: str) -> KbDocument:  # pragma: no cover - stub
    raise NotImplementedError(
        "DOI ingest depends on vaultlab.research being built — planned for "
        "after the kb-phase build completes."
    )


def matches_pmid(source: str) -> bool:
    return bool(PMID_PATTERN.match(source.strip()))


@register(
    "pmid",
    description="PubMed IDs. Fetches metadata via NCBI E-utilities. Planned after research module.",
    implemented=False,
)
def ingest_pmid(source: str) -> KbDocument:  # pragma: no cover - stub
    raise NotImplementedError(
        "PMID ingest depends on vaultlab.research.ncbi being built — planned "
        "for after the kb-phase build completes."
    )


_ZOTERO_SIGNAL = re.compile(r"items\.json|@library", re.IGNORECASE)


def matches_zotero(source: str) -> bool:
    p = Path(source)
    if not p.is_dir():
        return False
    return any(_ZOTERO_SIGNAL.search(child.name) for child in p.iterdir() if child.is_file())


@register(
    "zotero",
    description="Zotero export folder (items.json + attached PDFs). Planned post-v0.1.",
    implemented=False,
)
def ingest_zotero(source: str) -> list[KbDocument]:  # pragma: no cover - stub
    raise NotImplementedError(
        "Zotero export ingest is planned post-v0.1. Workaround: export as "
        "BibTeX or RIS — both work today."
    )


def matches_notebooklm(source: str) -> bool:
    p = Path(source)
    if not p.is_dir():
        return False
    return (p / "Notebook.md").exists() or (p / "notebook.md").exists()


@register(
    "notebooklm",
    description="NotebookLM-exported markdown bundle (folder containing "
    "Notebook.md). Planned post-v0.1.",
    implemented=False,
)
def ingest_notebooklm(source: str) -> list[KbDocument]:  # pragma: no cover - stub
    raise NotImplementedError("NotebookLM bundle ingest is planned post-v0.1.")
