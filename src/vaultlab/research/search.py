"""Unified search across all configured APIs with deduplication."""

from __future__ import annotations

import logging

from vaultlab.research.paper import Paper

logger = logging.getLogger(__name__)


def unified_search(
    query: str,
    max_results: int = 20,
    sources: list[str] | None = None,
    ncbi_client=None,
    springer_client=None,
    semantic_client=None,
    crossref_client=None,
    biorxiv_client=None,
) -> list[Paper]:
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

    Returns:
        Deduplicated list of Paper objects, sorted by citation count (desc).
    """
    if sources is None:
        sources = ["pubmed", "springer", "semantic", "crossref", "biorxiv"]

    all_papers: list[Paper] = []

    # Collect results from each source
    if "pubmed" in sources and ncbi_client is not None:
        try:
            papers = ncbi_client.search(query, max_results=max_results)
            all_papers.extend(papers)
            logger.info("PubMed returned %d results", len(papers))
        except Exception as e:
            logger.warning("PubMed search failed: %s", e)

    if "springer" in sources and springer_client is not None:
        try:
            papers = springer_client.search(query, max_results=max_results)
            all_papers.extend(papers)
            logger.info("Springer returned %d results", len(papers))
        except Exception as e:
            logger.warning("Springer search failed: %s", e)

    if "semantic" in sources and semantic_client is not None:
        try:
            papers = semantic_client.search(query, max_results=max_results)
            all_papers.extend(papers)
            logger.info("Semantic Scholar returned %d results", len(papers))
        except Exception as e:
            logger.warning("Semantic Scholar search failed: %s", e)

    if "crossref" in sources and crossref_client is not None:
        try:
            papers = crossref_client.search(query, max_results=max_results)
            all_papers.extend(papers)
            logger.info("CrossRef returned %d results", len(papers))
        except Exception as e:
            logger.warning("CrossRef search failed: %s", e)

    if "biorxiv" in sources and biorxiv_client is not None:
        try:
            papers = biorxiv_client.search(query, max_results=max_results)
            all_papers.extend(papers)
            logger.info("bioRxiv returned %d results", len(papers))
        except Exception as e:
            logger.warning("bioRxiv search failed: %s", e)

    # Deduplicate by DOI
    deduped = _deduplicate(all_papers)

    # Sort by citation count (desc), then year (desc)
    deduped.sort(key=lambda p: (p.citation_count, p.year), reverse=True)

    logger.info("Unified search: %d total -> %d after dedup", len(all_papers), len(deduped))
    return deduped


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
