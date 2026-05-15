"""Tests for deep-think crosstalk-policy wiring (SPEC-E sub-goal 2.4 followup).

The :mod:`vaultlab.workflows.crosstalk_policy` ``should_invoke`` gate was
already wired into ``lineage.run_lit_arc`` (picker + arc) and
``slides.deck.build_deck_from_lineage_result``. This test bundle covers
the deep-think wiring: ``plan_deep_think_round``,
``plan_deep_think_with_ensemble_critic``, and the runtime firing point
``run_deep_think_with_ensemble_critic``.

Every firing point records ``crosstalk_invoked`` / ``crosstalk_task_kind``
(and ``crosstalk_skip_reason`` when applicable) on the WorkflowPlan's
``Provenance.tags`` + ``notes`` so audits can reconstruct why a given
run was or wasn't a round-table — same shape as the lineage / deck-plan
wiring.
"""

from __future__ import annotations

import os
import tempfile

import pytest

from vaultlab.config import ProjectConfig
from vaultlab.workflows import (
    plan_deep_think_round,
    plan_deep_think_with_ensemble_critic,
    read_provenance,
    run_deep_think_with_ensemble_critic,
    run_workflow,
)


@pytest.fixture
def cfg():
    with tempfile.TemporaryDirectory() as d:
        kb = os.path.join(d, "kb")
        os.makedirs(os.path.join(kb, "Output"))
        os.makedirs(os.path.join(kb, "Sources", "Notes"))
        os.makedirs(os.path.join(kb, "Wiki", "Concepts"))
        yield ProjectConfig(
            name="test",
            kb_path=kb,
            domain="test-domain",
            domain_context="ctx",
        )


def _stub_agent(prefix: str = "STUB"):
    def fn(prompt: str, tools: list[str]) -> str:
        return f"{prefix}: {len(prompt)} chars"

    return fn


# ---------------------------------------------------------------------------
# plan_deep_think_round — single-round wiring
# ---------------------------------------------------------------------------


def test_plan_deep_think_round_records_crosstalk_decision_in_tags(cfg):
    """The classic round-table is task_kind=deep_think → fires by default."""
    wp = plan_deep_think_round(cfg, topic="t")
    tags = wp.provenance.tags
    assert "crosstalk_invoked=true" in tags
    assert "crosstalk_task_kind=deep_think" in tags


def test_plan_deep_think_round_records_decision_in_notes(cfg):
    """Notes carry the full structured decision summary."""
    wp = plan_deep_think_round(cfg, topic="t")
    notes = wp.provenance.notes
    assert "crosstalk_invoked=True" in notes
    assert "crosstalk_task_kind=deep_think" in notes
    # deep_think fires by default → no skip_reason in notes
    assert "crosstalk_skip_reason" not in notes


def test_plan_deep_think_round_decision_lands_in_step_output_provenance(cfg):
    """After run_workflow, each per-step output file's frontmatter carries
    the crosstalk decision via inherited tags (see ``_step_provenance``)."""
    wp = plan_deep_think_round(cfg, topic="t")
    run_workflow(wp, agent_fn=_stub_agent("RT"))
    analyst_path = wp.plan.steps[0].output_path
    prov = read_provenance(analyst_path)
    assert prov is not None
    assert any(t.startswith("crosstalk_invoked=") for t in prov.tags)
    assert "crosstalk_task_kind=deep_think" in prov.tags


# ---------------------------------------------------------------------------
# plan_deep_think_with_ensemble_critic — bundle wiring
# ---------------------------------------------------------------------------


def test_plan_ensemble_bundle_records_decision_on_every_phase(cfg):
    """Every phase (pre-critic, N critics, meta, synthesis) gets stamped."""
    bundle = plan_deep_think_with_ensemble_critic(cfg, topic="t", n_critics=3)
    for phase_wp in bundle.all_plans:
        tags = phase_wp.provenance.tags
        assert "crosstalk_invoked=true" in tags, (
            f"phase {phase_wp.provenance.kind!r} missing crosstalk_invoked tag"
        )
        assert "crosstalk_task_kind=deep_think" in tags


def test_plan_ensemble_bundle_synthesis_notes_carry_decision(cfg):
    """The synthesis phase — canonical final record — has the decision in notes."""
    bundle = plan_deep_think_with_ensemble_critic(cfg, topic="t", n_critics=2)
    notes = bundle.synthesis.provenance.notes
    assert "crosstalk_invoked=True" in notes
    assert "crosstalk_task_kind=deep_think" in notes


# ---------------------------------------------------------------------------
# run_deep_think_with_ensemble_critic — runtime firing point
# ---------------------------------------------------------------------------


def test_run_ensemble_runtime_stamps_hand_built_bundles(cfg):
    """A bundle whose phases never went through the planner still gets the
    decision stamped at runtime (the function is the canonical firing point)."""
    bundle = plan_deep_think_with_ensemble_critic(cfg, topic="t", n_critics=2)
    # Simulate a hand-built bundle by clearing the plan-time stamp on every phase
    for phase_wp in bundle.all_plans:
        phase_wp.provenance.tags = [
            t for t in phase_wp.provenance.tags if not t.startswith("crosstalk_")
        ]
        phase_wp.provenance.notes = ""

    # The agent is a stub; we only care that run_* re-stamps before/while firing
    run_deep_think_with_ensemble_critic(bundle, agent_fn=_stub_agent("ENS"))

    for phase_wp in bundle.all_plans:
        tags = phase_wp.provenance.tags
        assert "crosstalk_invoked=true" in tags
        assert "crosstalk_task_kind=deep_think" in tags


def test_run_ensemble_runtime_stamp_is_idempotent(cfg):
    """Double-stamping (plan-time + runtime) must not pile up duplicate tags
    or repeat the same notes summary."""
    bundle = plan_deep_think_with_ensemble_critic(cfg, topic="t", n_critics=2)
    # Phase plans already stamped at plan time. Now run — runtime call re-stamps.
    run_deep_think_with_ensemble_critic(bundle, agent_fn=_stub_agent("ENS"))

    for phase_wp in bundle.all_plans:
        tags = phase_wp.provenance.tags
        # Each marker should appear exactly once
        assert tags.count("crosstalk_invoked=true") == 1, (
            f"duplicate crosstalk_invoked tag on phase {phase_wp.provenance.kind!r}: {tags}"
        )
        assert tags.count("crosstalk_task_kind=deep_think") == 1
        # Notes summary deduped too
        notes = phase_wp.provenance.notes
        assert notes.count("crosstalk_invoked=True") == 1


def test_run_ensemble_writes_decision_into_synthesis_canonical_file(cfg):
    """The canonical synthesis output file's frontmatter records the decision."""
    bundle = plan_deep_think_with_ensemble_critic(cfg, topic="t", n_critics=2)
    run_deep_think_with_ensemble_critic(bundle, agent_fn=_stub_agent("ENS"))

    canonical = bundle.synthesis.canonical_output_path
    assert canonical is not None
    assert os.path.isfile(canonical)
    prov = read_provenance(canonical)
    assert prov is not None
    assert "crosstalk_invoked=true" in prov.tags
    assert "crosstalk_task_kind=deep_think" in prov.tags
    assert "crosstalk_invoked=True" in (prov.notes or "")
