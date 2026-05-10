"""Tests for vaultlab.workflows public builders.

Lifted from ``bobby-tools/tests/test_bobby_ailab/test_workflows.py``.
"""

from __future__ import annotations

import json
import os
import tempfile

import pytest

from vaultlab.config import ProjectConfig
from vaultlab.runner.models import (
    Agenda,
    InvestigationMode,
    MeetingMode,
)
from vaultlab.workflows import (
    DeepThinkEnsembleBundle,
    WorkflowPlan,
    plan_brainstorm_figures,
    plan_deep_think_round,
    plan_deep_think_with_ensemble_critic,
    plan_ensemble_critic,
    plan_lit_dive,
    plan_narrate_finding,
    plan_parallel_runs,
    plan_round_from_critic_tests,
    plan_synthesis,
)


@pytest.fixture
def cfg():
    with tempfile.TemporaryDirectory() as d:
        kb = os.path.join(d, "kb")
        os.makedirs(os.path.join(kb, "Output"))
        os.makedirs(os.path.join(kb, "Sources", "Notes"))
        os.makedirs(os.path.join(kb, "Wiki", "Concepts"))
        config = ProjectConfig(
            name="test",
            kb_path=kb,
            domain="metabolomics",
            domain_context="test project",
        )
        yield config


# ---------------------------------------------------------------------------
# plan_deep_think_round
# ---------------------------------------------------------------------------


def test_plan_deep_think_round_returns_workflow_plan(cfg):
    wp = plan_deep_think_round(cfg, topic="LPI test")
    assert isinstance(wp, WorkflowPlan)
    assert wp.meeting.topic == "LPI test"
    assert wp.meeting.mode == MeetingMode.ADVERSARIAL
    assert len(wp.plan.steps) == 4
    assert [s.role_id for s in wp.plan.steps] == [
        "data_analyst",
        "domain_expert",
        "methods_critic",
        "synthesizer",
    ]
    assert wp.provenance.generated_by == "deep-think"
    assert wp.provenance.round == 1


def test_plan_deep_think_round_respects_investigation_mode(cfg):
    wp = plan_deep_think_round(
        cfg,
        topic="x",
        investigation_mode=InvestigationMode.EXPLORATORY,
    )
    assert wp.meeting.agenda.investigation_mode == InvestigationMode.EXPLORATORY
    assert wp.provenance.investigation_mode == "exploratory"
    # every agent prompt carries the mode
    for step in wp.plan.steps:
        assert "INVESTIGATION MODE: EXPLORATORY" in step.prompt


def test_plan_deep_think_round_custom_agenda(cfg):
    agenda = Agenda(topic="x", statement="custom", questions=["Q1?"])
    wp = plan_deep_think_round(cfg, topic="x", agenda=agenda)
    for step in wp.plan.steps:
        assert "Q1?" in step.prompt


# ---------------------------------------------------------------------------
# plan_synthesis
# ---------------------------------------------------------------------------


def test_plan_synthesis_returns_canonical_output(cfg):
    wp = plan_synthesis(cfg)
    assert wp.canonical_output_path is not None
    assert wp.canonical_output_path.endswith(".md")
    assert "synthesis-" in wp.canonical_output_path
    assert wp.meeting.mode == MeetingMode.SYNTHESIS
    assert len(wp.plan.steps) == 1
    assert wp.plan.steps[0].role_id == "synthesizer"


def test_plan_synthesis_picks_up_existing_session_state(cfg):
    # write a minimal session file so session_summary_for_prompt has something
    session = {
        "project_name": "test",
        "kb_dir": cfg.kb_path,
        "domain": "metabolomics",
        "current_round": 1,
        "max_rounds": 4,
        "started": "2026-04-20",
        "next_id": 2,
        "findings": {
            "F001": {
                "id": "F001",
                "claim": "test claim",
                "status": "robust",
                "category": "novel",
                "confidence": 0.9,
                "data_source": "",
                "exact_value": "rho=0.5",
                "null_baseline": "",
                "mechanism": "",
                "literature": [],
                "chain": [],
                "branch_dir": "",
            }
        },
    }
    with open(os.path.join(cfg.kb_path, "Output", "research-session.json"), "w") as f:
        json.dump(session, f)
    wp = plan_synthesis(cfg)
    # the synthesizer's prompt should include the current finding summary
    assert "F001" in wp.plan.steps[0].prompt
    assert "test claim" in wp.plan.steps[0].prompt


