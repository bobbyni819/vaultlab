"""Tests for ClaudeCodeRunner.

Lifted from ``bobby-tools/tests/test_bobby_ailab/test_runner.py``.
"""

from __future__ import annotations

from vaultlab.runner import (
    Agenda,
    ClaudeCodeRunner,
    build_meeting,
    render_plan_as_instructions,
)


def test_runner_produces_one_step_per_turn() -> None:
    runner = ClaudeCodeRunner(kb_path="/tmp/kb", command_name="deep-think")
    m = build_meeting(topic="t", meeting_type="reasoning", session_context="ctx")
    plan = runner.plan(m, task="x")
    assert len(plan.steps) == 3
    assert [s.role_id for s in plan.steps] == [
        "data_analyst",
        "domain_expert",
        "methods_critic",
    ]


def test_runner_tool_selection_per_role() -> None:
    runner = ClaudeCodeRunner(kb_path="/tmp", command_name="c")
    m = build_meeting(topic="t", meeting_type="reasoning", session_context="ctx")
    plan = runner.plan(m, task="x")
    # data analyst gets Bash
    assert "Bash" in plan.steps[0].tools
    # methods critic does NOT get Bash
    assert "Bash" not in plan.steps[2].tools


def test_runner_narrator_gets_read_only() -> None:
    runner = ClaudeCodeRunner(kb_path="/tmp", command_name="narrate")
    m = build_meeting(topic="t", meeting_type="narrate", session_context="ctx")
    plan = runner.plan(m, task="x")
    assert plan.steps[0].tools == ("Read",)


def test_runner_output_path_structure() -> None:
    runner = ClaudeCodeRunner(
        kb_path="/tmp/kb", command_name="deep-think", date_str="2026-04-20"
    )
    m = build_meeting(
        topic="t", meeting_type="reasoning", session_context="ctx", round_num=2
    )
    plan = runner.plan(m, task="x")
    assert plan.steps[0].output_path.endswith(
        "deep-think-2026-04-20-round2-data_analyst.md"
    )


def test_runner_team_meeting_disambiguates_lead_initial_final() -> None:
    runner = ClaudeCodeRunner(
        kb_path="/kb", command_name="team", date_str="2026-04-20"
    )
    m = build_meeting(
        topic="t", meeting_type="team_meeting", session_context="ctx"
    )
    plan = runner.plan(m, task="x")
    lead_paths = [s.output_path for s in plan.steps if s.role_id == "team_lead"]
    assert len(lead_paths) == 2
    assert any("initial" in p for p in lead_paths)
    assert any("final" in p for p in lead_paths)


def test_runner_critiqued_meeting_disambiguates_role_open_response() -> None:
    runner = ClaudeCodeRunner(kb_path="/kb", command_name="c")
    m = build_meeting(
        topic="t", meeting_type="critiqued_domain_expert", session_context="ctx"
    )
    plan = runner.plan(m, task="x")
    expert_paths = [s.output_path for s in plan.steps if s.role_id == "domain_expert"]
    assert any("open" in p for p in expert_paths)
    assert any("response" in p for p in expert_paths)


def test_inject_prior_outputs_propagates_real_outputs() -> None:
    runner = ClaudeCodeRunner(kb_path="/kb", command_name="c")
    m = build_meeting(topic="t", meeting_type="reasoning", session_context="ctx")
    plan = runner.plan(m, task="x")
    plan.turns[0].output = "rho = 0.78 observed in data"
    plan2 = plan.inject_prior_outputs(plan.turns)
    # expert's step (index 1) now shows the real analyst output
    assert "rho = 0.78 observed in data" in plan2.steps[1].prompt
    assert "will be inserted here" not in plan2.steps[1].prompt


def test_runner_session_updates_include_critic_rating_hint() -> None:
    runner = ClaudeCodeRunner(kb_path="/kb", command_name="c")
    m = build_meeting(topic="t", meeting_type="reasoning", session_context="ctx")
    plan = runner.plan(m, task="x")
    hints = " ".join(plan.session_updates)
    assert "set_rating" in hints


def test_runner_respects_agenda() -> None:
    runner = ClaudeCodeRunner(kb_path="/kb", command_name="c")
    agenda = Agenda(
        topic="LPI", statement="assess", questions=["Q1?", "Q2?"]
    )
    m = build_meeting(
        topic="LPI",
        meeting_type="reasoning",
        session_context="ctx",
        agenda=agenda,
    )
    plan = runner.plan(m, task="ignored")
    for step in plan.steps:
        assert "Q1?" in step.prompt
        assert "Q2?" in step.prompt


def test_render_plan_as_instructions_emits_readable_markdown() -> None:
    runner = ClaudeCodeRunner(kb_path="/kb", command_name="c")
    m = build_meeting(topic="t", meeting_type="reasoning", session_context="ctx")
    plan = runner.plan(m, task="x")
    md = render_plan_as_instructions(plan)
    assert "# RunPlan:" in md
    assert "## Steps" in md
    assert "## Post-run actions" in md
    assert "Bash" in md  # tool lists appear


def test_runner_custom_tools_by_role() -> None:
    runner = ClaudeCodeRunner(
        kb_path="/kb",
        command_name="c",
        tools_by_role={"data_analyst": ("Read",)},  # override
    )
    m = build_meeting(topic="t", meeting_type="reasoning", session_context="ctx")
    plan = runner.plan(m, task="x")
    assert plan.steps[0].tools == ("Read",)
