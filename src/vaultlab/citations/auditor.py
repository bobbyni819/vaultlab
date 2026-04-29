"""Batch citation audit pipeline."""

from __future__ import annotations

import logging
import os
from collections import Counter
from datetime import datetime

from vaultlab.citations.extractor import extract_citations
from vaultlab.citations.models import AuditReport, Citation, VerificationStatus
from vaultlab.citations.verifier import verify_citation

logger = logging.getLogger(__name__)


def _citation_key(citation: Citation) -> str:
    """Return a deduplication key for a citation.

    Uses DOI if available, otherwise (authors_lower, year).
    """
    if citation.doi:
        return f"doi:{citation.doi.lower()}"
    if citation.pmid:
        return f"pmid:{citation.pmid}"
    return f"author:{citation.authors.lower()}:{citation.year}"


def audit_file(
    filepath: str,
    research_client=None,
    kb_dir: str | None = None,
    evidence_index=None,
) -> AuditReport:
    """Audit a single markdown file for citation verification.

    Args:
        filepath: Path to the markdown file.
        research_client: bobby_research.ResearchClient instance.
        kb_dir: Optional KB directory for full text lookups.
        evidence_index: Optional EvidenceIndex for caching.

    Returns:
        AuditReport with all citations and their verification status.
    """
    citations = extract_citations(filepath)
    logger.info("Extracted %d citations from %s", len(citations), filepath)

    if research_client:
        seen: set[str] = set()
        for i, citation in enumerate(citations):
            key = _citation_key(citation)
            if key in seen:
                # Copy status from the first occurrence
                for prev in citations[:i]:
                    if _citation_key(prev) == key:
                        citation.status = prev.status
                        citation.risk = prev.risk
                        citation.evidence = prev.evidence
                        citation.hallucination_flags = list(prev.hallucination_flags)
                        if prev.doi and not citation.doi:
                            citation.doi = prev.doi
                        if prev.title and not citation.title:
                            citation.title = prev.title
                        break
                logger.info(
                    "Skipping [%d/%d]: %s (already verified)",
                    i + 1,
                    len(citations),
                    citation.raw_text,
                )
                continue
            seen.add(key)
            logger.info("Verifying [%d/%d]: %s", i + 1, len(citations), citation.raw_text)
            verify_citation(citation, research_client, kb_dir, evidence_index)

    return _build_report(citations, [filepath])


def audit_directory(
    dirpath: str,
    glob_pattern: str = "**/*.md",
    research_client=None,
    kb_dir: str | None = None,
    evidence_index=None,
) -> AuditReport:
    """Audit all markdown files in a directory.

    Args:
        dirpath: Path to the directory.
        glob_pattern: Glob pattern for finding files.
        research_client: bobby_research.ResearchClient instance.
        kb_dir: Optional KB directory for full text lookups.
        evidence_index: Optional EvidenceIndex for caching.

    Returns:
        AuditReport covering all files.
    """
    import pathlib

    path = pathlib.Path(dirpath)
    files = sorted(str(f) for f in path.glob(glob_pattern) if f.is_file())

    all_citations = []
    for filepath in files:
        citations = extract_citations(filepath)
        all_citations.extend(citations)
        logger.info("Extracted %d citations from %s", len(citations), filepath)

    logger.info("Total: %d citations from %d files", len(all_citations), len(files))

    if research_client:
        seen: set[str] = set()
        for i, citation in enumerate(all_citations):
            key = _citation_key(citation)
            if key in seen:
                # Copy status from the first occurrence
                for prev in all_citations[:i]:
                    if _citation_key(prev) == key:
                        citation.status = prev.status
                        citation.risk = prev.risk
                        citation.evidence = prev.evidence
                        citation.hallucination_flags = list(prev.hallucination_flags)
                        if prev.doi and not citation.doi:
                            citation.doi = prev.doi
                        if prev.title and not citation.title:
                            citation.title = prev.title
                        break
                logger.info(
                    "Skipping [%d/%d]: %s (already verified)",
                    i + 1,
                    len(all_citations),
                    citation.raw_text,
                )
                continue
            seen.add(key)
            logger.info("Verifying [%d/%d]: %s", i + 1, len(all_citations), citation.raw_text)
            verify_citation(citation, research_client, kb_dir, evidence_index)

    return _build_report(all_citations, files)


def _build_report(citations: list[Citation], source_files: list[str]) -> AuditReport:
    """Build an AuditReport from a list of verified citations."""
    status_counts = Counter(c.status.value for c in citations)

    high_risk_unverified = sum(
        1
        for c in citations
        if c.status in (VerificationStatus.UNVERIFIED, VerificationStatus.SUSPECT)
        and c.risk.value == "high"
    )

    all_flags = []
    action_items = []
    for c in citations:
        all_flags.extend(c.hallucination_flags)
        if c.status == VerificationStatus.SUSPECT:
            action_items.append(
                f"Verify {c.raw_text} (line {c.line_number} in {os.path.basename(c.source_file)}) "
                f"-- {', '.join(c.hallucination_flags) if c.hallucination_flags else 'paper not found'}"
            )
        elif c.status == VerificationStatus.CONTRADICTED:
            action_items.append(
                f"CHECK {c.raw_text} (line {c.line_number}) -- claim may not be supported by paper"
            )

    return AuditReport(
        total=len(citations),
        by_status=dict(status_counts),
        high_risk_unverified=high_risk_unverified,
        citations=citations,
        hallucination_flags=list(set(all_flags)),
        action_items=action_items,
        source_files=source_files,
        audit_date=datetime.now().strftime("%Y-%m-%d"),
    )
