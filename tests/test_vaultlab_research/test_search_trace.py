"""Regression tests for the per-source search trace (Gap 1, evening-5).

The trace sidecar landed because the decisions log was reporting
``n_seeds: 8`` with no per-source breakdown. ``unified_search`` now
returns a ``SearchTrace`` (under ``return_trace=True``) and the lineage
orchestrator emits ``Sources/Notes/<topic>.search-trace.json`` next to
the markdown log. Tests here pin:

1. ``unified_search`` populates per-source hits / errors / wall-time.
2. The trace's ``by_source_after_dedup`` matches the dedup result.
3. The lineage orchestrator writes a JSON sidecar alongside the
   markdown log when the client exposes ``search_with_trace``.
"""

from __future__ import annotations

import json
from pathlib import Path

from vaultlab.research.paper import Paper
from vaultlab.research.search import (
    SearchTrace,
    SourceTrace,
    unified_search,
)


class _StubClient:
    """Minimal stand-in for one of the source clients."""

    def __init__(self, papers: list[Paper], *, raise_exc: Exception | None = None):
        self._papers = papers
        self._raise = raise_exc
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, max_results: int = 20) -> list[Paper]:
        self.calls.append((query, max_results))
        if self._raise is not None:
            raise self._raise
        return list(self._papers)


class TestUnifiedSearchTrace:
    def test_per_source_hits_and_dedup(self) -> None:
        ncbi = _StubClient(
            [
                Paper(
                    title="A",
                    doi="10.1/a",
                    citation_count=10,
                    year=2020,
                    source_api="pubmed",
                ),
                Paper(
                    title="B",
                    doi="10.1/b",
                    citation_count=5,
                    year=2019,
                    source_api="pubmed",
                ),
            ]
        )
        s2 = _StubClient(
            [
                # Same DOI as ncbi/a — should dedupe under "ncbi" since
                # PubMed wins.
                Paper(
                    title="A",
                    doi="10.1/a",
                    citation_count=11,
                    year=2020,
                    source_api="semantic",
                ),
                Paper(
                    title="C",
                    doi="10.1/c",
                    citation_count=2,
                    year=2018,
                    source_api="semantic",
                ),
            ]
        )

        result = unified_search(
            "test query",
            max_results=10,
            ncbi_client=ncbi,
            semantic_client=s2,
            return_trace=True,
        )
        assert isinstance(result, tuple)
        papers, trace = result

        # 2 (ncbi) + 2 (s2) = 4, but A is shared → 3 deduped.
        assert len(papers) == 3
        assert isinstance(trace, SearchTrace)
        assert trace.topic == "test query"
        assert trace.queried_at.endswith("Z")
        assert trace.deduped_seeds == 3

        # Per-source pre-dedup hits.
        assert trace.per_source["ncbi"].hits == 2
        assert trace.per_source["semantic_scholar"].hits == 2
        assert trace.per_source["ncbi"].queries == ["test query"]
        assert trace.per_source["ncbi"].errors == []
        # wall_time_ms is non-negative integer; on fast stubs it's often
        # 0, which is fine.
        assert trace.per_source["ncbi"].wall_time_ms >= 0

        # Dedup result by canonical source: A merged into ncbi (pubmed
        # preferred), B is ncbi, C is semantic_scholar.
        assert trace.by_source_after_dedup.get("ncbi", 0) == 2
        assert trace.by_source_after_dedup.get("semantic_scholar", 0) == 1

    def test_errors_are_recorded_per_source(self) -> None:
        broken = _StubClient([], raise_exc=RuntimeError("rate limited"))
        ok = _StubClient(
            [
                Paper(
                    title="A",
                    doi="10.1/a",
                    year=2020,
                    source_api="pubmed",
                )
            ]
        )
        papers, trace = unified_search(
            "boom",
            ncbi_client=ok,
            semantic_client=broken,
            return_trace=True,
        )
        assert len(papers) == 1
        # The successful tier still landed.
        assert trace.per_source["ncbi"].hits == 1
        assert trace.per_source["ncbi"].errors == []
        # The broken tier captured the exception verbatim.
        s2 = trace.per_source["semantic_scholar"]
        assert s2.hits == 0
        assert s2.errors and "rate limited" in s2.errors[0]

    def test_legacy_signature_still_returns_plain_list(self) -> None:
        """``return_trace=False`` is the default and the return type is
        still ``list[Paper]`` — back-compat for every existing caller."""
        ncbi = _StubClient(
            [
                Paper(
                    title="A",
                    doi="10.1/a",
                    year=2020,
                    source_api="pubmed",
                )
            ]
        )
        out = unified_search("q", ncbi_client=ncbi)
        assert isinstance(out, list)
        assert len(out) == 1


class TestSearchTraceSidecar:
    def test_lineage_writes_search_trace_sidecar(self, tmp_path: Path) -> None:
        """``run_lit_arc`` must emit
        ``Sources/Notes/lit-search-<slug>-<date>.search-trace.json``
        next to the markdown log when the client exposes
        ``search_with_trace``."""
        from vaultlab.research import lineage

        kb_root = tmp_path / "kb"
        kb_root.mkdir()
        topic = "codex multiplexed imaging"
        date_str = "2026-04-30"

        # Direct call to the trace writer with a hand-rolled SearchTrace
        # — that's what the orchestrator does internally. Keeps the test
        # fast (no real network, no full pipeline).
        trace = SearchTrace(
            topic=topic,
            queried_at="2026-04-30T22:01:14Z",
            per_source={
                "ncbi": SourceTrace(queries=[topic], hits=8, wall_time_ms=120),
                "semantic_scholar": SourceTrace(
                    queries=[topic], hits=4, errors=["403"], wall_time_ms=80
                ),
                "biorxiv": SourceTrace(queries=[topic], hits=0, wall_time_ms=30),
            },
            deduped_seeds=10,
            by_source_after_dedup={"ncbi": 7, "semantic_scholar": 3},
        )

        out = lineage._write_search_trace(
            kb_root=kb_root,
            topic=topic,
            date_str=date_str,
            trace=trace,
        )
        assert out is not None
        assert out.exists()
        # Sidecar is co-located with the markdown log under
        # Sources/Notes/.
        assert out.parent == kb_root / "Sources" / "Notes"
        assert out.name.endswith(".search-trace.json")

        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["topic"] == topic
        assert data["deduped_seeds"] == 10
        assert data["per_source"]["ncbi"]["hits"] == 8
        assert data["per_source"]["semantic_scholar"]["errors"] == ["403"]
        assert data["by_source_after_dedup"]["ncbi"] == 7

    def test_search_trace_sidecar_no_trace_returns_none(self, tmp_path: Path) -> None:
        """Trace=None path is silent (legacy clients without
        ``search_with_trace`` shouldn't crash the run)."""
        from vaultlab.research import lineage

        out = lineage._write_search_trace(
            kb_root=tmp_path,
            topic="x",
            date_str="2026-04-30",
            trace=None,
        )
        assert out is None
