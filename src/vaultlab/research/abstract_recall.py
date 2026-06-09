"""vaultlab.research.abstract_recall — thin abstract-recall wrapper over the federated get_paper.

Lineage: PATTERN — mirrors PaperQA2 (FutureHouse) metadata-recall step, where a fast
low-cost fetch returns a paper's abstract before deciding whether to retrieve and read
the full text. See INSPIRATIONS.md (PaperQA2 entry). This module is a thin delegate:
all network logic and API-key resolution live in ``vaultlab.research.get_paper``.

Circular-import note: the import of ``get_paper`` is done lazily inside each function
body because this file is a submodule of the ``vaultlab.research`` package whose
``__init__`` re-exports ``get_abstract_for_doi``. A top-level import would form a
circular dependency at package initialisation time.
"""

from __future__ import annotations


def get_abstract_for_doi(doi: str) -> str | None:
    """Return the abstract text for a paper identified by DOI.

    Delegates to the federated ``vaultlab.research.get_paper`` which tries
    PubMed, Semantic Scholar, Springer, and OpenAlex in turn.

    Args:
        doi: A DOI string such as ``"10.1038/s41586-023-05915-x"``.
             An empty or falsy value returns ``None`` immediately without
             making any network call.

    Returns:
        The abstract string if the paper is found and the abstract is
        non-empty; ``None`` otherwise.
    """
    if not doi:
        return None

    # Lazy import to avoid circular dependency: this module is a submodule of
    # vaultlab.research whose __init__ imports us.
    from vaultlab.research import get_paper  # noqa: PLC0415

    paper = get_paper(doi)
    if paper is None:
        return None

    abstract = paper.abstract
    if not abstract:
        return None

    return abstract
