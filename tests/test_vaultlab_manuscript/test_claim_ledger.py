"""Tests for vaultlab.manuscript.claim_ledger."""

from __future__ import annotations

import json
from pathlib import Path

from vaultlab.citations.models import RiskLevel, VerificationStatus
from vaultlab.manuscript.claim_ledger import (
    CitationTier,
    ClaimLedger,
    ClaimReadiness,
)


def test_citation_tier_maps_from_verification_status():
    assert CitationTier.from_verification_status(VerificationStatus.VERIFIED_FULLTEXT) is (
        CitationTier.TIER_3
    )
    assert CitationTier.from_verification_status(VerificationStatus.VERIFIED_ABSTRACT) is (
        CitationTier.TIER_2
    )
    assert CitationTier.from_verification_status(VerificationStatus.API_CONFIRMED) is (
        CitationTier.TIER_1
    )
    assert CitationTier.from_verification_status(VerificationStatus.UNVERIFIED) is None
    assert CitationTier.from_verification_status(VerificationStatus.SUSPECT) is None
    assert CitationTier.from_verification_status(VerificationStatus.CONTRADICTED) is None


def test_from_markdown_parses_claims_and_links():
    text = """
    [CLAIM:c1 kind=quantitative section=Results] Metabolism increases with hypoxia.
    [FIG:figR5 panel=c] [STAT:rho=0.31 src=results/fig5.csv method=spearman]
    [CITE:smith2020 tier=3 status=verified_fulltext]

    [CLAIM:c2 kind=novel] The organoid atlas motivates a new model.
    [STAT:n=42 src=results/atlas.csv] [FIG:figS2]
    """
    ledger = ClaimLedger.from_markdown(text)

    assert [claim.claim_id for claim in ledger.claims] == ["c1", "c2"]
    assert ledger.claims[0].text == "Metabolism increases with hypoxia."
    assert ledger.claims[0].section == "Results"
    assert ledger.claims[0].kind == "quantitative"
    assert ledger.figure_links[0].figure_id == "figR5"
    assert ledger.figure_links[0].panel == "c"
    assert ledger.numeric_links[0].value == "rho=0.31"
    assert ledger.numeric_links[0].source_file == "results/fig5.csv"
    assert ledger.numeric_links[0].stat_method == "spearman"
    assert ledger.citation_links[0].citation_key == "smith2020"
    assert ledger.citation_links[0].tier is CitationTier.TIER_3
    assert ledger.citation_links[0].status is VerificationStatus.VERIFIED_FULLTEXT
    assert ledger.parse_warnings == []


def test_audit_flags_missing_figure_missing_citation_under_tiered_and_missing_source(
    tmp_path: Path,
):
    existing_source = tmp_path / "results" / "fig5.csv"
    existing_source.parent.mkdir()
    existing_source.write_text("x,y\n1,2\n", encoding="utf-8")

    ledger = ClaimLedger()
    ledger.add_claim("c1", "Supported but under-tiered.", section="Results")
    ledger.link_figure("c1", "figR5", panel="c")
    ledger.link_numeric("c1", "rho=0.31", "results/fig5.csv", stat_method="spearman")
    ledger.link_citation("c1", "smith2020", CitationTier.TIER_1)

    ledger.add_claim("c2", "No figure or citation yet.", section="Results")
    ledger.link_numeric("c2", "P=0.02", "results/missing.csv")

    audit = ledger.audit(base_dir=tmp_path)

    assert not audit.ok
    messages = [problem.message for problem in audit.problems]
    assert any("needs Tier-3" in message for message in messages)
    assert any("missing figure link" in message for message in messages)
    assert any("missing citation link" in message for message in messages)
    assert any("numeric source file does not exist" in message for message in messages)
    assert all("results/fig5.csv" not in message for message in messages)


def test_needs_tier3_returns_under_tiered_links_only():
    ledger = ClaimLedger()
    ledger.add_claim("c1", "Under-tiered.")
    ledger.link_citation("c1", "smith2020", CitationTier.TIER_1)
    ledger.add_claim("c2", "Full-text verified.")
    ledger.link_citation("c2", "lee2021", CitationTier.TIER_3)

    queue = ledger.needs_tier3()

    assert [link.citation_key for link in queue] == ["smith2020"]


def test_novel_claim_without_citation_does_not_flag():
    ledger = ClaimLedger()
    ledger.add_claim("c1", "New method claim.", kind="novel")
    ledger.link_figure("c1", "fig1")
    ledger.link_numeric("c1", "n=3", "source.csv")

    audit = ledger.audit()

    assert all("missing citation link" not in problem.message for problem in audit.problems)


def test_json_round_trip_emits_provenance(tmp_path: Path):
    ledger = ClaimLedger()
    ledger.add_claim(
        "c1",
        "Metabolism increases with hypoxia.",
        section="Results",
        status=ClaimReadiness.CITATION_TIERED,
        risk=RiskLevel.HIGH,
    )
    ledger.link_figure("c1", "figR5", panel="c")
    ledger.link_numeric("c1", "rho=0.31", "results/fig5.csv", stat_method="spearman")
    ledger.link_citation(
        "c1",
        "smith2020",
        CitationTier.TIER_3,
        status=VerificationStatus.VERIFIED_FULLTEXT,
    )
    path = tmp_path / "claim-ledger.json"

    written = ledger.to_json(path)
    reloaded = ClaimLedger.read_json(path)

    assert written == path
    assert reloaded.claims == ledger.claims
    assert reloaded.figure_links == ledger.figure_links
    assert reloaded.numeric_links == ledger.numeric_links
    assert reloaded.citation_links == ledger.citation_links
    assert json.loads(path.read_text(encoding="utf-8"))["schema"] == "vaultlab-claim-ledger/v1"
    assert path.with_suffix(path.suffix + ".provenance.json").exists()
    assert path.with_suffix(path.suffix + ".method.md").exists()


def test_to_markdown_renders_claim_evidence_table():
    ledger = ClaimLedger()
    ledger.add_claim("c1", "Metabolism increases with hypoxia.", section="Results")
    ledger.link_figure("c1", "figR5", panel="c")
    ledger.link_numeric("c1", "rho=0.31", "results/fig5.csv", stat_method="spearman")
    ledger.link_citation("c1", "smith2020", CitationTier.TIER_3)

    table = ledger.to_markdown()

    assert "| claim | section | readiness | figures | stat(source) | citation(tier) | issues |" in table
    assert "c1: Metabolism increases with hypoxia." in table
    assert "figR5:c" in table
    assert "rho=0.31 (results/fig5.csv; spearman)" in table
    assert "smith2020 (TIER_3)" in table