# ---------------------------------------------------------------------------
# plan_brainstorm_figures
# ---------------------------------------------------------------------------


def test_plan_brainstorm_figures_uses_latest_synthesis(cfg):
    synth_path = os.path.join(cfg.kb_path, "Output", "synthesis-2026-04-20.md")
    with open(synth_path, "w") as f:
        f.write("# Synthesis\n\nLead: F042 with rho=0.98")
    wp = plan_brainstorm_figures(cfg)
    assert "F042 with rho=0.98" in wp.plan.steps[0].prompt
    assert wp.canonical_output_path.endswith("figure-plan.md")
    # two-role adversarial (FigureLead + Critic)
    assert [s.role_id for s in wp.plan.steps] == ["figure_lead", "methods_critic"]


# ---------------------------------------------------------------------------
# plan_narrate_finding
# ---------------------------------------------------------------------------


def test_plan_narrate_finding_output_path_uses_slug(cfg):
    wp = plan_narrate_finding(
        cfg,
        finding_id="F001",
        claim="LPI enriches in epithelium",
        exact_value="rho=0.78",
        data_source="corrs.csv",
    )
    assert "f001" in wp.canonical_output_path
    assert "lpi-enriches-in-epithelium" in wp.canonical_output_path
    assert wp.provenance.finding_ids == ["F001"]
    assert "rho=0.78" in wp.plan.steps[0].prompt
    assert "corrs.csv" in wp.plan.steps[0].prompt


# ---------------------------------------------------------------------------
# plan_lit_dive
# ---------------------------------------------------------------------------


def test_plan_lit_dive_uses_literature_surveyor(cfg):
    wp = plan_lit_dive(cfg, topic="GPR55 tight junctions")
    assert wp.plan.steps[0].role_id == "literature_surveyor"
    assert wp.meeting.mode == MeetingMode.INDIVIDUAL
    assert wp.meeting.agenda.investigation_mode == InvestigationMode.EXPLORATORY
    assert wp.provenance.generated_by == "lit-dive"
    assert "gpr55-tight-junctions" in wp.canonical_output_path
    assert wp.canonical_output_path.endswith(".md")


def test_plan_lit_dive_requires_topic(cfg):
    with pytest.raises(ValueError, match="non-empty topic"):
        plan_lit_dive(cfg, topic="   ")


def test_plan_lit_dive_prompt_includes_paperclip_instructions(cfg):
    wp = plan_lit_dive(cfg, topic="test topic")
    prompt = wp.plan.steps[0].prompt
    assert "paperclip" in prompt.lower()
    assert "stateful workflow" in prompt.lower()


# ---------------------------------------------------------------------------
# plan_round_from_critic_tests
# ---------------------------------------------------------------------------


def test_plan_round_from_critic_tests_parses_priority_lines(cfg):
    critic = """## Findings

### F001
- Rating: NEEDS_VALIDATION

**Priority next-round checks:**

1. [CRITICAL] Recompute aggregate at K=50 with permutation null
2. [HIGH] Verify the correlation against an independent cohort
3. [MEDIUM] Cross-check the literature claim with paperclip
"""
    wp = plan_round_from_critic_tests(
        cfg,
        critic_output=critic,
        topic="LPI",
        round_num=2,
    )
    # Each agenda question should carry the priority tag
    questions = wp.meeting.agenda.questions
    assert any("[CRITICAL]" in q for q in questions)
    assert any("[HIGH]" in q for q in questions)
    assert wp.meeting.agenda.investigation_mode == InvestigationMode.DIRECTED
    assert "round-from-critic" in wp.provenance.tags


def test_plan_round_from_critic_tests_priority_filter(cfg):
    critic = """**Priority next-round checks:**

1. [CRITICAL] Test A
2. [LOW] Test B
"""
    wp = plan_round_from_critic_tests(
        cfg,
        critic_output=critic,
        topic="t",
        priority_filter=["CRITICAL"],
    )
    questions = wp.meeting.agenda.questions
    assert any("[CRITICAL]" in q for q in questions)
    assert not any("[LOW]" in q for q in questions)


def test_plan_round_from_critic_tests_raises_when_no_priorities(cfg):
    with pytest.raises(ValueError, match="No priority-tagged tests"):
        plan_round_from_critic_tests(
            cfg,
            critic_output="just some prose, no priority tags",
            topic="t",
        )


# ---------------------------------------------------------------------------
# plan_parallel_runs
# ---------------------------------------------------------------------------


