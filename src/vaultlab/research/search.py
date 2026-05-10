"""Unified search across all configured APIs with deduplication."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import UTC
from typing import Any

from vaultlab.research.paper import Paper

logger = logging.getLogger(__name__)


# Public source-name → "trace key" mapping. We keep these stable so the
# emitted ``.search-trace.json`` sidecars are diffable across runs.
# ``unified_search`` accepts ``sources=["pubmed", ...]`` for the historical
# alias; the trace shape uses the canonical name (e.g. ``ncbi``) so it
# matches the actual API surface used.
_SOURCE_TO_TRACE_KEY: dict[str, str] = {
    "pubmed": "ncbi",
    "ncbi": "ncbi",
    "springer": "springer",
    "semantic": "semantic_scholar",
    "semantic_scholar": "semantic_scholar",
    "crossref": "crossref",
    "biorxiv": "biorxiv",
    "scopus": "scopus",
    "sciencedirect": "scopus",  # ScienceDirect search unsupported — uses Scopus
    "elsevier": "scopus",  # legacy alias for the Elsevier-cluster source
    "paperclip": "paperclip",  # 8M-paper biomedical full-text corpus (2026-05-02)
}


@dataclass
class SourceTrace:
    """Per-source fingerprint of a single ``unified_search`` call.

    Attributes:
        queries: Query strings actually issued (we currently issue one,
            but this is a list for forward-compat with multi-pass query
            expansion).
        hits: Number of papers returned by this source BEFORE dedup.
        errors: Free-text error strings (one per failed call).
        wall_time_ms: Wall-clock time spent in this source's branch.
    """

    queries: list[str] = field(default_factory=list)
    hits: int = 0
    errors: list[str] = field(default_factory=list)
    wall_time_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "queries": list(self.queries),
            "hits": int(self.hits),
            "errors": list(self.errors),
            "wall_time_ms": int(self.wall_time_ms),
        }


@dataclass
class SearchTrace:
    """Per-source trace of a unified_search call.

    Carries ``per_source`` (one :class:`SourceTrace` per canonical source
    name), the deduped-seed count, and the per-source distribution AFTER
    dedup so the user can see which API "won" for each surviving paper.
    """

    topic: str = ""
    queried_at: str = ""
    per_source: dict[str, SourceTrace] = field(default_factory=dict)
    deduped_seeds: int = 0
    by_source_after_dedup: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "queried_at": self.queried_at,
            "per_source": {k: v.to_dict() for k, v in self.per_source.items()},
            "deduped_seeds": int(self.deduped_seeds),
            "by_source_after_dedup": dict(self.by_source_after_dedup),
        }


def unified_search(
    query: str,
    max_results: int = 50,
    sources: list[str] | None = None,
    ncbi_client=None,
    springer_client=None,
    semantic_client=None,
    crossref_client=None,
    biorxiv_client=None,
    sciencedirect_client=None,
    paperclip_client=None,
    return_trace: bool = False,
    recency_weight: float | None = None,
    queries: list[str] | None = None,
) -> list[Paper] | tuple[list[Paper], SearchTrace]:
    """Search across multiple APIs and deduplicate results.

    Results are deduplicated by DOI. When the same paper appears from multiple
    sources, metadata is merged (PubMed data is preferred for bio papers).

    Args:
        query: Search query string.
        max_results: Maximum results per source.
        sources: List of source names to search. Defaults to all available.
            Options: "pubmed", "springer", "semantic", "crossref", "biorxiv".
        ncbi_client: NCBIClient instance (or None to skip).
        springer_client: SpringerClient instance (or None to skip).
        semantic_client: SemanticScholarClient instance (or None to skip).
        crossref_client: CrossRefClient instance (or None to skip).
        biorxiv_client: BioRxivClient instance (or None to skip).
        return_trace: When ``True``, return ``(papers, SearchTrace)`` so
            callers can emit a ``.search-trace.json`` sidecar with
            per-source hit counts, errors, and wall-time. Defaults to
            ``False`` for backward compatibility.
        recency_weight: Float in ``[0, 1]`` blending citations-per-year
            and absolute citation count for the post-dedup ranking. ``None``
            uses :data:`vaultlab.research.scoring.DEFAULT_RECENCY_WEIGHT`
            (0.6). Pass ``0.0`` to recover the legacy citation-count-only
            order.
        queries: Optional list of query variants to fan out across. When
            given, each variant is run against every source and the
            combined results are deduplicated. The original ``query``
            argument is ignored. Use
            :func:`vaultlab.research.query_expansion.expand_query` to
            produce variants. ``None`` (default) preserves single-query
            behaviour.

    Returns:
        List of deduplicated :class:`Paper` (default) or
        ``(papers, trace)`` when ``return_trace=True``. Papers are sorted
        by recency-blended score (citations/year + absolute citations,
        log-squashed), with year as tiebreaker.
    """
    if sources is None:
        sources = [
            "pubmed",
            "springer",
            "semantic",
            "crossref",
            "biorxiv",
            "scopus",
            "paperclip",
        ]

    # ------------------------------------------------------------------
    # Resolve query list. ``queries`` (multi-query expansion) wins over
    # the single ``query`` arg when given. The trace's ``topic`` is the
    # FIRST query so the sidecar still labels the run with something
    # readable.
    # ------------------------------------------------------------------
    query_list: list[str] = list(queries) if queries else [query]
    if not query_list:
        query_list = [query]
    primary_query = query_list[0]

    all_papers: list[Paper] = []
    trace = SearchTrace(
        topic=primary_query,
        queried_at=_iso_utc_now(),
        per_source={
            _SOURCE_TO_TRACE_KEY[s]: SourceTrace(queries=list(query_list))
            for s in sources
            if s in _SOURCE_TO_TRACE_KEY
        },
    )
    # Track which source returned each paper (pre-dedup).
    pre_dedup_source_by_paper: list[str] = []

    # Fan out: for each variant, hit every configured source. Across
    # variants we accumulate hits; dedup-by-DOI runs once at the end.
    for q in query_list:
        if "pubmed" in sources and ncbi_client is not None:
            papers = _run_source(
                "ncbi",
                trace,
                lambda c=ncbi_client, qq=q: c.search(qq, max_results=max_results),
                accumulate=True,
            )
            all_papers.extend(papers)
            pre_dedup_source_by_paper.extend(["ncbi"] * len(papers))

        if "springer" in sources and springer_client is not None:
            papers = _run_source(
                "springer",
                trace,
                lambda c=springer_client, qq=q: c.search(qq, max_results=max_results),
                accumulate=True,
            )
            all_papers.extend(papers)
            pre_dedup_source_by_paper.extend(["springer"] * len(papers))

        if "semantic" in sources and semantic_client is not None:
            papers = _run_source(
                "semantic_scholar",
                trace,
                lambda c=semantic_client, qq=q: c.search(qq, max_results=max_results),
                accumulate=True,
            )
            all_papers.extend(papers)
            pre_dedup_source_by_paper.extend(["semantic_scholar"] * len(papers))

        if "crossref" in sources and crossref_client is not None:
            papers = _run_source(
                "crossref",
                trace,
                lambda c=crossref_client, qq=q: c.search(qq, max_results=max_results),
                accumulate=True,
            )
            all_papers.extend(papers)
            pre_dedup_source_by_paper.extend(["crossref"] * len(papers))

        if "biorxiv" in sources and biorxiv_client is not None:
            papers = _run_source(
                "biorxiv",
                trace,
                lambda c=biorxiv_client, qq=q: c.search(qq, max_results=max_results),
                accumulate=True,
            )
            all_papers.extend(papers)
            pre_dedup_source_by_paper.extend(["biorxiv"] * len(papers))

        if (
            "scopus" in sources or "sciencedirect" in sources or "elsevier" in sources
        ) and sciencedirect_client is not None:
            papers = _run_source(
                "scopus",
                trace,
                lambda c=sciencedirect_client, qq=q: c.search(qq, max_results=max_results),
                accumulate=True,
            )
            all_papers.extend(papers)
            pre_dedup_source_by_paper.extend(["scopus"] * len(papers))

        if "paperclip" in sources and paperclip_client is not None:
            # Per design-doc Q1 (2026-05-02), paperclip is the 7th parallel
            # source — surfaces papers (especially arXiv preprints + recent
            # 2024-2025 SOTA) that the live PubMed/S2/CrossRef/biorxiv/
            # Springer/Elsevier stack misses.
            #
            # Per Q5, PaperclipUnavailable raised inside .search (missing
            # auth, missing binary, etc.) is caught by _run_source and
            # recorded as a per-source error in the trace. The pipeline
            # continues with the other 6 sources. No exception leaks out.
            papers = _run_source(
                "paperclip",
                trace,
                lambda c=paperclip_client, qq=q: c.search(qq, max_results=max_results),
                accumulate=True,
            )
            all_papers.extend(papers)
            pre_dedup_source_by_paper.extend(["paperclip"] * len(papers))

    # Deduplicate by DOI
    deduped = _deduplicate(all_papers)

    # Sort by recency-balanced blended score (citations/year + log-citation-count).
    # See vaultlab.research.scoring.blended_paper_score for the formula.
    # Pass ``recency_weight=0.0`` to recover the legacy "citation_count desc" order.
    from vaultlab.research.scoring import (
        DEFAULT_RECENCY_WEIGHT,
        blended_paper_score,
    )

    rw = DEFAULT_RECENCY_WEIGHT if recency_weight is None else float(recency_weight)
    deduped.sort(
        key=lambda p: (blended_paper_score(p, recency_weight=rw), p.year),
        reverse=True,
    )

    # Populate by_source_after_dedup. For each surviving paper we use
    # ``paper.source_api`` (set by the source clients). Papers merged
    # from multiple sources retain whichever source_api won during
    # _deduplicate (pubmed-preferred); that's the right answer because
    # the merged record's *primary* source is the one whose metadata
    # we kept.
    by_source: dict[str, int] = {}
    for paper in deduped:
        key = (getattr(paper, "source_api", "") or "").strip().lower() or "unknown"
        # Normalize to canonical trace key so 'pubmed' ⇒ 'ncbi'.
        canonical = _SOURCE_TO_TRACE_KEY.get(key, key)
        by_source[canonical] = by_source.get(canonical, 0) + 1
    trace.deduped_seeds = len(deduped)
    trace.by_source_after_dedup = by_source

    logger.info("Unified search: %d total -> %d after dedup", len(all_papers), len(deduped))
    if return_trace:
        return deduped, trace
    return deduped


def _run_source(
    canonical_key: str,
    trace: SearchTrace,
    fn: Any,
    *,
    accumulate: bool = False,
) -> list[Paper]:
    """Invoke a per-source search ``fn`` and record stats into ``trace``.

    Args:
        canonical_key: Trace-key for this source ("ncbi", "crossref", ...).
        trace: The :class:`SearchTrace` to record stats into.
        fn: The zero-arg callable that performs the search.
        accumulate: When ``True``, hits and wall-time are summed across
            calls (used for multi-query fan-out so the trace records the
            total hits across all variants, not just the last one). When
            ``False`` (default), behaves as before — overwrites any prior
            stats. Errors always append, regardless.
    """
    started = time.time()
    try:
        papers = fn() or []
        elapsed_ms = int((time.time() - started) * 1000)
        slot = trace.per_source.setdefault(canonical_key, SourceTrace())
        if accumulate:
            slot.hits += len(papers)
            slot.wall_time_ms += elapsed_ms
        else:
            slot.hits = len(papers)
            slot.wall_time_ms = elapsed_ms
        logger.info("%s returned %d results", canonical_key, len(papers))
        return papers
    except Exception as e:
        elapsed_ms = int((time.time() - started) * 1000)
        slot = trace.per_source.setdefault(canonical_key, SourceTrace())
        slot.errors.append(repr(e))
        if accumulate:
            slot.wall_time_ms += elapsed_ms
        else:
            slot.wall_time_ms = elapsed_ms
        logger.warning("%s search failed: %s", canonical_key, e)
        return []


def _iso_utc_now() -> str:
    """Return an ISO-8601 UTC timestamp ('Z' suffix) — kept tight for sidecars."""
    from datetime import datetime

    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _deduplicate(papers: list[Paper]) -> list[Paper]:
    """Deduplicate papers by DOI, merging metadata from multiple sources.

    Papers from PubMed are preferred as the base record for biological papers
    because PubMed has the most reliable metadata for biomedical literature.
    """
    # Group papers by DOI
    by_doi: dict[str, list[Paper]] = {}
    no_doi: list[Paper] = []

    for paper in papers:
        doi = paper.doi.strip().lower() if paper.doi else ""
        if doi:
            by_doi.setdefault(doi, []).append(paper)
        else:
            no_doi.append(paper)

    merged: list[Paper] = []

    for group in by_doi.values():
        if len(group) == 1:
            merged.append(group[0])
        else:
            # Prefer PubMed as base, then merge from others
            base = None
            others = []
            for p in group:
                if p.source_api == "pubmed" and base is None:
                    base = p
                else:
                    others.append(p)
            if base is None:
                base = group[0]
                others = group[1:]

            for other in others:
                base.merge(other)

            merged.append(base)

    # Deduplicate no-DOI papers by title similarity (simple exact match)
    seen_titles = set()
    for p in no_doi:
        title_key = p.title.strip().lower()
        if title_key and title_key not in seen_titles:
            # Check if we already have this title from a DOI paper
            already_have = any(m.title.strip().lower() == title_key for m in merged)
            if not already_have:
                seen_titles.add(title_key)
                merged.append(p)

    return merged
