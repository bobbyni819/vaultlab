"""Corpus assembly for the literature-search v2 citation graph.

A :class:`Corpus` is the unit of analysis for a literature topic:

* ``seeds`` — papers from a keyword search (e.g. "CRISPR base editing")
* ``papers`` — every paper observed (seed or referenced), keyed by DOI
* ``references`` — adjacency map: paper DOI -> list of cited DOIs
* ``metrics`` — :class:`vaultlab.research.graph_metrics.CorpusMetrics`,
  computed lazily

The corpus is built by walking outbound CrossRef references one or more
hops from the seeds. Papers without DOIs are dropped from the graph (we
can't dedupe them); papers where CrossRef has the DOI but no reference
list are kept as nodes with an empty reference list, signalling that a
later PDF-reading task should fill the gap.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

from vaultlab.research.citation_lookup import (
    Reference,
    get_references_via_crossref,
)
from vaultlab.research.paper import Paper

if TYPE_CHECKING:
    from vaultlab.research.graph_metrics import CorpusMetrics

logger = logging.getLogger(__name__)


# Type alias: a callable that fetches references for a DOI. Defaults to
# :func:`get_references_via_crossref`. Tests inject their own.
ReferenceFetcher = Callable[[str], "list[Reference] | None"]


@dataclass
class Corpus:
    """A topic-scoped collection of papers and their citation edges.

    Attributes:
        topic: The topic / search query that produced this corpus.
        seeds: The papers returned by the keyword search. These are the
            "OG" papers in the corpus's frame of reference — every other
            paper either is one of these or is referenced by one.
        papers: Every paper in the graph, keyed by lower-cased DOI.
        references: ``doi -> list of cited DOIs`` adjacency. A paper present
            here with an empty list means CrossRef knew of it but had no
            reference array (PDF-reading fallback target). A paper absent
            means we never tried to look up its refs.
        metrics: Computed citation metrics. Populated by
            :func:`vaultlab.research.graph_metrics.compute_metrics`.
    """

    topic: str
    seeds: list[Paper]
    papers: dict[str, Paper] = field(default_factory=dict)
    references: dict[str, list[str]] = field(default_factory=dict)
    metrics: "CorpusMetrics | None" = None

    # ------------------------------------------------------------------
    # Convenience views
    # ------------------------------------------------------------------

    @property
    def seed_dois(self) -> list[str]:
        """Lower-cased DOIs of the seed papers (drops seeds without DOI)."""
        return [s.doi.lower() for s in self.seeds if s.doi]

    @property
    def n_papers(self) -> int:
        return len(self.papers)

    @property
    def n_edges(self) -> int:
        return sum(len(v) for v in self.references.values())

    def has_references_for(self, doi: str) -> bool:
        """True if ``doi`` is in ``references`` with at least one cited DOI."""
        refs = self.references.get(doi.lower())
        return bool(refs)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_doi(doi: str) -> str:
    return (doi or "").strip().lower()


def _add_paper(corpus: Corpus, paper: Paper) -> None:
    """Insert ``paper`` into ``corpus.papers`` (lower-cased DOI key).

    If the same DOI is already present, merge the new paper's metadata
    into the existing one (Paper.merge fills empty fields).
    """
    if not paper.doi:
        return
    key = _normalize_doi(paper.doi)
    paper.doi = key
    if key in corpus.papers:
        corpus.papers[key].merge(paper)
    else:
        corpus.papers[key] = paper


def _reference_to_paper(ref: Reference) -> Paper | None:
    """Convert a Reference to a minimal Paper, or None if it has no DOI."""
    if not ref.doi:
        return None
    return Paper(
        title=ref.title,
        authors=list(ref.authors),
        year=ref.year,
        doi=ref.doi.lower(),
        source_api="crossref-ref",
    )


def _walk_one_layer(
    corpus: Corpus,
    dois_to_walk: list[str],
    fetch_refs: ReferenceFetcher,
) -> list[str]:
    """Fetch references for each DOI in ``dois_to_walk`` and add them to the corpus.

    Returns the list of newly-discovered DOIs (so callers can recurse).
    """
    newly_discovered: list[str] = []
    for doi in dois_to_walk:
        key = _normalize_doi(doi)
        if not key or key in corpus.references:
            # Already attempted — skip to avoid re-querying the API.
            continue
        try:
            refs = fetch_refs(key)
        except Exception as exc:  # network / HTTP / parse error
            logger.warning("Failed to fetch references for %s: %s", key, exc)
            corpus.references[key] = []
            continue

        if refs is None:
            # CrossRef has no reference array (or doesn't know the DOI).
            # Record the empty edge list so we don't retry, but signal
            # to the PDF-reading task that this paper needs follow-up.
            corpus.references[key] = []
            continue

        cited_dois: list[str] = []
        for ref in refs:
            ref_doi = _normalize_doi(ref.doi)
            if not ref_doi:
                continue
            cited_dois.append(ref_doi)
            if ref_doi not in corpus.papers:
                paper = _reference_to_paper(ref)
                if paper is not None:
                    _add_paper(corpus, paper)
                    newly_discovered.append(ref_doi)
        corpus.references[key] = cited_dois
    return newly_discovered


# ---------------------------------------------------------------------------
# Public builders
# ---------------------------------------------------------------------------


def build_corpus_from_seeds(
    seeds: list[Paper],
    *,
    topic: str = "",
    fetch_refs: ReferenceFetcher | None = None,
) -> Corpus:
    """Build a :class:`Corpus` from a list of seed papers.

    For each seed with a DOI, fetch its CrossRef references and record
    them as outbound edges. Seeds without DOIs are kept in ``seeds`` but
    cannot be placed into the graph (we have no key to dedupe them).

    Args:
        seeds: The papers from a keyword search.
        topic: A label (e.g. the search query) for the corpus.
        fetch_refs: Override for the reference fetcher; defaults to
            :func:`get_references_via_crossref`. Useful for tests.

    Returns:
        A populated :class:`Corpus`. ``corpus.metrics`` is left ``None``;
        call :func:`vaultlab.research.graph_metrics.compute_metrics` to
        populate it.
    """
    fetch = fetch_refs or get_references_via_crossref
    corpus = Corpus(topic=topic, seeds=list(seeds))
    for seed in seeds:
        _add_paper(corpus, seed)
    seed_dois = [_normalize_doi(s.doi) for s in seeds if s.doi]
    _walk_one_layer(corpus, seed_dois, fetch)
    logger.info(
        "Built corpus '%s': %d seeds, %d papers, %d edges",
        topic,
        len(seeds),
        corpus.n_papers,
        corpus.n_edges,
    )
    return corpus


def expand_corpus(
    corpus: Corpus,
    depth: int = 1,
    *,
    fetch_refs: ReferenceFetcher | None = None,
) -> Corpus:
    """Walk the citation graph ``depth`` more layers outward from current frontier.

    The "frontier" is every paper currently in ``corpus.papers`` whose
    references haven't been fetched yet.

    Args:
        corpus: The corpus to expand (mutated in place and returned).
        depth: How many additional reference layers to walk. ``0`` is a
            no-op; ``1`` fetches refs for every current paper that doesn't
            already have an entry in ``corpus.references``.
        fetch_refs: Override for the reference fetcher.

    Returns:
        The same ``corpus`` object, after expansion.
    """
    if depth <= 0:
        return corpus
    fetch = fetch_refs or get_references_via_crossref
    for layer in range(depth):
        frontier = [doi for doi in corpus.papers if doi not in corpus.references]
        if not frontier:
            logger.info("expand_corpus: frontier empty after %d layer(s)", layer)
            break
        logger.info(
            "expand_corpus layer %d/%d: walking %d papers",
            layer + 1,
            depth,
            len(frontier),
        )
        _walk_one_layer(corpus, frontier, fetch)
    return corpus


__all__ = [
    "Corpus",
    "ReferenceFetcher",
    "build_corpus_from_seeds",
    "expand_corpus",
]
