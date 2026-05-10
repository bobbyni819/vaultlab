"""Tests for forward citation expansion (Corpus.cited_by + expand_corpus_forward).

Forward expansion fixes the SOTA blind spot where the standard
backward-only citation graph never surfaces papers newer than the seeds.
"""

from __future__ import annotations

from vaultlab.research.corpus import (
    build_corpus_from_seeds,
    expand_corpus_forward,
)
from vaultlab.research.paper import Paper


def _seed(doi: str, year: int = 2018) -> Paper:
    return Paper(
        title=f"seed-{doi}",
        year=year,
        citation_count=100,
        doi=doi,
        source_api="pubmed",
    )


def _citing(doi: str, year: int = 2024) -> Paper:
    return Paper(
        title=f"citing-{doi}",
        year=year,
        citation_count=5,
        doi=doi,
        source_api="semantic-scholar",
    )


def test_forward_expansion_adds_citing_papers_to_corpus():
    """Citing papers (newer) are added to corpus.papers and corpus.cited_by."""
    seed = _seed("10.1/seed", year=2018)

    # Backward expansion off (no refs fetcher exercised in this test)
    corpus = build_corpus_from_seeds([seed], topic="t", fetch_refs=lambda _doi: None)
    initial_n_papers = corpus.n_papers
    assert "10.1/seed" in corpus.papers

    # Mock S2 forward-citations: this seed is cited by 3 newer papers.
    citing_papers = [
        _citing("10.1/citing-a", year=2024),
        _citing("10.1/citing-b", year=2025),
        _citing("10.1/citing-c", year=2025),
    ]

    def fake_fetch(doi: str, limit: int):
        if doi == "10.1/seed":
            return citing_papers
        return []

    expand_corpus_forward(corpus, fetch_citations=fake_fetch, max_per_paper=10)

    # All 3 new papers are now in corpus
    assert corpus.n_papers == initial_n_papers + 3
    assert "10.1/citing-a" in corpus.papers
    assert corpus.papers["10.1/citing-a"].year == 2024

    # cited_by adjacency populated for the seed
    assert "10.1/seed" in corpus.cited_by
    assert set(corpus.cited_by["10.1/seed"]) == {
        "10.1/citing-a",
        "10.1/citing-b",
        "10.1/citing-c",
    }


def test_forward_expansion_seed_only_skips_non_seeds_by_default():
    """``seed_only=True`` only fetches forward citations for seeds, not for
    every paper in the corpus."""
    seed = _seed("10.1/seed")
    corpus = build_corpus_from_seeds([seed], topic="t", fetch_refs=lambda _doi: None)
    # Add a non-seed paper directly
    extra = _citing("10.1/extra", year=2020)
    corpus.papers["10.1/extra"] = extra

    fetched_dois: list[str] = []

    def fake_fetch(doi: str, limit: int):
        fetched_dois.append(doi)
        return []

    expand_corpus_forward(corpus, fetch_citations=fake_fetch, seed_only=True)

    # Only the seed got expanded.
    assert fetched_dois == ["10.1/seed"]


def test_forward_expansion_seed_only_false_expands_all_papers():
    seed = _seed("10.1/seed")
    corpus = build_corpus_from_seeds([seed], topic="t", fetch_refs=lambda _doi: None)
    extra = _citing("10.1/extra", year=2020)
    corpus.papers["10.1/extra"] = extra

    fetched_dois: list[str] = []

    def fake_fetch(doi: str, limit: int):
        fetched_dois.append(doi)
        return []

    expand_corpus_forward(corpus, fetch_citations=fake_fetch, seed_only=False)

    # Both seed and extra got expanded.
    assert set(fetched_dois) == {"10.1/seed", "10.1/extra"}


def test_forward_expansion_handles_fetcher_exception_gracefully():
    """If the S2 fetcher raises, the seed gets an empty cited_by list, not crash."""
    seed = _seed("10.1/seed")
    corpus = build_corpus_from_seeds([seed], topic="t", fetch_refs=lambda _doi: None)

    def broken_fetch(doi: str, limit: int):
        raise RuntimeError("S2 down")

    expand_corpus_forward(corpus, fetch_citations=broken_fetch)

    # No new papers added; seed has empty cited_by.
    assert corpus.cited_by["10.1/seed"] == []


def test_forward_expansion_skips_already_processed_seeds():
    """Re-running expand_corpus_forward doesn't re-fetch already-processed DOIs."""
    seed = _seed("10.1/seed")
    corpus = build_corpus_from_seeds([seed], topic="t", fetch_refs=lambda _doi: None)
    fetch_count = [0]

    def fake_fetch(doi: str, limit: int):
        fetch_count[0] += 1
        return [_citing("10.1/A", year=2024)]

    expand_corpus_forward(corpus, fetch_citations=fake_fetch)
    expand_corpus_forward(corpus, fetch_citations=fake_fetch)

    # Only fetched once.
    assert fetch_count[0] == 1


def test_forward_expansion_drops_citing_papers_without_doi():
    """Papers without DOIs from S2 don't pollute the corpus."""
    seed = _seed("10.1/seed")
    corpus = build_corpus_from_seeds([seed], topic="t", fetch_refs=lambda _doi: None)

    citing = [
        Paper(title="no-doi", year=2024, doi=""),
        _citing("10.1/has-doi", year=2024),
    ]

    def fake_fetch(doi: str, limit: int):
        return citing

    expand_corpus_forward(corpus, fetch_citations=fake_fetch)

    assert "10.1/has-doi" in corpus.papers
    # The no-DOI paper didn't add anything
    assert "" not in corpus.papers
    # cited_by only contains the DOI'd citing paper
    assert corpus.cited_by["10.1/seed"] == ["10.1/has-doi"]


def test_corpus_cited_by_is_default_empty():
    """Fresh corpus has empty cited_by dict (not None)."""
    seed = _seed("10.1/seed")
    corpus = build_corpus_from_seeds([seed], topic="t", fetch_refs=lambda _doi: None)
    assert corpus.cited_by == {}
