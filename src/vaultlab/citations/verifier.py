"""Citation verification orchestrator --- coordinates API checks and claim matching."""

from __future__ import annotations

import logging
import re
from datetime import datetime

from vaultlab.citations.models import Citation, RiskLevel, VerificationStatus

logger = logging.getLogger(__name__)


def verify_citation(
    citation: Citation,
    research_client,
    kb_dir: str | None = None,
    evidence_index=None,
) -> Citation:
    """Verify a single citation against APIs and optionally match its claim.

    Args:
        citation: The citation to verify.
        research_client: A bobby_research.ResearchClient instance.
        kb_dir: Optional KB directory to check for full text and evidence cache.
        evidence_index: Optional EvidenceIndex for cache lookups.

    Returns:
        The citation with updated status, evidence, and hallucination flags.
    """
    # Step 0: Check evidence cache
    doi_or_pmid = citation.doi or citation.pmid
    if evidence_index and doi_or_pmid:
        cached = evidence_index.lookup(doi_or_pmid, citation.claim)
        if cached:
            try:
                citation.status = VerificationStatus(cached["status"])
                logger.info("Cache hit for %s: %s", doi_or_pmid, cached["status"])
                return citation
            except (ValueError, KeyError):
                logger.warning("Invalid cached status for %s, treating as cache miss", doi_or_pmid)

    # Step 1: Find the paper
    if doi_or_pmid:
        verification = research_client.verify_exists(doi_or_pmid)
    else:
        # Search by author + year + keywords
        query = f"{citation.authors} {citation.year}"
        if citation.claim:
            # Add first few meaningful words from claim
            words = [w for w in citation.claim.split()[:5] if len(w) > 3]
            query += " " + " ".join(words)
        results = research_client.search(query, max_results=3)
        if results:
            from vaultlab.research.verification import VerificationResult

            paper = _best_match(results, citation)
            verification = VerificationResult(
                exists=True,
                paper=paper,
                sources_checked=["search"],
                confidence=0.6,
            )
        else:
            from vaultlab.research.verification import VerificationResult

            verification = VerificationResult(
                exists=False,
                paper=None,
                sources_checked=["search"],
                confidence=0.0,
            )

    # Step 2: Check hallucination indicators
    citation.hallucination_flags = check_hallucination_risks(citation)

    if not verification.exists:
        citation.status = VerificationStatus.SUSPECT
        citation.hallucination_flags.append("PAPER_NOT_FOUND")
        citation.risk = _assign_risk(citation)
        return citation

    # Paper exists -- update citation metadata
    paper = verification.paper
    if paper:
        if paper.doi and not citation.doi:
            citation.doi = paper.doi
        if paper.pmid and not citation.pmid:
            citation.pmid = paper.pmid
        if paper.title:
            citation.title = paper.title
        if paper.journal:
            citation.journal = paper.journal

    # Step 3: Match claim if we have text
    if paper and citation.claim and (paper.abstract or kb_dir):
        full_text = None
        if kb_dir:
            full_text = research_client.find_full_text_in_kb(paper, kb_dir)

        claim_match = research_client.match_claim(citation.claim, paper, full_text)

        from vaultlab.research.verification import EvidenceRecord

        citation.evidence = EvidenceRecord(
            citation_text=citation.raw_text,
            verification=verification,
            claim_match=claim_match,
            timestamp=datetime.now().isoformat(),
        )

        # Set status based on match result
        if claim_match.supported == "supported":
            if full_text:
                citation.status = VerificationStatus.VERIFIED_FULLTEXT
            else:
                citation.status = VerificationStatus.VERIFIED_ABSTRACT
        elif claim_match.supported == "unsupported":
            citation.status = VerificationStatus.CONTRADICTED
        elif claim_match.supported == "partial":
            citation.status = VerificationStatus.VERIFIED_ABSTRACT
        else:
            citation.status = VerificationStatus.API_CONFIRMED

        # Cache the result
        if evidence_index and (citation.doi or citation.pmid):
            evidence_index.store(
                doi=citation.doi or citation.pmid,
                claim=citation.claim,
                status=citation.status.value,
                evidence_chunk=claim_match.evidence_chunk,
                chunk_location=claim_match.chunk_location,
                confidence=claim_match.confidence,
                source_file=citation.source_file,
            )
    else:
        citation.status = VerificationStatus.API_CONFIRMED

    # Step 4: Assign risk level
    citation.risk = _assign_risk(citation)

    # Step 5: Append verified claims to KB article if applicable
    if kb_dir and citation.evidence and citation.evidence.claim_match:
        _append_verified_claim_to_kb(citation, kb_dir)

    return citation


