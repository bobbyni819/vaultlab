"""Tests for vaultlab.roles._invoke — the SPEC-B audit-role invocation wrapper.

Verifies the integration that closes audit-report-2026-05-08 §2.1 + §2.3:
loading journal guidelines, assembling the user prompt, and aggregating
multi-role verdicts into a single per-artifact rollup.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vaultlab.roles._invoke import (
    JOURNAL_TARGET_DEFAULTS,
    META_AGENT_ROLES,
    AggregatedAudit,
    AuditPreparationError,
    AuditPrompt,
    aggregate_audits,
    available_journal_yaml,
    load_journal_guideline_yaml,
    prepare_audit,
)


@pytest.fixture
def sample_artifact(tmp_path: Path) -> Path:
    """Sample concept doc to audit."""
    art = tmp_path / "sample-concept.md"
    art.write_text(
        "# Sample Concept\n\n"
        "We demonstrate that long-chain SMs accumulate in muscularis layer "
        "(n=4 donors, FDR q=0.003).\n\n"
        "Methods: Spearman correlation, BH-FDR.\n",
        encoding="utf-8",
    )
    return art


def test_journal_yaml_files_loadable() -> None:
    """All bundled journal yaml files are loadable + non-empty."""
    available = available_journal_yaml()
    # SPEC-H ships these 5
    expected = {"cell", "nature", "elife", "biorxiv", "_common"}
    assert expected.issubset(set(available)), (
        f"missing journal yaml: expected {expected}, got {available}"
    )
    for name in expected:
        loaded = load_journal_guideline_yaml(name)
        assert isinstance(loaded, dict)
        assert len(loaded) > 0, f"{name}.yaml is empty"


def test_journal_target_defaults_includes_cell_systems() -> None:
    """cell-systems routes to cell.yaml (per SPEC-H)."""
    assert JOURNAL_TARGET_DEFAULTS["cell-systems"] == "cell"
    assert JOURNAL_TARGET_DEFAULTS["nature"] == "nature"
    assert JOURNAL_TARGET_DEFAULTS["elife"] == "elife"


def test_meta_agent_roles_constant_matches_spec_b() -> None:
    """The exported META_AGENT_ROLES set matches what SPEC-B shipped."""
    expected = {
        "journal_reviewer",
        "expert_reviewer",
        "adoption_evaluator",
        "publication_guideline_compliance",
    }
    assert set(META_AGENT_ROLES) == expected


def test_prepare_audit_loads_role_and_artifact(sample_artifact: Path) -> None:
    """prepare_audit() returns a structured AuditPrompt."""
    bundle = prepare_audit(
        "journal_reviewer",
        sample_artifact,
        target_journal="cell-systems",
        load_kb_context=False,
    )
    assert isinstance(bundle, AuditPrompt)
    assert bundle.role.id == "journal_reviewer"
    assert "long-chain SMs" in bundle.artifact_text
    assert bundle.target_journal == "cell-systems"
    # cell-systems routes to cell.yaml
    assert "figure" in bundle.journal_yaml or "publisher" in bundle.journal_yaml


def test_prepare_audit_assembles_user_prompt(sample_artifact: Path) -> None:
    """The assembled user prompt includes role + artifact + journal yaml."""
    bundle = prepare_audit(
        "journal_reviewer",
        sample_artifact,
        target_journal="cell-systems",
        load_kb_context=False,
    )
    prompt = bundle.assembled_user_prompt()
    assert "Artifact under audit" in prompt
    assert "long-chain SMs" in prompt
    assert "Journal enforceable rules" in prompt
    # Common yaml is always loaded
    assert "Cross-journal common rules" in prompt or "okabe_ito" in prompt
    # Final task instruction present
    assert "Output ONLY the structured JSON" in prompt


def test_prepare_audit_unknown_role_raises(sample_artifact: Path) -> None:
    """Unknown role id raises AuditPreparationError."""
    with pytest.raises(AuditPreparationError, match="Role not found"):
        prepare_audit(
            "definitely_not_a_real_role_xyz",
            sample_artifact,
            target_journal="cell-systems",
            load_kb_context=False,
        )


def test_prepare_audit_missing_artifact_raises(tmp_path: Path) -> None:
    """Missing artifact raises AuditPreparationError."""
    nope = tmp_path / "does-not-exist.md"
    with pytest.raises(AuditPreparationError, match="Artifact not found"):
        prepare_audit(
            "journal_reviewer",
            nope,
            load_kb_context=False,
        )


def test_prepare_audit_unknown_journal_falls_back_gracefully(
    sample_artifact: Path,
) -> None:
    """Unknown target_journal falls back to lookup; missing yaml = empty dict."""
    bundle = prepare_audit(
        "journal_reviewer",
        sample_artifact,
        target_journal="some-niche-journal-xyz",
        load_kb_context=False,
    )
    # Falls back to looking up "some-niche-journal-xyz.yaml" which doesn't exist
    # → empty dict, but doesn't crash
    assert bundle.target_journal == "some-niche-journal-xyz"
    assert bundle.journal_yaml == {}


def test_prepare_audit_for_publication_guideline_role(
    sample_artifact: Path,
) -> None:
    """publication_guideline_compliance role is also wirable."""
    bundle = prepare_audit(
        "publication_guideline_compliance",
        sample_artifact,
        target_journal="nature",
        load_kb_context=False,
    )
    assert bundle.role.id == "publication_guideline_compliance"
    assert bundle.target_journal == "nature"
    # Loads nature.yaml
    assert "figure" in bundle.journal_yaml


def test_aggregate_audits_picks_worst_case() -> None:
    """aggregate_audits() returns worst-case verdict across reports."""
    reports = [
        {
            "_role": "journal_reviewer",
            "verdict": "ship_with_revisions",
            "evidence_axis": "solid",
            "issues": [
                {"severity": "minor", "issue": "x"},
                {"severity": "style", "issue": "y"},
            ],
        },
        {
            "_role": "expert_reviewer",
            "would_signoff_for_grant": True,
            "would_signoff_for_paper": False,
            "evidence_axis": "solid",
            "concerns": [
                {"severity": "major", "concern": "n=4 power"},
            ],
        },
        {
            "_role": "publication_guideline_compliance",
            "verdict": "ship",
            "checks": [
                {"name": "fig_dpi", "result": "pass"},
            ],
        },
    ]
    agg = aggregate_audits(reports)
    assert isinstance(agg, AggregatedAudit)
    assert agg.role_count == 3
    # Major issue exists → verdict downgrades to needs_minor_revision
    assert agg.aggregated_verdict in ("needs_minor_revision", "ship_with_revisions")
    assert agg.issue_count["major"] == 1
    assert agg.issue_count["minor"] == 1
    assert agg.issue_count["style"] == 1
    # Evidence axes — both "solid", so worst-case is "solid"
    assert agg.aggregated_evidence_axis == "solid"


def test_aggregate_audits_fail_overrides_ship() -> None:
    """A fail issue overrides a ship verdict."""
    reports = [
        {
            "_role": "journal_reviewer",
            "verdict": "ship",
            "issues": [{"severity": "fail", "issue": "contradiction"}],
        },
    ]
    agg = aggregate_audits(reports)
    assert agg.aggregated_verdict == "needs_major_revision"
    assert agg.issue_count["fail"] == 1


def test_aggregate_audits_empty_raises() -> None:
    """Empty reports list raises AuditPreparationError."""
    with pytest.raises(AuditPreparationError):
        aggregate_audits([])


def test_aggregate_audits_evidence_worst_case() -> None:
    """Evidence axis picks the lowest rank (closer to inadequate)."""
    reports = [
        {"_role": "a", "verdict": "ship", "evidence_axis": "compelling"},
        {"_role": "b", "verdict": "ship", "evidence_axis": "incomplete"},
        {"_role": "c", "verdict": "ship", "evidence_axis": "convincing"},
    ]
    agg = aggregate_audits(reports)
    # incomplete is the worst of {compelling, incomplete, convincing}
    assert agg.aggregated_evidence_axis == "incomplete"


def test_publication_compliance_warn_aggregates_as_minor() -> None:
    """publication_guideline_compliance uses 'warn' which maps to minor in aggregation."""
    reports = [
        {
            "_role": "publication_guideline_compliance",
            "verdict": "ship_with_revisions",
            "checks": [
                {"name": "fig_color_blind_safe", "result": "warn"},
                {"name": "fig_dpi", "result": "pass"},
            ],
        },
    ]
    agg = aggregate_audits(reports)
    assert agg.issue_count["minor"] == 1
