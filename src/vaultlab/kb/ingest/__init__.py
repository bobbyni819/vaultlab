"""vaultlab.kb.ingest — pluggable ingestors for many source types.

Master plan §5 (file 05). Each source type has its own ingestor module that
emits a normalized :class:`KbDocument` with frontmatter + body. The dispatcher
:func:`ingest` infers the source type from the input and routes accordingly.

Supported source types in this phase:

- **markdown** — local ``.md`` files (passthrough; preserves existing frontmatter)
- **pdf** — research papers; extracts text via stdlib + records DOI when present
- **bibtex / ris** — citation files; one entry per record → one KbDocument per citation
- **folder** — recursive ingest of a directory (dispatches per-file)

Stubbed (raise ``NotImplementedError`` with clear guidance):

- **url** — web fetch + html-to-markdown (planned: phase 4b)
- **doi / pmid** — uses ``vaultlab.research`` (planned after research module lands)
- **zotero** — Zotero export folder (.json + attached PDFs)
- **notebooklm** — NotebookLM-exported markdown bundles

Examples
--------
>>> from vaultlab.kb.ingest import ingest
>>> doc = ingest("path/to/note.md")  # doctest: +SKIP
>>> print(doc.kind, doc.title, len(doc.body))  # doctest: +SKIP
"""

from __future__ import annotations

from vaultlab.kb.ingest.dispatcher import IngestError, ingest, registered_ingestors
from vaultlab.kb.ingest.models import KbDocument

__all__ = [
    "IngestError",
    "KbDocument",
    "ingest",
    "registered_ingestors",
]
