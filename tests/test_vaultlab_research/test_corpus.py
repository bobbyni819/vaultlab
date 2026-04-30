"""Unit tests for vaultlab.research.corpus.

A 5-paper synthetic corpus is built using a stub ``fetch_refs`` so no
HTTP traffic is involved.
"""

from __future__ import annotations

from vaultlab.research.citation_lookup import Reference
from vaultlab.research.corpus import (
    Corpus,
    build_corpus_from_seeds,
    expand_corpus,
)
from vaultlab.research.paper import Paper


# ---------------------------------------------------------------------------
# Fixture: synthetic 5-paper graph
# ---------------------------------------------------------------------------
#
# Seeds: A, B, C  (citing each other and old-papers X, Y)
# Background:     X (very old), Y (older)
#
#   A --> X, Y, B
#   B --> X, Y
#   C --> Y, A
#
# Expected metrics later:
#   og_score: X=2/3, Y=3/3=1.0, A=1/3, B=1/3
#   forward_influence: A=1 (cited by C), B=1 (cited by A), C=0


def _seed(doi: str, year: int, title: str = "") -> Paper:
    return Paper(
        title=title or doi,
        doi=doi,
        year=year,
        source_api="seed",
    )


def _ref(doi: str, year: int = 0, title: str = "") -> Reference:
    return Reference(doi=doi, year=year, title=title or doi)


def _make_fetch_refs():
    """Return a deterministic fake of ``get_references_via_crossref``."""
    table: dict[str, list[Reference] | None] = {
        "10.1/a": [_ref("10.1/x", 1990), _ref("10.1/y", 2000), _ref("10.1/b", 2018)],
        "10.1/b": [_ref("10.1/x", 1990), _ref("10.1/y", 2000)],
        "10.1/c": [_ref("10.1/y", 2000), _ref("10.1/a", 2017)],
    }
    calls: list[str] = []

    def fetch(doi: str):
        calls.append(doi)
        return table.get(doi.lower())

    fetch.calls = calls  # type: ignore[attr-defined]
    return fetch


# ---------------------------------------------------------------------------
# build_corpus_from_seeds
# ---------------------------------------------------------------------------


def test_build_corpus_populates_papers_and_edges():
    seeds = [
        _seed("10.1/A", 2017, "A"),
        _seed("10.1/b", 2018, "B"),
        _seed("10.1/c", 2019, "C"),
    ]
    fetch = _make_fetch_refs()
    corpus = build_corpus_from_seeds(seeds, topic="test", fetch_refs=fetch)

    # Seeds + background papers (X, Y) all in the corpus
    assert set(corpus.papers.keys()) == {"10.1/a", "10.1/b", "10.1/c", "10.1/x", "10.1/y"}
    assert corpus.topic == "test"
    assert corpus.n_papers == 5

    # Edges
    assert corpus.references["10.1/a"] == ["10.1/x", "10.1/y", "10.1/b"]
    assert corpus.references["10.1/b"] == ["10.1/x", "10.1/y"]
    assert corpus.references["10.1/c"] == ["10.1/y", "10.1/a"]

    # Total edge count
    assert corpus.n_edges == 7

    # Seeds are all marked as papers, with year preserved
    assert corpus.papers["10.1/a"].year == 2017
    assert corpus.papers["10.1/b"].year == 2018

    # Background papers got titles + years from references
    assert corpus.papers["10.1/x"].year == 1990
    assert corpus.papers["10.1/y"].year == 2000


def test_seed_doi_normalization():
    """Seed DOIs are lower-cased before being used as keys."""
    seeds = [_seed("10.1/A", 2020)]
    fetch = lambda doi: [_ref("10.1/x", 1990)]  # noqa: E731
    corpus = build_corpus_from_seeds(seeds, fetch_refs=fetch)
    assert "10.1/a" in corpus.papers
    assert corpus.papers["10.1/a"].doi == "10.1/a"
    assert corpus.references["10.1/a"] == ["10.1/x"]


def test_seed_without_doi_kept_in_seeds_but_not_papers():
    seeds = [_seed("10.1/a", 2020), Paper(title="No DOI", year=2019)]
    fetch = lambda doi: []  # noqa: E731
    corpus = build_corpus_from_seeds(seeds, fetch_refs=fetch)
    assert len(corpus.seeds) == 2
    assert len(corpus.papers) == 1  # only the DOI-bearing seed


def test_crossref_no_refs_marks_empty_list():
    """When fetch returns None, paper is recorded with no references (PDF fallback)."""
    seeds = [_seed("10.1/a", 2020)]
    fetch = lambda doi: None  # noqa: E731
    corpus = build_corpus_from_seeds(seeds, fetch_refs=fetch)
    assert corpus.references["10.1/a"] == []
    assert corpus.has_references_for("10.1/a") is False


def test_fetch_exception_swallowed_as_empty():
    """A raised exception during fetch should not abort the build."""
    seeds = [_seed("10.1/a", 2020), _seed("10.1/b", 2020)]

    def fetch(doi):
        if doi == "10.1/a":
            raise RuntimeError("boom")
        return [_ref("10.1/y", 2010)]

    corpus = build_corpus_from_seeds(seeds, fetch_refs=fetch)
    assert corpus.references["10.1/a"] == []
    assert corpus.references["10.1/b"] == ["10.1/y"]


def test_no_duplicate_fetch_for_same_doi():
    seeds = [_seed("10.1/a", 2020), _seed("10.1/A", 2020)]  # same DOI, different case
    fetch = _make_fetch_refs()
    build_corpus_from_seeds(seeds, fetch_refs=fetch)
    assert fetch.calls.count("10.1/a") == 1


# ---------------------------------------------------------------------------
# expand_corpus
# ---------------------------------------------------------------------------


def test_expand_corpus_walks_one_layer():
    seeds = [_seed("10.1/a", 2017)]
    fetch_table = {
        "10.1/a": [_ref("10.1/b", 2010)],
        "10.1/b": [_ref("10.1/c", 2000)],
        "10.1/c": [],
    }

    def fetch(doi):
        return fetch_table.get(doi.lower())

    corpus = build_corpus_from_seeds(seeds, fetch_refs=fetch)
    # After build: A and B are known, but only A's refs were fetched.
    assert "10.1/a" in corpus.references
    assert "10.1/b" not in corpus.references

    expand_corpus(corpus, depth=1, fetch_refs=fetch)
    assert "10.1/b" in corpus.references
    assert corpus.references["10.1/b"] == ["10.1/c"]
    assert "10.1/c" in corpus.papers


def test_expand_depth_zero_is_noop():
    seeds = [_seed("10.1/a", 2020)]
    fetch = lambda doi: []  # noqa: E731
    corpus = build_corpus_from_seeds(seeds, fetch_refs=fetch)
    before = len(corpus.references)
    expand_corpus(corpus, depth=0, fetch_refs=fetch)
    assert len(corpus.references) == before


def test_corpus_dataclass_helpers():
    seeds = [_seed("10.1/a", 2017)]
    fetch = lambda doi: [_ref("10.1/x", 1990)]  # noqa: E731
    corpus = build_corpus_from_seeds(seeds, fetch_refs=fetch)
    assert corpus.seed_dois == ["10.1/a"]
    assert corpus.n_papers == 2
    assert corpus.n_edges == 1
    assert corpus.has_references_for("10.1/a") is True
    assert corpus.has_references_for("10.1/x") is False


def test_corpus_metrics_attribute_starts_none():
    corpus = Corpus(topic="t", seeds=[])
    assert corpus.metrics is None
