"""Tests for LocalRunner (dry-run mode + fake-client; real API calls are
integration-only).

Lifted from ``bobby-tools/tests/test_bobby_ailab/test_local_runner.py``.
"""

from __future__ import annotations

from vaultlab.runner import LocalRunner, LocalRunnerConfig, build_meeting


def test_local_runner_is_dry_run_by_default() -> None:
    runner = LocalRunner(kb_path="/tmp", command_name="c")
    assert runner.is_dry_run


def test_local_runner_execute_fills_turn_outputs() -> None:
    runner = LocalRunner(kb_path="/tmp", command_name="c")
    m = build_meeting(topic="t", meeting_type="reasoning", session_context="ctx")
    plan = runner.plan(m, task="x")
    assert all(t.output == "" for t in plan.turns)
    plan = runner.execute(plan)
    assert all(t.output.startswith("[DRY RUN]") for t in plan.turns)


def test_local_runner_execute_propagates_outputs_to_later_prompts() -> None:
    runner = LocalRunner(kb_path="/tmp", command_name="c")
    m = build_meeting(topic="t", meeting_type="reasoning", session_context="ctx")
    plan = runner.plan(m, task="x")
    plan = runner.execute(plan)
    # After execute, the critic's prompt (final step) should contain the
    # dry-run stubs from analyst + expert
    critic_prompt = plan.steps[-1].prompt
    assert "[DRY RUN] Data Analyst" in critic_prompt
    assert "[DRY RUN] Domain Expert" in critic_prompt


def test_local_runner_custom_stub() -> None:
    runner = LocalRunner(
        kb_path="/tmp",
        command_name="c",
        config=LocalRunnerConfig(dry_run_stub=lambda s: f"CUSTOM:{s.role_id}"),
    )
    m = build_meeting(topic="t", meeting_type="narrate", session_context="ctx")
    plan = runner.plan(m, task="x")
    plan = runner.execute(plan)
    assert plan.turns[0].output == "CUSTOM:narrator"


def test_local_runner_inherits_tool_selection_from_parent() -> None:
    runner = LocalRunner(kb_path="/tmp", command_name="c")
    m = build_meeting(topic="t", meeting_type="reasoning", session_context="ctx")
    plan = runner.plan(m, task="x")
    # Same tool allow-list as ClaudeCodeRunner
    assert "Bash" in plan.steps[0].tools  # data_analyst
    assert "Bash" not in plan.steps[2].tools  # methods_critic


def test_local_runner_with_fake_client_calls_messages_create() -> None:
    """Verify the real-client code path by using a fake messages API."""
    calls = []

    class FakeMessage:
        content = [type("Block", (), {"text": "fake response text"})()]

    class FakeMessages:
        def create(self, **kwargs):
            calls.append(kwargs)
            return FakeMessage()

    class FakeClient:
        messages = FakeMessages()

    runner = LocalRunner(kb_path="/tmp", command_name="c", client=FakeClient())
    assert not runner.is_dry_run
    m = build_meeting(topic="t", meeting_type="narrate", session_context="ctx")
    plan = runner.plan(m, task="x")
    plan = runner.execute(plan)
    assert plan.turns[0].output == "fake response text"
    assert len(calls) == 1
    assert calls[0]["model"] == "claude-opus-4-7"


def test_local_runner_handles_empty_response_blocks() -> None:
    class FakeMessage:
        content = []

    class FakeMessages:
        def create(self, **kwargs):
            return FakeMessage()

    class FakeClient:
        messages = FakeMessages()

    runner = LocalRunner(kb_path="/tmp", command_name="c", client=FakeClient())
    m = build_meeting(topic="t", meeting_type="narrate", session_context="ctx")
    plan = runner.plan(m, task="x")
    plan = runner.execute(plan)
    assert plan.turns[0].output == ""
