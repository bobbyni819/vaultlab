"""Behavioural tests for vaultlab.citations.verifier.verify_citation.

Pins the trust-fix decision (2026-06-10): a cited paper that *exists* but whose claim was
never checked against text must be scored UNVERIFIED (not the optimistic API_CONFIRMED),
and such a citation is never low-risk. Verified and existence-only paths are unchanged.
"""

from __future__ import annotations

from vaultlab.citations.models import Citation, RiskLevel, VerificationStatus
from vaultlab.citations.verifier import verify_citation
from vaultlab.research.verification import ClaimMatch, VerificationResult


class _FakePaper:
    def __init__(self, *, doi="", pmid="", title="", journal="", abstract=""):
        self.doi = doi
        self.pmid = pmid
        self.title = title
        self.journal = journal
        self.abstract = abstract


class _FakeClient:
    """A research client stub: controls existence, available text, and the claim match."""

    def __init__(self, *, exists=True, paper=None, full_text=None, match=None):
        self._exists = exists
        self._paper = paper
        self._full_text = full_text
        self._match = match

    def verify_exists(self, _doi_or_pmid):
        return VerificationResult(
            exists=self._exists,
            paper=self._paper if self._exists else None,
            sources_checked=["crossref"],
            confidence=1.0 if self._exists else 0.0,
        )

    def search(self, _query, max_results=3):
        return []

    def find_full_text_in_kb(self, _paper, _kb_dir):
        return self._full_text

    def match_claim(self, _claim, _paper, _full_text):
        return self._match


def _citation(claim="cells doubled in number"):
    return Citation(
        raw_text="(Smith 2020)",
        authors="Smith",
        year=2020,
        claim=claim,
        source_file="draft.md",
        line_number=1,
        doi="10.1/exists",
    )


def test_existing_paper_with_unchecked_claim_is_unverified():
    # Paper exists but has no abstract and there's no KB full text -> the claim cannot be
    # checked. Must be UNVERIFIED + non-low risk, not API_CONFIRMED.
    client = _FakeClient(exists=True, paper=_FakePaper(doi="10.1/exists"), full_text=None)
    out = verify_citation(_citation(), client, kb_dir=None)
    assert out.status == VerificationStatus.UNVERIFIED
    assert out.risk == RiskLevel.MEDIUM


def test_existing_paper_no_claim_is_api_confirmed_low():
    # No claim attached -> confirming existence is all that was asked; that stays LOW.
    client = _FakeClient(exists=True, paper=_FakePaper(doi="10.1/exists"))
    out = verify_citation(_citation(claim=""), client, kb_dir=None)
    assert out.status == VerificationStatus.API_CONFIRMED
    assert out.risk == RiskLevel.LOW


def test_inconclusive_match_is_unverified():
    # We had abstract text and ran the match, but it was 'unrelated' -> not a confirmation.
    paper = _FakePaper(doi="10.1/exists", abstract="Some abstract text.")
    match = ClaimMatch(supported="unrelated", evidence_chunk="", chunk_location="abstract", confidence=0.1, reasoning="no overlap")
    client = _FakeClient(exists=True, paper=paper, match=match)
    out = verify_citation(_citation(), client, kb_dir=None)
    assert out.status == VerificationStatus.UNVERIFIED
    assert out.risk == RiskLevel.MEDIUM


def test_supported_with_fulltext_is_verified_low():
    paper = _FakePaper(doi="10.1/exists", abstract="abstract")
    match = ClaimMatch(supported="supported", evidence_chunk="cells doubled", chunk_location="results p3", confidence=0.9, reasoning="match")
    client = _FakeClient(exists=True, paper=paper, full_text="full text body", match=match)
    out = verify_citation(_citation(), client, kb_dir="/kb")
    assert out.status == VerificationStatus.VERIFIED_FULLTEXT
    assert out.risk == RiskLevel.LOW


def test_missing_paper_is_suspect_high():
    client = _FakeClient(exists=False)
    out = verify_citation(_citation(), client, kb_dir=None)
    assert out.status == VerificationStatus.SUSPECT
    assert out.risk == RiskLevel.HIGH
    assert "PAPER_NOT_FOUND" in out.hallucination_flags
