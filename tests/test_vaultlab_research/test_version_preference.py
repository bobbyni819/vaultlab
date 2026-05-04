"""Tests for vaultlab.research.version_preference."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from vaultlab.research.corpus import build_corpus_from_seeds
from vaultlab.research.paper import Paper
from vaultlab.research.sources.crossref import CrossRefClient
from vaultlab.research.version_preference import (
    PreprintPublishedPair,
    decide_version_preference,
    filter_duplicates_from_picks,
    find_pairs_from_crossref_relations,
    is_preprint_doi,
)


def test_is_preprint_doi_recognizes_biorxiv_medrxiv():
    assert is_preprint_doi("10.1101/2020.12.06.20244913") is True
    assert is_preprint_doi("10.1101/743989") is True


def test_is_preprint_doi_recognizes_arxiv_via_crossref():
    assert is_preprint_doi("10.48550/arXiv.2310.01234") is True


def test_is_preprint_doi_returns_false_for_published():
    assert is_preprint_doi("10.1038/nature21349") is False
    assert is_preprint_doi("10.1016/j.cell.2018.07.010") is False
    assert is_preprint_doi("") is False


def test_find_pairs_from_is_preprint_of_relation():
    candidates = [
        {
            "doi": "10.1101/preprint1",
            "relation": {
                "is-preprint-of": [
                    {"id": "10.1038/published1", "id-type": "doi"},
                ],
            },
        },
    ]

    pairs = find_pairs_from_crossref_relations(candidates=candidates)
    assert len(pairs) == 1
    assert pairs[0].preprint_doi == "10.1101/preprint1"
    assert pairs[0].published_doi == "10.1038/published1"
    assert pairs[0].relation_source == "is-preprint-of"


def test_find_pairs_from_has_preprint_relation():
    candidates = [
        {
            "doi": "10.1038/published1",
            "relation": {
                "has-preprint": [
                    {"id": "10.1101/preprint1", "id-type": "doi"},
                ],
            },
        },
    ]

    pairs = find_pairs_from_crossref_relations(candidates=candidates)
    assert len(pairs) == 1
    assert pairs[0].preprint_doi == "10.1101/preprint1"
    assert pairs[0].published_doi == "10.1038/published1"
    assert pairs[0].relation_source == "has-preprint"


def test_find_pairs_dedupes_when_both_directions_present():
    """When BOTH the preprint side AND the published side declare the
    relation, we should only emit ONE pair."""
    candidates = [
        {
            "doi": "10.1101/preprint1",
            "relation": {
                "is-preprint-of": [{"id": "10.1038/published1"}],
            },
        },
        {
            "doi": "10.1038/published1",
            "relation": {
                "has-preprint": [{"id": "10.1101/preprint1"}],
            },
        },
    ]

    pairs = find_pairs_from_crossref_relations(candidates=candidates)
    assert len(pairs) == 1


def test_find_pairs_handles_missing_relation_field():
    candidates = [
        {"doi": "10.1101/foo"},
        {"doi": "10.1038/bar", "relation": None},
        {"doi": "10.1101/baz", "relation": {}},
    ]
    assert find_pairs_from_crossref_relations(candidates=candidates) == []


def test_find_pairs_skips_self_referential_relations():
    candidates = [
        {
            "doi": "10.1101/foo",
            "relation": {"is-preprint-of": [{"id": "10.1101/foo"}]},
        },
    ]
    assert find_pairs_from_crossref_relations(candidates=candidates) == []


def test_decide_prefers_published_pdf_when_both_have_pdfs():
    pair = PreprintPublishedPair(
        preprint_doi="10.1101/p", published_doi="10.1038/x"
    )
    pdf_paths = {"10.1101/p": "/preprint.pdf", "10.1038/x": "/published.pdf"}

    decision = decide_version_preference(pair=pair, pdf_paths=pdf_paths)

    assert decision.canonical_doi == "10.1038/x"
    assert decision.canonical_pdf_path == "/published.pdf"
    assert decision.proxy_caveat == ""


def test_decide_uses_preprint_as_proxy_when_only_preprint_has_pdf():
    pair = PreprintPublishedPair(
        preprint_doi="10.1101/p", published_doi="10.1038/x"
    )
    pdf_paths = {"10.1101/p": "/preprint.pdf"}

    decision = decide_version_preference(pair=pair, pdf_paths=pdf_paths)

    assert decision.canonical_doi == "10.1038/x"  # cite the published DOI
    assert decision.canonical_pdf_path == "/preprint.pdf"  # read preprint as proxy
    assert "preprint" in decision.proxy_caveat.lower()
    assert "10.1038/x" in decision.proxy_caveat


def test_decide_picks_published_when_no_pdfs():
    pair = PreprintPublishedPair(
        preprint_doi="10.1101/p", published_doi="10.1038/x"
    )

    decision = decide_version_preference(pair=pair, pdf_paths={})

    assert decision.canonical_doi == "10.1038/x"
    assert decision.canonical_pdf_path == ""  # neither has PDF
    assert decision.proxy_caveat == ""


def test_filter_duplicates_drops_preprint_when_published_present():
    picks = [
        {"doi": "10.1101/preprint1", "rank": 1},
        {"doi": "10.1038/published1", "rank": 2},
        {"doi": "10.1038/other", "rank": 3},
    ]
    pairs = [
        PreprintPublishedPair(
            preprint_doi="10.1101/preprint1",
            published_doi="10.1038/published1",
        ),
    ]

    result = filter_duplicates_from_picks(picks=picks, pairs=pairs)

    dois = [p["doi"] for p in result]
    assert "10.1101/preprint1" not in dois
    assert "10.1038/published1" in dois
    assert "10.1038/other" in dois
    assert [p["rank"] for p in result] == [1, 2]  # ranks rewritten


def test_filter_keeps_preprint_when_published_not_in_picks():
    """If only the preprint is in picks (published was filtered out
    upstream), keep the preprint."""
    picks = [
        {"doi": "10.1101/preprint1", "rank": 1},
        {"doi": "10.1038/other", "rank": 2},
    ]
    pairs = [
        PreprintPublishedPair(
            preprint_doi="10.1101/preprint1",
            published_doi="10.1038/published1",  # NOT in picks
        ),
    ]

    result = filter_duplicates_from_picks(picks=picks, pairs=pairs)
    dois = [p["doi"] for p in result]
    assert "10.1101/preprint1" in dois  # kept


def test_filter_handles_empty_picks_or_pairs():
    assert filter_duplicates_from_picks(picks=[], pairs=[]) == []
    picks = [{"doi": "10.1/a", "rank": 1}]
    assert filter_duplicates_from_picks(picks=picks, pairs=[]) == picks


# ---------------------------------------------------------------------------
# Wiring: Paper.relation, CrossRef parsing, Corpus.preprint_pairs, picker filter
# ---------------------------------------------------------------------------


def test_paper_relation_field_defaults_to_none_for_backward_compat():
    """Paper instantiations that predate the relation field must still work."""
    paper = Paper(title="Old", doi="10.1/x", year=2020)
    assert paper.relation is None
    # to_dict / from_dict round-trips preserve None
    d = paper.to_dict()
    assert d["relation"] is None
    restored = Paper.from_dict(d)
    assert restored.relation is None


def test_paper_relation_field_round_trips_when_populated():
    rel = {"is-preprint-of": [{"id": "10.1038/x", "id-type": "doi"}]}
    paper = Paper(doi="10.1101/p", relation=rel)
    assert paper.relation == rel
    restored = Paper.from_dict(paper.to_dict())
    assert restored.relation == rel


def test_crossref_parse_item_extracts_relation():
    """`_parse_item` must surface CrossRef's `relation` field on the Paper."""
    client = CrossRefClient()
    item = {
        "DOI": "10.1101/preprint1",
        "title": ["Preprint"],
        "author": [{"family": "Smith", "given": "Jane"}],
        "issued": {"date-parts": [[2020]]},
        "relation": {
            "is-preprint-of": [
                {"id": "10.1038/published1", "id-type": "doi"},
            ],
        },
    }
    paper = client._parse_item(item)
    assert paper is not None
    assert paper.relation == {
        "is-preprint-of": [{"id": "10.1038/published1", "id-type": "doi"}],
    }


