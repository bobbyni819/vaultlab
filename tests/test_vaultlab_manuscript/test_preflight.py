"""Tests for vaultlab.manuscript.preflight."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from vaultlab.manuscript.preflight import (
    DEFAULT_REVIEWER_ROLES,
    FixItem,
    run_manuscript_preflight,
)
from vaultlab.roles._invoke import AuditPrompt


def _manuscript() -> str:
    return """
    [CLAIM:c1 kind=quantitative section=Results] The cohort association was rho=0.42.
    [STAT:rho=0.42 src=stats.csv]
    [CITE:smith2020 tier=1]

    The key result appears in Figure 5.
    """


def test_preflight_builds_deterministic_queue_and_prepared_role_items(tmp_path: Path) -> None:
    report = run_manuscript_preflight(
        _manuscript(),
        artifact_path=tmp_path / "manuscript.md",
        figures_dir=tmp_path / "figures",
        roles=["journal_reviewer", "definitely_missing_role"],
        target_journal="cell-systems",
    )

    assert not report.ok
    assert report.aggregated is None
    assert {item.severity for item in report.fix_queue[:3]} == {"error"}
    assert any(
        item.source == "claim_ledger" and "missing figure link" in item.message
        for item in report.fix_queue
    )
    assert any(
        item.source == "claim_ledger" and "needs Tier-3" in item.message
        for item in report.fix_queue
    )
    assert any(
        item.source == "figure_text" and "Figure 5 is referenced" in item.message
        for item in report.fix_queue
    )
    assert any(
        item.source == "role:journal_reviewer"
        and item.severity == "info"
        and "review prepared" in item.message
        for item in report.fix_queue
    )
    assert any(
        item.source == "role:definitely_missing_role"
        and item.severity == "warning"
        and "could not be prepared" in item.message
        for item in report.fix_queue
    )
    assert [role.role_id for role in report.prepared_roles] == [
        "journal_reviewer",
        "definitely_missing_role",
    ]
    assert report.prepared_roles[0].prompt is not None
    assert report.prepared_roles[1].prompt is None


def test_fake_executor_populates_aggregation_and_role_findings(tmp_path: Path) -> None:
    def fake_executor(prompt: AuditPrompt) -> dict[str, Any]:
        return {
            "_role": prompt.role.id,
            "target_artifact": str(prompt.artifact_path),
            "verdict": "ship_with_revisions",
            "evidence_axis": "solid",
            "issues": [
                {
                    "severity": "major",
                    "issue": f"{prompt.role.id} wants a limitations paragraph",
                    "fix": "Add a direct limitations paragraph before submission.",
                }
            ],
        }

    report = run_manuscript_preflight(
        _manuscript(),
        artifact_path=tmp_path / "manuscript.md",
        figures_dir=tmp_path / "figures",
        roles=["journal_reviewer"],
        target_journal="cell-systems",
        executor=fake_executor,
    )

    assert report.aggregated is not None
    assert report.aggregated.role_count == 1
    assert report.aggregated.issue_count["major"] == 1
    assert any(
        item.source == "role:journal_reviewer"
        and item.severity == "warning"
        and "limitations paragraph" in item.message
        for item in report.fix_queue
    )
    assert not any("without a message" in item.message for item in report.fix_queue)
    assert not any("review prepared" in item.message for item in report.fix_queue)


def test_to_dict_and_markdown_render_ranked_queue(tmp_path: Path) -> None:
    report = run_manuscript_preflight(
        _manuscript(),
        artifact_path=tmp_path / "manuscript.md",
        roles=[],
    )

    payload = report.to_dict()
    rendered = report.to_markdown()

    assert payload["ok"] is False
    assert payload["fix_queue"][0]["severity"] == "error"
    assert "# Manuscript Preflight Report" in rendered
    assert "## Ranked fix queue" in rendered
    assert "claim_ledger" in rendered
    assert "quantitative claim missing figure link" in rendered


def test_default_role_constant_matches_capstone_spec() -> None:
    assert DEFAULT_REVIEWER_ROLES == (
        "rigor_auditor",
        "methods_critic",
        "journal_reviewer",
        "expert_reviewer",
        "publication_guideline_compliance",
        "figure_reader",
    )


def test_fix_item_to_dict_omits_none_values() -> None:
    assert FixItem("claim_ledger", "error", "x").to_dict() == {
        "source": "claim_ledger",
        "severity": "error",
        "message": "x",
    }
