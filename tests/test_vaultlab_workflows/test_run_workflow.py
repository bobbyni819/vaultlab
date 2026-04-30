"""Tests for vaultlab.workflows.run_workflow + run_workflow_with_reflection.

Lifted from ``bobby-tools/tests/test_bobby_ailab/test_run_workflow.py``.
"""

from __future__ import annotations

import os
import tempfile

import pytest

from vaultlab.config import ProjectConfig

from vaultlab.runner.models import InvestigationMode

from vaultlab.workflows import (
    plan_deep_think_round,
    plan_lit_dive,
    plan_narrate_finding,
    plan_synthesis,
    read_provenance,
    run_workflow,
    run_workflow_with_reflection,
)


@pytest.fixture
def cfg():
    with tempfile.TemporaryDirectory() as d:
        kb = os.path.join(d, "kb")
        os.makedirs(os.path.join(kb, "Output"))
        os.makedirs(os.path.join(kb, "Sources", "Notes"))
        os.makedirs(os.path.join(kb, "Wiki", "Concepts"))
        yield ProjectConfig(
            name="test", kb_path=kb,
            domain="test", domain_context="ctx",
        )


def _stub_agent(prefix: str = "STUB"):
    def fn(prompt: str, tools: list[str]) -> str:
        return f"{prefix}: {len(prompt)} chars, tools={tools}"
    return fn


def test_run_workflow_fills_all_turn_outputs(cfg):
    wp = plan_deep_think_round(cfg, topic="t")
    assert all(t.output == "" for t in wp.plan.turns)
    result = run_workflow(wp, agent_fn=_stub_agent())
    assert all(t.output.startswith("STUB") for t in result.plan.turns)


def test_run_workflow_writes_per_step_outputs_with_provenance(cfg):
    wp = plan_synthesis(cfg)
    run_workflow(wp, agent_fn=_stub_agent("SYN"))
    step_path = wp.plan.steps[0].output_path
    assert os.path.exists(step_path)
    content = open(step_path, encoding="utf-8").read()
    assert content.startswith("---")
    assert "generated_by: synthesize" in content
    assert "SYN:" in content


def test_run_workflow_writes_canonical_output(cfg):
    wp = plan_synthesis(cfg)
    run_workflow(wp, agent_fn=_stub_agent("CANON"))
    canonical = wp.canonical_output_path
    assert os.path.exists(canonical)
    content = open(canonical, encoding="utf-8").read()
    assert "generated_by: synthesize" in content
    assert "CANON:" in content


def test_run_workflow_skips_canonical_when_flag_off(cfg):
    wp = plan_synthesis(cfg)
    run_workflow(wp, agent_fn=_stub_agent(), write_canonical=False)
    assert not os.path.exists(wp.canonical_output_path)


def test_run_workflow_injects_prior_outputs_across_adversarial_steps(cfg):
    """Later steps should see earlier real outputs after run_workflow."""
    captured_prompts: list[str] = []

    def recording_agent(prompt: str, tools: list[str]) -> str:
        captured_prompts.append(prompt)
        return f"turn-{len(captured_prompts)} output"

    wp = plan_deep_think_round(cfg, topic="test topic")
    run_workflow(wp, agent_fn=recording_agent)

    # Step 2 (Expert) should see step 1's (Analyst) real output, not placeholder
    assert "turn-1 output" in captured_prompts[1]
    assert "will be inserted here by the runner" not in captured_prompts[1]
    # Step 4 (Synthesizer) should see turns 1-3
    assert "turn-1 output" in captured_prompts[3]
    assert "turn-2 output" in captured_prompts[3]
    assert "turn-3 output" in captured_prompts[3]


def test_run_workflow_per_step_provenance_has_role_tag(cfg):
    wp = plan_deep_think_round(cfg, topic="t")
    run_workflow(wp, agent_fn=_stub_agent())
    analyst_path = wp.plan.steps[0].output_path
    prov = read_provenance(analyst_path)
    assert prov is not None
    assert "data_analyst" in prov.tags
    assert prov.kind == "data_analyst" or "deep_think" in prov.kind


def test_run_workflow_respects_investigation_mode(cfg):
    """Agent prompts still carry the mode header after run_workflow."""
    captured: list[str] = []

    def fn(prompt, tools):
        captured.append(prompt)
        return "ok"

    wp = plan_deep_think_round(
        cfg, topic="t", investigation_mode=InvestigationMode.EXPLORATORY,
    )
    run_workflow(wp, agent_fn=fn)
    for p in captured:
        assert "INVESTIGATION MODE: EXPLORATORY" in p


def test_run_workflow_with_narrate_finding(cfg):
    wp = plan_narrate_finding(
        cfg, finding_id="F001",
        claim="test claim", exact_value="rho=0.5",
    )
    result = run_workflow(wp, agent_fn=_stub_agent("NARR"))
    assert os.path.exists(result.plan.steps[0].output_path)
    assert os.path.exists(result.canonical_output_path)
    assert "f001" in result.canonical_output_path.lower()


def test_run_workflow_provenance_contains_generated_by(cfg):
    wp = plan_lit_dive(cfg, topic="test")
    run_workflow(wp, agent_fn=_stub_agent("LIT"))
    prov = read_provenance(wp.canonical_output_path)
    assert prov is not None
    assert prov.generated_by == "lit-dive"
    assert prov.kind == "literature_dive"


def test_run_workflow_resume_uses_existing_outputs(cfg):
    wp = plan_synthesis(cfg)
    # First pass — write the file
    calls: list[int] = []

    def fn(prompt, tools):
        calls.append(1)
        return "first run output"

    run_workflow(wp, agent_fn=fn)
    assert len(calls) == 1

    # Second pass with resume=True — should NOT call agent again
    wp2 = plan_synthesis(cfg)
    calls2: list[int] = []

    def fn2(prompt, tools):
        calls2.append(1)
        return "second run output"

    run_workflow(wp2, agent_fn=fn2, resume=True)
    assert len(calls2) == 0
    assert "first run output" in wp2.plan.turns[0].output


def test_run_workflow_with_reflection_zero_falls_back(cfg):
    """max_reflections=0 should behave like plain run_workflow."""
    wp = plan_synthesis(cfg)
    result = run_workflow_with_reflection(
        wp, agent_fn=_stub_agent("REFL"), max_reflections=0,
    )
    assert result.plan.turns[0].output.startswith("REFL")
