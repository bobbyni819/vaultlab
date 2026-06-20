"""Tests for vaultlab.manuscript.citation_gate."""

from __future__ import annotations

import pytest

from vaultlab.citations.models import Citation, VerificationStatus
from vaultlab.manuscript.citation_gate import run_citation_gate
from vaultlab.manuscript.claim_ledger import CitationTier, ClaimLedger


def _citation(
    key: str,
    status: VerificationStatus,
    *,
    doi: str = "",
    pmid: str = "",
    claim: str = "A manuscript claim.",
) -> Citation:
    return Citation(
        raw_text=key,
        authors=key,
        year=2024,
        claim=claim,
        source_file="draft.md",
        line_number=7,
        doi=doi,
        pmid=pmid,
        status=status,
    )


def test_mixed_citations_block_below_tier3_and_emit_promotions() -> None:
    report = run_citation_gate(
        citations=[
            _citation("Fulltext", VerificationStatus.VERIFIED_FULLTEXT, doi="10.1/full"),
            _citation("Abstract", VerificationStatus.VERIFIED_ABSTRACT, doi="10.1/abstract"),
            _citation("Api", VerificationStatus.API_CONFIRMED, doi="10.1/api"),
            _citation("Unverified DOI", VerificationStatus.UNVERIFIED, doi="10.1/unverified"),
            _citation("Contradicted", VerificationStatus.CONTRADICTED, doi="10.1/bad"),
        ]
    )

    assert not report.ok
    assert [status.citation_key for status in report.blocked] == [
        "10.1/bad",
        "10.1/unverified",
        "10.1/api",
        "10.1/abstract",
    ]
    assert {status.citation_key for status in report.statuses if not status.blocked} == {
        "10.1/full"
    }
    actions = {action.citation_key: action.action for action in report.promotion_queue}
    assert "RESOLVE" in actions["10.1/bad"]
    assert "verify DOI/PMID exists" in actions["10.1/unverified"]
    assert "fetch the abstract" in actions["10.1/api"]
    assert "fetch full text" in actions["10.1/abstract"]
    assert "verbatim quote" in actions["10.1/abstract"]


def test_unverified_without_identifier_cannot_be_tiered_yet() -> None:
    report = run_citation_gate(
        citations=[_citation("No Identifier", VerificationStatus.UNVERIFIED)]
    )

    assert not report.ok
    assert report.blocked[0].tier is None
    assert "find the DOI/PMID" in report.promotion_queue[0].action


def test_manuscript_markdown_uses_citation_extractor() -> None:
    report = run_citation_gate(
        manuscript_md="This claim is supported by DOI: 10.1234/example and needs checking."
    )

    assert not report.ok
    assert [status.citation_key for status in report.statuses] == ["10.1234/example"]
    assert report.statuses[0].status is VerificationStatus.UNVERIFIED
    assert "verify DOI/PMID exists" in report.promotion_queue[0].action


def test_ledger_links_use_existing_tiers() -> None:
    ledger = ClaimLedger()
    ledger.add_claim("c1", "Only abstract verified.")
    ledger.link_citation(
        "c1",
        "smith2024",
        CitationTier.TIER_2,
        status=VerificationStatus.VERIFIED_ABSTRACT,
    )
    ledger.add_claim("c2", "Full text verified.")
    ledger.link_citation(
        "c2",
        "lee2025",
        CitationTier.TIER_3,
        status=VerificationStatus.VERIFIED_FULLTEXT,
    )

    report = run_citation_gate(ledger=ledger)

    assert not report.ok
    assert [status.citation_key for status in report.blocked] == ["smith2024"]
    assert report.blocked[0].claim_text == "Only abstract verified."
    assert report.promotion_queue[0].current_tier is CitationTier.TIER_2


def test_to_dict_and_markdown_render_gate_report() -> None:
    report = run_citation_gate(
        citations=[_citation("Api", VerificationStatus.API_CONFIRMED, doi="10.1/api")]
    )

    payload = report.to_dict()
    markdown = report.to_markdown()

    assert payload["ok"] is False
    assert payload["blocked"][0]["tier"] == "tier_1"
    assert "| citation | tier | status | blocked |" in markdown
    assert "## Promotion queue" in markdown
    assert "10.1/api" in markdown


def test_requires_at_least_one_input_source() -> None:
    with pytest.raises(ValueError, match="manuscript_md, citations, or ledger"):
        run_citation_gate()


def test_citation_tier_rank_is_ordered() -> None:
    assert CitationTier.TIER_1.rank < CitationTier.TIER_2.rank < CitationTier.TIER_3.rank
