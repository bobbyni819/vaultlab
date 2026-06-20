"""Tests for vaultlab.manuscript.state."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from vaultlab.manuscript.state import (
    ManuscriptStage,
    assess_manuscript,
    read_json,
)
from vaultlab.roles._invoke import AuditPrompt


def _blocked_manuscript() -> str:
    return """
    [CLAIM:c1 kind=quantitative section=Results] The cohort association was rho=0.42.
    [STAT:rho=0.42 src=stats.csv]
    [CITE:smith2020 tier=1]

    The key result appears in Figure 5.
    """


def _cleaner_manuscript() -> str:
    return """
    [CLAIM:c1 kind=quantitative section=Results] The cohort association was rho=0.42.
    [FIG:5]
    [STAT:rho=0.42 src=stats.csv]
    [CITE:smith2020 tier=3]

    The key result appears in Figure 5.
    """


def test_blocked_manuscript_stays_drafting_with_evidence_and_citation_blockers() -> None:
    state = assess_manuscript(_blocked_manuscript(), roles=[])

    assert state.current_stage is ManuscriptStage.DRAFTING
    evidence_gate = state.gate_for(ManuscriptStage.EVIDENCE_LINKED)
    citation_gate = state.gate_for(ManuscriptStage.CITATION_TIERED)

    assert not evidence_gate.passed
    assert any("missing figure link" in blocker for blocker in evidence_gate.blockers)
    assert not citation_gate.passed
    assert citation_gate.blockers == ["smith2020 needs Tier-3"]
    assert state.n_claims == 1
    assert state.n_blocked_citations == 1
    assert any(item.source == "citation_gate" for item in state.fix_queue)


def test_cleaner_manuscript_advances_to_citation_tiered_without_executed_roles() -> None:
    state = assess_manuscript(_cleaner_manuscript(), roles=[])

    assert state.current_stage is ManuscriptStage.CITATION_TIERED
    assert state.gate_for(ManuscriptStage.EVIDENCE_LINKED).passed
    assert state.gate_for(ManuscriptStage.FIGURE_SYNCED).passed
    assert state.gate_for(ManuscriptStage.CITATION_TIERED).passed
    assert not state.gate_for(ManuscriptStage.REVIEWER_AUDITED).passed
    assert state.gate_for(ManuscriptStage.REVIEWER_AUDITED).blockers == [
        "reviewer role passes prepared but not executed"
    ]


def test_cleaner_manuscript_with_clean_executor_advances_to_submission_ready() -> None:
    def fake_executor(prompt: AuditPrompt) -> dict[str, Any]:
        return {
            "_role": prompt.role.id,
            "target_artifact": str(prompt.artifact_path),
            "verdict": "ship",
            "evidence_axis": "compelling",
            "issues": [],
        }

    state = assess_manuscript(
        _cleaner_manuscript(),
        roles=["journal_reviewer"],
        executor=fake_executor,
    )

    assert state.current_stage is ManuscriptStage.SUBMISSION_READY
    assert all(gate.passed for gate in state.gates)


def test_json_round_trip_preserves_stage_gates_and_fix_queue(tmp_path: Path) -> None:
    state = assess_manuscript(
        _blocked_manuscript(),
        roles=[],
        title="Blocked draft",
        timestamp="2026-06-20T12:00:00Z",
    )

    target = state.to_json(tmp_path / "state.json")
    loaded = read_json(target)

    assert loaded.current_stage is ManuscriptStage.DRAFTING
    assert loaded.title == "Blocked draft"
    assert loaded.timestamp == "2026-06-20T12:00:00Z"
    assert loaded.gate_for(ManuscriptStage.CITATION_TIERED).blockers == ["smith2020 needs Tier-3"]
    assert [item.to_dict() for item in loaded.fix_queue] == [
        item.to_dict() for item in state.fix_queue
    ]


def test_to_markdown_renders_five_gate_dashboard() -> None:
    state = assess_manuscript(_blocked_manuscript(), roles=[])

    rendered = state.to_markdown()

    assert "# Manuscript State Dashboard" in rendered
    assert "- **Current stage:** `DRAFTING`" in rendered
    assert rendered.count("- [") == 5
    assert "- [ ] EVIDENCE_LINKED" in rendered
    assert "- [ ] SUBMISSION_READY" in rendered
    assert "## Ranked fix queue" in rendered
