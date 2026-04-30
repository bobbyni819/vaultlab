"""Unit tests for vaultlab.research.graph_metrics.

Synthetic 5-paper corpus with hand-checked metric values.
"""

from __future__ import annotations

from vaultlab.research.citation_lookup import Reference
from vaultlab.research.corpus import build_corpus_from_seeds
from vaultlab.research.graph_metrics import (
    CorpusMetrics,
    _year_bucket_assignments,
    compute_metrics,
)
from vaultlab.research.paper import Paper


# ---------------------------------------------------------------------------
# Synthetic corpus (matches the test_corpus.py fixture)
# ---------------------------------------------------------------------------
#
#   A (2017) --> X (1990), Y (2000), B (2018)
#   B (2018) --> X (1990), Y (2000)
#   C (2019) --> Y (2000), A (2017)
#
# Hand-computed expected metrics:
#
#   og_score (with 3 seed papers having refs):
#     X: 2/3 ~ 0.667
#     Y: 3/3 = 1.0
#     B: 1/3 ~ 0.333
#     A: 1/3 ~ 0.333
#
#   forward_influence (only A, B, C in seed set):
#     A: 1 (cited by C)
#     B: 1 (cited by A)
#     C: 0
#
#   co_citation_pairs (>= 2 corpus papers cite both):
#     (X, Y): 2 (A and B both cite X and Y)
#
#   year_buckets (5 papers: years 1990, 2000, 2017, 2018, 2019):
#     X (1990): history
#     Y (2000): development
#     A (2017): development
#     B (2018): sota
#     C (2019): sota


def _seed(doi: str, year: int) -> Paper:
    return Paper(title=doi, doi=doi, year=year, source_api="seed")


def _ref(doi: str, year: int = 0) -> Reference:
    return Reference(doi=doi, year=year, title=doi)


def _build_test_corpus():
    seeds = [
        _seed("10.1/a", 2017),
        _seed("10.1/b", 2018),
        _seed("10.1/c", 2019),
    ]

    table = {
        "10.1/a": [_ref("10.1/x", 1990), _ref("10.1/y", 2000), _ref("10.1/b", 2018)],
        "10.1/b": [_ref("10.1/x", 1990), _ref("10.1/y", 2000)],
        "10.1/c": [_ref("10.1/y", 2000), _ref("10.1/a", 2017)],
    }

    return build_corpus_from_seeds(
        seeds,
        topic="t",
        fetch_refs=lambda doi: table.get(doi.lower()),
    )


# ---------------------------------------------------------------------------
# OG score
# ---------------------------------------------------------------------------


class TestOgScore:
    def test_expected_values(self):
        corpus = _build_test_corpus()
        metrics = compute_metrics(corpus)
        assert metrics.og_score["10.1/y"] == 1.0
        assert abs(metrics.og_score["10.1/x"] - 2 / 3) < 1e-9
        assert abs(metrics.og_score["10.1/a"] - 1 / 3) < 1e-9
        assert abs(metrics.og_score["10.1/b"] - 1 / 3) < 1e-9
        assert "10.1/c" not in metrics.og_score  # never cited

    def test_attaches_to_corpus(self):
        corpus = _build_test_corpus()
        metrics = compute_metrics(corpus)
        assert corpus.metrics is metrics

    def test_top_og_returns_sorted_pairs(self):
        corpus = _build_test_corpus()
        metrics = compute_metrics(corpus)
        top = metrics.top_og(n=2)
        assert len(top) == 2
        assert top[0][0] == "10.1/y"  # 1.0
        assert top[0][1] == 1.0


# ---------------------------------------------------------------------------
# Forward influence
# ---------------------------------------------------------------------------


class TestForwardInfluence:
    def test_seed_subgraph_in_degrees(self):
        corpus = _build_test_corpus()
        metrics = compute_metrics(corpus)
        assert metrics.forward_influence["10.1/a"] == 1
        assert metrics.forward_influence["10.1/b"] == 1
        assert metrics.forward_influence["10.1/c"] == 0

    def test_only_seeds_get_keys(self):
        corpus = _build_test_corpus()
        metrics = compute_metrics(corpus)
        # X, Y are not seeds — should not appear in forward_influence
        assert "10.1/x" not in metrics.forward_influence
        assert "10.1/y" not in metrics.forward_influence


# ---------------------------------------------------------------------------
# Co-citation pairs
# ---------------------------------------------------------------------------


class TestCoCitationPairs:
    def test_pair_x_y_is_top(self):
        corpus = _build_test_corpus()
        metrics = compute_metrics(corpus)
        pairs = {(a, b): c for a, b, c in metrics.co_citation_pairs}
        assert ("10.1/x", "10.1/y") in pairs
        assert pairs[("10.1/x", "10.1/y")] == 2

    def test_pairs_sorted_descending(self):
        corpus = _build_test_corpus()
        metrics = compute_metrics(corpus)
        counts = [c for _a, _b, c in metrics.co_citation_pairs]
        assert counts == sorted(counts, reverse=True)


# ---------------------------------------------------------------------------
# Year buckets
# ---------------------------------------------------------------------------


class TestYearBuckets:
    def test_history_development_sota_present(self):
        corpus = _build_test_corpus()
        metrics = compute_metrics(corpus)
        buckets = set(metrics.year_buckets.values())
        assert "history" in buckets
        assert "development" in buckets
        assert "sota" in buckets

    def test_oldest_is_history(self):
        corpus = _build_test_corpus()
        metrics = compute_metrics(corpus)
        assert metrics.year_buckets["10.1/x"] == "history"

    def test_newest_is_sota(self):
        corpus = _build_test_corpus()
        metrics = compute_metrics(corpus)
        assert metrics.year_buckets["10.1/c"] == "sota"

    def test_year_zero_is_unknown(self):
        years = {"a": 2020, "b": 0, "c": 2010}
        out = _year_bucket_assignments(years)
        assert out["b"] == "unknown"

    def test_handles_three_papers(self):
        years = {"a": 2000, "b": 2010, "c": 2020}
        out = _year_bucket_assignments(years)
        assert out == {"a": "history", "b": "development", "c": "sota"}

    def test_handles_one_paper(self):
        years = {"a": 2020}
        out = _year_bucket_assignments(years)
        assert out == {"a": "sota"}

    def test_no_valid_years_all_unknown(self):
        out = _year_bucket_assignments({"a": 0, "b": 0})
        assert out == {"a": "unknown", "b": "unknown"}


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_compute_metrics_on_empty_corpus_returns_empty():
    from vaultlab.research.corpus import Corpus

    corpus = Corpus(topic="t", seeds=[])
    metrics = compute_metrics(corpus)
    assert metrics.og_score == {}
    assert metrics.forward_influence == {}
    assert metrics.co_citation_pairs == []
    assert metrics.year_buckets == {}


def test_corpus_metrics_dataclass_defaults():
    m = CorpusMetrics()
    assert m.og_score == {}
    assert m.forward_influence == {}
    assert m.co_citation_pairs == []
    assert m.year_buckets == {}


def test_dedup_within_same_paper():
    """If a single paper accidentally references the same DOI twice, OG count is 1."""
    from vaultlab.research.corpus import build_corpus_from_seeds

    seeds = [_seed("10.1/a", 2020)]
    fetch = lambda doi: [_ref("10.1/x", 1990), _ref("10.1/x", 1990)]  # noqa: E731
    corpus = build_corpus_from_seeds(seeds, fetch_refs=fetch)
    metrics = compute_metrics(corpus)
    assert metrics.og_score["10.1/x"] == 1.0  # 1 of 1 paper, deduped