def test_crossref_parse_item_relation_absent_yields_none():
    """When CrossRef omits `relation`, Paper.relation stays None."""
    client = CrossRefClient()
    item = {
        "DOI": "10.1038/no-relation",
        "title": ["Standalone"],
        "issued": {"date-parts": [[2021]]},
    }
    paper = client._parse_item(item)
    assert paper is not None
    assert paper.relation is None


def test_corpus_preprint_pairs_populated_from_seed_relations():
    """When seed papers carry CrossRef relation metadata, the corpus
    builder should populate ``preprint_pairs`` after walking refs."""
    seeds = [
        Paper(
            doi="10.1101/preprint1",
            year=2020,
            source_api="seed",
            relation={
                "is-preprint-of": [
                    {"id": "10.1038/published1", "id-type": "doi"},
                ],
            },
        ),
        Paper(doi="10.1038/other", year=2021, source_api="seed"),
    ]

    def fake_fetch(_doi):
        # No references fetched — keeps the test focused on relation pairing.
        return None

    corpus = build_corpus_from_seeds(
        seeds, topic="test-pairs", fetch_refs=fake_fetch
    )

    assert len(corpus.preprint_pairs) == 1
    pair = corpus.preprint_pairs[0]
    assert pair.preprint_doi == "10.1101/preprint1"
    assert pair.published_doi == "10.1038/published1"


def test_corpus_preprint_pairs_empty_when_no_relations():
    """Backward-compat: seeds without `relation` produce an empty pair list."""
    seeds = [Paper(doi="10.1/a", year=2018, source_api="seed")]
    corpus = build_corpus_from_seeds(
        seeds, topic="t", fetch_refs=lambda _d: None
    )
    assert corpus.preprint_pairs == []


def test_filter_duplicates_in_picker_postprocessing():
    """Picker post-processing drops the preprint when published is also
    picked — exercises the ``filter_duplicates_from_picks`` integration
    point that the picker calls in-line."""
    picks = [
        {"doi": "10.1101/preprint1", "rank": 1},
        {"doi": "10.1038/published1", "rank": 2},
        {"doi": "10.1038/other", "rank": 3},
    ]
    pairs = [
        PreprintPublishedPair(
            preprint_doi="10.1101/preprint1",
            published_doi="10.1038/published1",
        ),
    ]
    result = filter_duplicates_from_picks(picks=picks, pairs=pairs)

    dois = [p["doi"] for p in result]
    # Preprint dropped, published kept, other untouched.
    assert dois == ["10.1038/published1", "10.1038/other"]
    # Ranks rewritten to 1..N.
    assert [p["rank"] for p in result] == [1, 2]
