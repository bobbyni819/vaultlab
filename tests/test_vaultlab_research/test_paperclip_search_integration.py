"""Tests for paperclip integration into ``unified_search``.

Per the 2026-05-02 paperclip integration design (Q1: parallel source,
Q5: graceful degradation, Q6: no domain detection), paperclip is the
7th parallel source — runs in fan-out alongside PubMed/S2/CrossRef/
biorxiv/Springer/Elsevier, DOI-deduped on output. Failures (missing
auth, binary not on PATH, etc.) are absorbed by ``_run_source`` and
the pipeline continues with the other 6 sources.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from vaultlab.research.paper import Paper
from vaultlab.research.search import (
    _SOURCE_TO_TRACE_KEY,
    unified_search,
)
from vaultlab.research.sources.paperclip import PaperclipUnavailable


def test_paperclip_is_in_default_sources():
    """Default sources list must include paperclip per Q1."""
    # Trigger default-sources resolution by passing sources=None and
    # inspecting the trace.
    fake_paperclip = MagicMock()
    fake_paperclip.search = MagicMock(return_value=[])

    _, trace = unified_search(
        query="test",
        paperclip_client=fake_paperclip,
        return_trace=True,
    )
    assert "paperclip" in trace.per_source


def test_paperclip_in_trace_key_map():
    """Trace key must be 'paperclip' for the public source name."""
    assert _SOURCE_TO_TRACE_KEY["paperclip"] == "paperclip"


def test_paperclip_results_merge_with_other_sources():
    """Papers from paperclip dedupe by DOI alongside other sources."""
    paperclip = MagicMock()
    paperclip.search = MagicMock(return_value=[
        Paper(
            doi="10.1/x",
            title="Paper X",
            year=2024,
            source_api="paperclip",
        ),
    ])

    pubmed = MagicMock()
    pubmed.search = MagicMock(return_value=[
        Paper(
            doi="10.1/y",
            title="Paper Y",
            year=2024,
            source_api="ncbi",
        ),
    ])

    papers = unified_search(
        query="test",
        sources=["pubmed", "paperclip"],
        ncbi_client=pubmed,
        paperclip_client=paperclip,
    )
    dois = {p.doi for p in papers}
    assert dois == {"10.1/x", "10.1/y"}


def test_paperclip_dedupes_with_overlapping_doi():
    """When paperclip and another source return the same DOI, the
    paper appears once after dedup."""
    same_doi = "10.1/shared"
    paperclip = MagicMock()
    paperclip.search = MagicMock(return_value=[
        Paper(doi=same_doi, title="Paper", year=2024, source_api="paperclip"),
    ])
    biorxiv = MagicMock()
    biorxiv.search = MagicMock(return_value=[
        Paper(doi=same_doi, title="Paper", year=2024, source_api="biorxiv"),
    ])

    papers = unified_search(
        query="test",
        sources=["biorxiv", "paperclip"],
        biorxiv_client=biorxiv,
        paperclip_client=paperclip,
    )
    assert len(papers) == 1
    assert papers[0].doi == same_doi


def test_paperclip_unauthenticated_does_not_break_other_sources():
    """Per Q5, PaperclipUnavailable from .search() is absorbed and the
    rest of the parallel fan-out continues uninterrupted."""
    paperclip = MagicMock()
    paperclip.search = MagicMock(side_effect=PaperclipUnavailable(
        "paperclip is unauthenticated"
    ))

    pubmed = MagicMock()
    pubmed.search = MagicMock(return_value=[
        Paper(doi="10.1/y", title="Paper Y", year=2024, source_api="ncbi"),
    ])

    papers = unified_search(
        query="test",
        sources=["pubmed", "paperclip"],
        ncbi_client=pubmed,
        paperclip_client=paperclip,
    )
    # Other sources still produce results
    assert len(papers) == 1
    assert papers[0].doi == "10.1/y"


def test_paperclip_skipped_when_client_is_none():
    """Per Q5, when paperclip_client is None, the paperclip source is
    silently skipped (no error)."""
    pubmed = MagicMock()
    pubmed.search = MagicMock(return_value=[
        Paper(doi="10.1/y", title="Paper Y", year=2024, source_api="ncbi"),
    ])

    _, trace = unified_search(
        query="test",
        sources=["pubmed", "paperclip"],
        ncbi_client=pubmed,
        paperclip_client=None,
        return_trace=True,
    )
    # paperclip should appear in the per_source trace from the trace-init
    # step, but with hits=0 and no errors — i.e., it was a no-op.
    pc_trace = trace.per_source.get("paperclip")
    assert pc_trace is not None
    assert pc_trace.hits == 0
    assert pc_trace.errors == []


def test_paperclip_records_errors_in_trace():
    """When paperclip raises during search, the error is recorded in
    the trace's per-source ``errors`` list (per Q5 graceful degrade)."""
    paperclip = MagicMock()
    paperclip.search = MagicMock(side_effect=PaperclipUnavailable("nope"))

    _, trace = unified_search(
        query="test",
        sources=["paperclip"],
        paperclip_client=paperclip,
        return_trace=True,
    )
    pc_trace = trace.per_source["paperclip"]
    assert pc_trace.hits == 0
    assert len(pc_trace.errors) == 1
    assert "nope" in pc_trace.errors[0] or "PaperclipUnavailable" in pc_trace.errors[0]


def test_paperclip_runs_in_parallel_with_six_other_sources():
    """All 7 sources run when paperclip_client is given alongside
    pubmed/springer/semantic/crossref/biorxiv/scopus."""
    paperclip = MagicMock()
    paperclip.search = MagicMock(return_value=[
        Paper(doi="10.1/x", title="X", year=2024, source_api="paperclip"),
    ])
    other = MagicMock()
    other.search = MagicMock(return_value=[])

    _, trace = unified_search(
        query="test",
        ncbi_client=other,
        springer_client=other,
        semantic_client=other,
        crossref_client=other,
        biorxiv_client=other,
        sciencedirect_client=other,
        paperclip_client=paperclip,
        return_trace=True,
    )
    # All 7 sources should have a per-source trace entry
    expected = {"ncbi", "springer", "semantic_scholar", "crossref",
                "biorxiv", "scopus", "paperclip"}
    actual = set(trace.per_source.keys())
    assert expected.issubset(actual)


def test_paperclip_results_are_marked_with_source_api():
    """Papers returned via paperclip carry source_api='paperclip' so
    downstream consumers (composite_score, recency_quota, etc.) can
    weight or filter accordingly."""
    paperclip = MagicMock()
    paperclip.search = MagicMock(return_value=[
        Paper(
            doi="10.1/x",
            title="From paperclip",
            year=2024,
            source_api="paperclip",
        ),
    ])
    papers = unified_search(
        query="test",
        sources=["paperclip"],
        paperclip_client=paperclip,
    )
    assert len(papers) == 1
    assert papers[0].source_api == "paperclip"