def test_plan_parallel_runs_returns_n_plans_plus_merge(cfg):
    parallels, merge = plan_parallel_runs(cfg, topic="t", num_runs=3)
    assert len(parallels) == 3
    for i, wp in enumerate(parallels):
        assert isinstance(wp, WorkflowPlan)
        assert f"parallel-run-{i + 1}" in wp.provenance.tags
        assert wp.provenance.kind == "parallel_run"
        # ensemble temperature should be set on every step
        for step in wp.plan.steps:
            assert step.temperature == 0.75
    assert merge.provenance.kind == "parallel_merge"
    assert "parallel-merge" in merge.provenance.tags


def test_plan_parallel_runs_requires_min_two(cfg):
    with pytest.raises(ValueError, match="num_runs >= 2"):
        plan_parallel_runs(cfg, topic="t", num_runs=1)


# ---------------------------------------------------------------------------
# plan_ensemble_critic
# ---------------------------------------------------------------------------


def test_plan_ensemble_critic_returns_critics_plus_meta(cfg):
    critics, meta = plan_ensemble_critic(
        cfg,
        topic="t",
        prior_outputs="some prior",
        n_critics=3,
    )
    assert len(critics) == 3
    for i, wp in enumerate(critics):
        assert wp.provenance.kind == "ensemble_critic"
        assert f"critic-{i + 1}" in wp.provenance.tags
        # critic-only meeting
        assert len(wp.plan.steps) == 1
        assert wp.plan.steps[0].role_id == "methods_critic"
        # ensemble temperature
        assert wp.plan.steps[0].temperature == 0.75
    assert meta.provenance.kind == "ensemble_meta_review"
    assert "meta-review" in meta.provenance.tags


def test_plan_ensemble_critic_requires_min_two_critics(cfg):
    with pytest.raises(ValueError, match="n_critics >= 2"):
        plan_ensemble_critic(cfg, topic="t", prior_outputs="x", n_critics=1)


# ---------------------------------------------------------------------------
# plan_deep_think_with_ensemble_critic
# ---------------------------------------------------------------------------


def test_plan_deep_think_with_ensemble_critic_structure(cfg):
    bundle = plan_deep_think_with_ensemble_critic(
        cfg,
        topic="t",
        n_critics=3,
        round_num=1,
    )
    assert isinstance(bundle, DeepThinkEnsembleBundle)
    # Phase 1: pre-critic — Analyst + Expert
    assert [s.role_id for s in bundle.pre_critic.plan.steps] == [
        "data_analyst",
        "domain_expert",
    ]
    # Phase 2: 3 critic plans
    assert len(bundle.critic_plans) == 3
    for cp in bundle.critic_plans:
        assert cp.plan.steps[0].role_id == "methods_critic"
    # Phase 3: meta-review (synthesizer-shaped)
    assert bundle.meta_review.plan.steps[0].role_id == "synthesizer"
    assert bundle.meta_review.provenance.kind == "ensemble_meta_review"
    # Phase 4: synthesis
    assert bundle.synthesis.plan.steps[0].role_id == "synthesizer"
    assert "ensemble-synthesis" in bundle.synthesis.provenance.tags
    assert bundle.synthesis.provenance.kind == "deep_think_ensemble_synthesis"
    # all_plans flattens correctly
    assert len(bundle.all_plans) == 1 + 3 + 1 + 1


def test_plan_deep_think_with_ensemble_critic_requires_min_two_critics(cfg):
    with pytest.raises(ValueError, match="n_critics >= 2"):
        plan_deep_think_with_ensemble_critic(cfg, topic="t", n_critics=1)


# ---------------------------------------------------------------------------
# Cross-cutting invariants
# ---------------------------------------------------------------------------


def test_provenance_tags_include_investigation_mode(cfg):
    wp = plan_deep_think_round(
        cfg,
        topic="x",
        investigation_mode=InvestigationMode.EXPLORATORY,
    )
    assert "exploratory" in wp.provenance.tags


def test_all_plans_can_serialize_provenance(cfg):
    for factory, args in [
        (plan_deep_think_round, {"topic": "t"}),
        (plan_synthesis, {}),
        (plan_brainstorm_figures, {}),
        (plan_lit_dive, {"topic": "t"}),
    ]:
        wp = factory(cfg, **args)
        # render_frontmatter should not raise
        md = wp.provenance.render_frontmatter()
        assert md.startswith("---\n")
        assert "generated_by:" in md