def check_hallucination_risks(citation: Citation) -> list[str]:
    """Check for signs of AI hallucination in a citation.

    Args:
        citation: The citation to check.

    Returns:
        List of flag strings describing risks found.
    """
    flags = []
    current_year = datetime.now().year

    # Future date
    if citation.year > current_year:
        flags.append(f"FUTURE_DATE: {citation.year} is in the future")

    # Current year (hard to verify)
    if citation.year == current_year:
        flags.append(f"CURRENT_YEAR: {citation.year} paper --- verify it exists")

    # Specific quantitative claim with no DOI
    if citation.claim and not citation.doi and not citation.pmid:
        if re.search(r"\d+\.?\d*%|\d+\.\d+|p\s*[<>=]|n\s*=", citation.claim):
            flags.append("UNVERIFIED_QUANTITATIVE: numerical claim with no DOI/PMID")

    return flags


def _assign_risk(citation: Citation) -> RiskLevel:
    """Assign a risk level based on status and hallucination flags."""
    # HIGH: hallucination flags present, or status is SUSPECT/CONTRADICTED
    if citation.hallucination_flags:
        return RiskLevel.HIGH
    if citation.status in (VerificationStatus.SUSPECT, VerificationStatus.CONTRADICTED):
        return RiskLevel.HIGH

    # LOW: API confirmed with no claim to check
    if citation.status == VerificationStatus.API_CONFIRMED and not citation.claim:
        return RiskLevel.LOW

    # LOW: fully verified
    if citation.status in (
        VerificationStatus.VERIFIED_FULLTEXT,
        VerificationStatus.VERIFIED_ABSTRACT,
    ):
        return RiskLevel.LOW

    return RiskLevel.MEDIUM


def _append_verified_claim_to_kb(citation: Citation, kb_dir: str) -> None:
    """Append verified claim to the paper's article in Sources/Articles/."""
    import os

    if not citation.doi and not citation.title:
        return

    articles_dir = os.path.join(kb_dir, "Sources", "Articles")
    if not os.path.isdir(articles_dir):
        return

    # Find the article file matching this citation's paper
    target_file = None
    for filename in os.listdir(articles_dir):
        if not filename.endswith(".md"):
            continue
        filepath = os.path.join(articles_dir, filename)
        try:
            with open(filepath, encoding="utf-8", errors="ignore") as f:
                content = f.read()
            if citation.doi and citation.doi in content:
                target_file = filepath
                break
            if citation.title and citation.title.lower() in content.lower():
                target_file = filepath
                break
        except Exception:
            continue

    if not target_file:
        return

    # Build the claim entry
    cm = citation.evidence.claim_match
    claim_entry = (
        f"- **Claim:** {citation.claim}\n"
        f"  - **Supported:** {cm.supported} (confidence: {cm.confidence:.2f})\n"
        f"  - **Evidence:** {cm.evidence_chunk}\n"
        f"  - **Source:** {citation.source_file}:{citation.line_number}\n"
    )

    try:
        with open(target_file, encoding="utf-8") as f:
            content = f.read()

        if "## Verified Claims" in content:
            # Append to existing section (before the next ## heading or at end)
            parts = content.split("## Verified Claims", 1)
            after = parts[1]
            # Find next heading
            next_heading = re.search(r"\n## ", after)
            if next_heading:
                insert_pos = next_heading.start()
                after = after[:insert_pos] + "\n" + claim_entry + after[insert_pos:]
            else:
                after = after.rstrip() + "\n" + claim_entry + "\n"
            content = parts[0] + "## Verified Claims" + after
        else:
            # Add new section at end
            content = content.rstrip() + "\n\n## Verified Claims\n\n" + claim_entry + "\n"

        with open(target_file, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        logger.warning("Failed to append verified claim to KB: %s", e)


def _best_match(papers, citation: Citation):
    """Pick the best matching paper from search results.

    When the citation has claim context, scores each candidate by keyword
    overlap between the claim text and the paper's title + abstract.  A year
    match bonus is added so that papers from the cited year are strongly
    preferred.  Falls back to year-only matching when no claim is available.
    """
    if not citation.claim:
        # No context -- prefer year match
        for p in papers:
            if p.year == citation.year:
                return p
        return papers[0]

    # Score by keyword overlap between claim and title+abstract
    claim_words = set(citation.claim.lower().split())
    best_score = -1
    best_paper = papers[0]
    for p in papers:
        text = f"{p.title} {p.abstract}".lower()
        overlap = len(claim_words & set(text.split()))
        year_bonus = 10 if p.year == citation.year else 0
        score = overlap + year_bonus
        if score > best_score:
            best_score = score
            best_paper = p
    return best_paper
