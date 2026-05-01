"""vaultlab.research — Scientific literature search across NCBI, Springer, Semantic Scholar.

Search, fetch, and manage scientific papers from multiple APIs with a
unified interface. Designed for use with bobby_kb and Obsidian knowledge bases.

Usage:
    from vaultlab.research import ResearchClient, search_papers, get_paper, download_pdf

    client = ResearchClient()
    results = client.search("lysophosphatidylinositol intestine", max_results=10)
    for paper in results:
        print(f"{paper.title} ({paper.year}) - {paper.journal}")

Citation methodology
--------------------
The lineage-arc pipeline ranks papers by **og_score** — Kessler (1963)
bibliographic coupling against the seed set: ``og_score(p) = fraction of
seed papers that cite p``. Co-citation pairs follow Small (1973). For a
full treatment of the metrics, year-bucketing, anonymous-author
handling, and "when og_score is misleading", see
``vaultlab/docs/methodology.md`` (canonical reference).

A high og_score does NOT mean a paper is topically relevant — it means
the seed set's authors thought it was foundational. The content-aware
picker (``vaultlab.research.picker``) reads abstracts before ranking so
it can override og_score when an abstract disagrees with the citation
signal. Run with ``picker_mode="adversarial"`` whenever the seed set is
heterogeneous or the topic is application-heavy.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from vaultlab.research.acquisition import (
    AcquisitionResult,
    acquire_pdf,
    acquire_pdfs_for_corpus,
)
from vaultlab.research.binning import (
    BinningCallback,
    BinningCandidate,
    BinningResult,
    BinningTask,
    assign_buckets_with_llm,
    binning_response_schema,
    prepare_binning_task,
    render_binning_from_response,
)
from vaultlab.research.citation_graph import CitationGraph
from vaultlab.research.citation_lookup import (
    RateLimitError,
    Reference,
    get_citations_via_s2,
    get_influential_count_via_s2,
    get_references_via_crossref,
)
from vaultlab.research.corpus import Corpus, build_corpus_from_seeds, expand_corpus
from vaultlab.research.data_utils import detect_data_format
from vaultlab.research.figures import extract_figures, write_figure_notes
from vaultlab.research.graph_metrics import CorpusMetrics, compute_metrics
from vaultlab.research.lineage import (
    ArcNarrator,
    ArcTask,
    DepthLevel,
    LineageRunResult,
    arc_response_schema,
    prepare_arc_task,
    render_arc_from_response,
    run_lit_arc,
)
from vaultlab.research.report import (
    SECTION_ORDER,
    SECTION_ROLES,
    SECTION_WORD_TARGETS,
    ReportRunResult,
    ReportTask,
    Section,
    build_section_prompt,
    prepare_report_task,
    render_section_from_response,
    run_lit_report,
    section_response_schema,
)
from vaultlab.research.picker import (
    CandidatePaper,
    PickerCallback,
    PickerTask,
    pick_top_n_content_aware,
    picker_response_schema,
    prepare_picker_task,
    render_picks_from_response,
)

if TYPE_CHECKING:
    from vaultlab.research.verification import (
        ClaimMatch,
        EvidenceRecord,
        VerificationResult,
    )
from vaultlab.research.paper import Paper
from vaultlab.research.pdf import batch_extract, extract_and_save, extract_text
from vaultlab.research.session import Finding, FindingStatus, ResearchSession
from vaultlab.research.summarize import (
    PaperSummary,
    SummarizationTask,
    SummarizeAuthError,
    SummaryReader,
    prepare_summary_task,
    render_summary_from_response,
    summarize_corpus,
    summarize_paper,
    summary_response_schema,
    write_summary_to_kb,
)

logger = logging.getLogger(__name__)

__all__ = [
    # PDF acquisition waterfall
    "AcquisitionResult",
    "ArcNarrator",
    "ArcTask",
    "BinningCallback",
    "BinningCandidate",
    "BinningResult",
    "BinningTask",
    "CandidatePaper",
    "CitationGraph",
    # Citation graph corpus / metrics (literature-search v2)
    "Corpus",
    "CorpusMetrics",
    "DepthLevel",
    "Finding",
    "FindingStatus",
    "LineageRunResult",
    "Paper",
    "PaperSummary",
    "PickerCallback",
    "PickerTask",
    "RateLimitError",
    "Reference",
    "ReportRunResult",
    "ReportTask",
    "ResearchClient",
    "ResearchSession",
    "SECTION_ORDER",
    "SECTION_ROLES",
    "SECTION_WORD_TARGETS",
    "Section",
    "SummarizationTask",
    "SummarizeAuthError",
    "SummaryReader",
    "acquire_pdf",
    "acquire_pdfs_for_corpus",
    "arc_response_schema",
    "assign_buckets_with_llm",
    "batch_extract",
    "binning_response_schema",
    "build_corpus_from_seeds",
    "build_section_prompt",
    "compute_metrics",
    # Data format detection
    "detect_data_format",
    "download_pdf",
    "expand_corpus",
    "extract_and_save",
    # Figure extraction
    "extract_figures",
    # PDF extraction
    "extract_text",
    "get_citations_via_s2",
    "get_influential_count_via_s2",
    "get_paper",
    "get_references_via_crossref",
    "pick_top_n_content_aware",
    "picker_response_schema",
    "prepare_arc_task",
    "prepare_binning_task",
    "prepare_picker_task",
    "prepare_report_task",
    "prepare_summary_task",
    "render_arc_from_response",
    "render_binning_from_response",
    "render_picks_from_response",
    "render_section_from_response",
    "render_summary_from_response",
    "run_lit_arc",
    "run_lit_report",
    "search_papers",
    "section_response_schema",
    "summarize_corpus",
    "summarize_paper",
    "summary_response_schema",
    "write_figure_notes",
    "write_summary_to_kb",
]


class ResearchClient:
    """Unified client for searching scientific literature across APIs.

    Automatically discovers API keys from the config file on Google Drive
    and initializes clients for each available API.

    Args:
        config_path: Override path to the API keys JSON file.
            Defaults to G:/My Drive/Knowledge/tools/.config/research_apis.json
    """

    def __init__(self, config_path: str | None = None):
        from vaultlab.research.config import get_config, get_key

        self._config = get_config(config_path)

        # Initialize clients for each API that has a key
        self._ncbi = None
        self._springer = None
        self._semantic = None
        self._crossref = None
        self._biorxiv = None
        self._sciencedirect = None

        # CrossRef and bioRxiv are free (no API key needed)
        try:
            from vaultlab.research.sources.crossref import CrossRefClient

            self._crossref = CrossRefClient()
            logger.debug("CrossRef client initialized")
        except Exception:
            pass

        try:
            from vaultlab.research.sources.biorxiv import BioRxivClient

            self._biorxiv = BioRxivClient()
            logger.debug("bioRxiv client initialized")
        except Exception:
            pass

        ncbi_key = get_key("ncbi_api_key", config_path)
        if ncbi_key:
            from vaultlab.research.sources.ncbi import NCBIClient

            self._ncbi = NCBIClient(api_key=ncbi_key)
            logger.debug("NCBI client initialized")

        springer_oa = get_key("springer_open_access_api_key", config_path)
        springer_meta = get_key("springer_meta_api_key", config_path)
        if springer_oa or springer_meta:
            from vaultlab.research.sources.springer import SpringerClient

            self._springer = SpringerClient(
                meta_api_key=springer_meta,
                oa_api_key=springer_oa,
            )
            logger.debug("Springer client initialized")

        semantic_key = get_key("semantic_scholar_api_key", config_path)
        if semantic_key:
            from vaultlab.research.sources.semantic import SemanticScholarClient

            self._semantic = SemanticScholarClient(api_key=semantic_key)
            logger.debug("Semantic Scholar client initialized")

        elsevier_key = get_key("elsevier_key", config_path)
        if elsevier_key:
            from vaultlab.research.sources.elsevier import ElsevierClient

            self._sciencedirect = ElsevierClient(api_key=elsevier_key)
            logger.debug("Scopus (Elsevier) client initialized")

        available = []
        if self._ncbi:
            available.append("pubmed")
        if self._springer:
            available.append("springer")
        if self._semantic:
            available.append("semantic")
        if self._crossref:
            available.append("crossref")
        if self._biorxiv:
            available.append("biorxiv")
        if self._sciencedirect:
            available.append("scopus")
        logger.info("ResearchClient ready with sources: %s", ", ".join(available))

    def search(
        self,
        query: str,
        max_results: int = 20,
        sources: list[str] | None = None,
    ) -> list[Paper]:
        """Search across all configured APIs, deduplicate by DOI.

        Args:
            query: Search query string.
            max_results: Maximum results per source.
            sources: List of sources to query. Defaults to all available.
                Options: "pubmed", "springer", "semantic".

        Returns:
            Deduplicated list of Paper objects sorted by citation count.
        """
        from vaultlab.research.search import unified_search

        return unified_search(
            query,
            max_results=max_results,
            sources=sources,
            ncbi_client=self._ncbi,
            springer_client=self._springer,
            semantic_client=self._semantic,
            crossref_client=self._crossref,
            biorxiv_client=self._biorxiv,
            sciencedirect_client=self._sciencedirect,
        )

    def search_with_trace(
        self,
        query: str,
        max_results: int = 50,
        sources: list[str] | None = None,
        queries: list[str] | None = None,
    ):
        """Like :meth:`search` but also returns a per-source trace.

        Args:
            query: Single query (used when ``queries`` is None).
            max_results: Per-source cap on raw hits.
            sources: Optional list of source names.
            queries: Optional list of query variants to fan out across.
                When given, each variant runs against every source and
                results are deduped across the whole batch. See
                :func:`vaultlab.research.query_expansion.expand_query`.

        Returns:
            ``(papers, trace)`` where ``trace`` is a
            :class:`vaultlab.research.search.SearchTrace` with per-source
            hits / errors / wall-time. The orchestrator uses this to emit
            a ``Sources/Notes/<topic>.search-trace.json`` sidecar so the
            decisions log can show real per-API hit counts (not just the
            seed-set size).
        """
        from vaultlab.research.search import unified_search

        return unified_search(
            query,
            max_results=max_results,
            sources=sources,
            ncbi_client=self._ncbi,
            springer_client=self._springer,
            semantic_client=self._semantic,
            crossref_client=self._crossref,
            biorxiv_client=self._biorxiv,
            sciencedirect_client=self._sciencedirect,
            return_trace=True,
            queries=queries,
        )

    def get_paper(self, doi_or_pmid: str) -> Paper | None:
        """Get full metadata from the best available source.

        Tries PubMed first (if input looks like a PMID), then Semantic Scholar
        (by DOI), then PubMed search by DOI.

        Args:
            doi_or_pmid: A DOI (e.g., "10.1038/...") or PMID (e.g., "39358522").

        Returns:
            Paper object or None if not found.
        """
        # Detect if it's a PMID (all digits)
        if doi_or_pmid.strip().isdigit():
            if self._ncbi:
                paper = self._ncbi.get_paper(doi_or_pmid.strip())
                if paper:
                    return paper

        # Try Semantic Scholar by DOI
        if self._semantic and "/" in doi_or_pmid:
            paper = self._semantic.get_paper(f"DOI:{doi_or_pmid}")
            if paper:
                # Enrich with PubMed data if available
                if self._ncbi and paper.pmid:
                    pubmed_paper = self._ncbi.get_paper(paper.pmid)
                    if pubmed_paper:
                        pubmed_paper.merge(paper)
                        return pubmed_paper
                return paper

        # Try PubMed search by DOI
        if self._ncbi and "/" in doi_or_pmid:
            results = self._ncbi.search(f"{doi_or_pmid}[doi]", max_results=1)
            if results:
                return results[0]

        return None

    def get_citations(self, doi: str, depth: int = 1) -> list[Paper]:
        """Find papers that cite this one (via Semantic Scholar).

        Args:
            doi: DOI of the paper.
            depth: Citation depth (1 = direct citations only).

        Returns:
            List of citing Paper objects.
        """
        if not self._semantic:
            logger.warning("Semantic Scholar not configured; cannot get citations.")
            return []

        paper_id = f"DOI:{doi}" if "/" in doi else doi
        citations = self._semantic.get_citations(paper_id)

        if depth > 1 and citations:
            # Get second-level citations (citations of citations)
            second_level = []
            for p in citations[:10]:  # limit to avoid API overload
                if p.doi:
                    sub_cites = self._semantic.get_citations(f"DOI:{p.doi}", limit=20)
                    second_level.extend(sub_cites)
            citations.extend(second_level)

        return citations

    def get_references(self, doi: str) -> list[Paper]:
        """Find papers that this paper cites.

        Args:
            doi: DOI of the paper.

        Returns:
            List of referenced Paper objects.
        """
        if not self._semantic:
            logger.warning("Semantic Scholar not configured; cannot get references.")
            return []

        paper_id = f"DOI:{doi}" if "/" in doi else doi
        return self._semantic.get_references(paper_id)

    def verify_exists(self, doi_or_pmid: str) -> VerificationResult:
        """Check if a paper exists across CrossRef, PubMed, Semantic Scholar.

        Args:
            doi_or_pmid: A DOI or PubMed ID.

        Returns:
            VerificationResult with exists, paper, sources_checked, confidence.
        """
        from vaultlab.research.verification import VerificationResult

        sources_checked = []
        is_pmid = doi_or_pmid.strip().isdigit()
        is_doi = "/" in doi_or_pmid

        # Try CrossRef first for DOIs (most authoritative)
        if is_doi and self._crossref:
            sources_checked.append("crossref")
            paper = self._crossref.resolve_doi(doi_or_pmid)
            if paper:
                paper = self._enrich_abstract(paper)
                return VerificationResult(
                    exists=True,
                    paper=paper,
                    sources_checked=sources_checked,
                    confidence=1.0,
                )

        # Try PubMed for PMIDs or as fallback for DOIs
        if self._ncbi:
            sources_checked.append("pubmed")
            if is_pmid:
                paper = self._ncbi.get_paper(doi_or_pmid.strip())
            else:
                results = self._ncbi.search(f"{doi_or_pmid}[doi]", max_results=1)
                paper = results[0] if results else None
            if paper:
                paper = self._enrich_abstract(paper)
                return VerificationResult(
                    exists=True,
                    paper=paper,
                    sources_checked=sources_checked,
                    confidence=0.95,
                )

        # Try Semantic Scholar
        if self._semantic and is_doi:
            sources_checked.append("semantic")
            paper = self._semantic.get_paper(f"DOI:{doi_or_pmid}")
            if paper:
                paper = self._enrich_abstract(paper)
                return VerificationResult(
                    exists=True,
                    paper=paper,
                    sources_checked=sources_checked,
                    confidence=0.8,
                )

        return VerificationResult(
            exists=False,
            paper=None,
            sources_checked=sources_checked,
            confidence=0.0,
        )

    def _enrich_abstract(self, paper: Paper) -> Paper:
        """Try to fill in a missing abstract from PubMed or Semantic Scholar.

        CrossRef records often lack abstracts. This method attempts to fetch
        the abstract from PubMed (best for biomedical papers) or Semantic
        Scholar as a fallback.

        Args:
            paper: Paper object that may be missing an abstract.

        Returns:
            The same Paper object, potentially with abstract filled in.
        """
        if paper.abstract:
            return paper

        # Try PubMed (most complete abstracts for bio papers)
        if self._ncbi and paper.doi:
            try:
                results = self._ncbi.search(f"{paper.doi}[doi]", max_results=1)
                if results and results[0].abstract:
                    paper.abstract = results[0].abstract
                    return paper
            except Exception:
                pass

        # Try Semantic Scholar as fallback
        if self._semantic and paper.doi:
            try:
                s2_paper = self._semantic.get_paper(f"DOI:{paper.doi}")
                if s2_paper and s2_paper.abstract:
                    paper.abstract = s2_paper.abstract
                    return paper
            except Exception:
                pass

        return paper

    def get_recommendations(self, paper_ids: list[str]) -> list[Paper]:
        """Get recommended papers based on seed papers.

        Args:
            paper_ids: List of DOIs or Semantic Scholar IDs.

        Returns:
            List of recommended Paper objects.
        """
        if not self._semantic:
            logger.warning("Semantic Scholar not configured; cannot get recommendations.")
            return []

        # Prefix DOIs for the API
        formatted = []
        for pid in paper_ids:
            if "/" in pid:
                formatted.append(f"DOI:{pid}")
            else:
                formatted.append(pid)

        return self._semantic.get_recommendations(formatted)

    def download_pdf(self, paper: Paper, output_dir: str) -> str:
        """Download PDF if available. Returns path or empty string.

        Args:
            paper: Paper object with metadata.
            output_dir: Directory to save the PDF.

        Returns:
            Path to the downloaded PDF, or empty string.
        """
        from vaultlab.research.download import download_pdf as _dl

        return _dl(paper, output_dir)

    def save_to_kb(self, paper: Paper, kb_dir: str) -> str:
        """Save paper metadata as Obsidian-compatible markdown.

        Args:
            paper: Paper object with metadata.
            kb_dir: Path to the knowledge base root directory.

        Returns:
            Path to the saved markdown file.
        """
        from vaultlab.research.download import save_to_kb as _save

        return _save(paper, kb_dir)

    def match_claim(
        self,
        claim_text: str,
        paper: Paper,
        full_text: str | None = None,
    ) -> ClaimMatch:
        """Use Claude to assess whether a paper supports a claim.

        Args:
            claim_text: The claim to verify.
            paper: Paper object with at least an abstract.
            full_text: Optional full paper text for deeper matching.

        Returns:
            ClaimMatch with evidence chunk and reasoning.
        """
        from vaultlab.research.verification import match_claim_with_llm

        text = full_text or paper.abstract
        if not text:
            from vaultlab.research.verification import ClaimMatch

            return ClaimMatch(
                supported="unrelated",
                evidence_chunk="",
                chunk_location="",
                confidence=0.0,
                reasoning="No text available (no abstract or full text).",
            )

        text_source = "full_text" if full_text else "abstract"
        return match_claim_with_llm(claim_text, text, text_source)

    def fetch_evidence(
        self,
        claim_text: str,
        doi_or_pmid: str,
        kb_dir: str | None = None,
    ) -> EvidenceRecord:
        """Full verification pipeline: verify paper exists, match claim, return evidence.

        Args:
            claim_text: The claim to verify.
            doi_or_pmid: DOI or PMID of the cited paper.
            kb_dir: Optional KB directory to check for full text.

        Returns:
            EvidenceRecord with verification result and claim match.
        """
        from datetime import datetime

        from vaultlab.research.verification import EvidenceRecord

        # Step 1: Verify paper exists
        verification = self.verify_exists(doi_or_pmid)

        claim_match = None
        if verification.exists and verification.paper:
            # Step 2: Check KB for full text
            full_text = None
            if kb_dir:
                full_text = self.find_full_text_in_kb(verification.paper, kb_dir)

            # Step 3: Match claim against text
            claim_match = self.match_claim(claim_text, verification.paper, full_text)

        return EvidenceRecord(
            citation_text=claim_text,
            verification=verification,
            claim_match=claim_match,
            timestamp=datetime.now().isoformat(),
        )

    def find_full_text_in_kb(self, paper: Paper, kb_dir: str) -> str | None:
        """Look for paper's full text in a KB's Sources/Papers/ or Sources/Articles/."""
        import os
        import re

        for subdir in ("Papers", "Articles"):
            source_dir = os.path.join(kb_dir, "Sources", subdir)
            if not os.path.isdir(source_dir):
                continue
            for filename in os.listdir(source_dir):
                if not filename.endswith(".md"):
                    continue
                filepath = os.path.join(source_dir, filename)
                try:
                    with open(filepath, encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    # Check if this file is about the same paper (match DOI or title)
                    if paper.doi and paper.doi in content:
                        # Strip frontmatter and return body
                        body = re.sub(r"^---.*?---\s*", "", content, flags=re.DOTALL)
                        return body
                    if paper.title and paper.title.lower() in content.lower():
                        body = re.sub(r"^---.*?---\s*", "", content, flags=re.DOTALL)
                        return body
                except Exception:
                    continue
        return None


# Module-level convenience functions


def search_papers(
    query: str,
    max_results: int = 20,
    sources: list[str] | None = None,
    download_dir: str | None = None,
    config_path: str | None = None,
) -> list[Paper]:
    """Search for papers across all configured APIs.

    Convenience function that creates a ResearchClient and searches.

    Args:
        query: Search query string.
        max_results: Maximum results per source.
        sources: List of sources ("pubmed", "springer", "semantic").
        download_dir: If provided, download PDFs to this directory.
        config_path: Override path to API keys config file.

    Returns:
        Deduplicated list of Paper objects.
    """
    client = ResearchClient(config_path=config_path)
    results = client.search(query, max_results=max_results, sources=sources)

    if download_dir:
        for paper in results:
            client.download_pdf(paper, download_dir)

    return results


def get_paper(
    doi_or_pmid: str,
    config_path: str | None = None,
) -> Paper | None:
    """Get full metadata for a paper by DOI or PMID.

    Args:
        doi_or_pmid: DOI or PubMed ID.
        config_path: Override path to API keys config file.

    Returns:
        Paper object or None.
    """
    client = ResearchClient(config_path=config_path)
    return client.get_paper(doi_or_pmid)


def download_pdf(
    paper: Paper,
    output_dir: str,
) -> str:
    """Download PDF for a paper.

    Args:
        paper: Paper with metadata.
        output_dir: Directory to save the PDF.

    Returns:
        Path to the downloaded PDF, or empty string.
    """
    from vaultlab.research.download import download_pdf as _dl

    return _dl(paper, output_dir)
