"""vaultlab.kb — knowledge-base primitives.

Public surface (currently exported here):

- :func:`retrieve_by_frontmatter` — YAML-frontmatter-driven lookup
  (researcher-pathway cascade layer 2). See ``retrieve.md`` for the full
  layered-retrieval doc.
- :func:`build_indexes` — auto-generate ``_Index.md``, ``_Catalog.md``, and
  ``_BackLinks.md`` from frontmatter + wikilink scanning (cascade layer 3).
- :func:`scaffold_kb` (alias :func:`setup`) — scaffold the canonical KB
  folder layout (SPEC-D).
- :func:`lint_kb` (alias :func:`lint`) — audit a KB folder against the
  canonical schema; returns a :class:`LintReport` (SPEC-D).
- :class:`LintReport` / :class:`LintFinding` (alias :class:`LintIssue`) —
  structured lint results.
- :class:`ScaffoldError` — raised when scaffolding hits a precondition
  failure (existing folder without ``force=True``, unknown domain
  extension).

The rest of the subpackage (``dossier``, ``feedback``, ``ingest``,
``paths``, ``semantic_search``, ``snapshot``, ``start_here``,
``tools_index``) is reached via its module path; that surface will be
exported from here in follow-up sub-goals.
"""

from vaultlab.kb.indexes import build_indexes
from vaultlab.kb.retrieve import retrieve_by_frontmatter
from vaultlab.kb.setup import (
    LintFinding,
    LintReport,
    ScaffoldError,
    lint_kb,
    scaffold_kb,
)

# Task-brief-aligned short aliases. The canonical names (``scaffold_kb`` /
# ``lint_kb`` / ``LintFinding``) carry the full SPEC-D semantics; ``setup`` /
# ``lint`` / ``LintIssue`` are the ergonomic shorthand the north-star plan
# (sub-goal 2.3) calls out as the public-primitive surface.
setup = scaffold_kb
lint = lint_kb
LintIssue = LintFinding

__all__ = [
    "LintFinding",
    "LintIssue",
    "LintReport",
    "ScaffoldError",
    "build_indexes",
    "lint",
    "lint_kb",
    "retrieve_by_frontmatter",
    "scaffold_kb",
    "setup",
]
