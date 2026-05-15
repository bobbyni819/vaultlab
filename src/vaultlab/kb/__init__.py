"""vaultlab.kb — knowledge-base primitives.

Public surface (currently exported here):

- :func:`retrieve_by_frontmatter` — YAML-frontmatter-driven lookup
  (researcher-pathway cascade layer 2). See ``retrieve.md`` for the full
  layered-retrieval doc.
- :func:`build_indexes` — auto-generate ``_Index.md``, ``_Catalog.md``, and
  ``_BackLinks.md`` from frontmatter + wikilink scanning (cascade layer 3).

The rest of the subpackage (``dossier``, ``feedback``, ``ingest``,
``paths``, ``semantic_search``, ``setup``, ``snapshot``, ``start_here``,
``tools_index``) is reached via its module path; that surface will be
exported from here in follow-up sub-goals.
"""

from vaultlab.kb.indexes import build_indexes
from vaultlab.kb.retrieve import retrieve_by_frontmatter

__all__ = [
    "build_indexes",
    "retrieve_by_frontmatter",
]
