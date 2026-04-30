"""Tests for vaultlab.runner.reflection.run_with_reflection.

Lifted from ``bobby-tools/tests/test_bobby_ailab/test_workflow_reflection.py``
— the reflection-loop primitive in isolation. Workflow-level reflection
behaviour (run_workflow_with_reflection) is exercised separately in
``test_vaultlab_workflows/test_run_workflow.py``.
"""

from __future__ import annotations

from vaultlab.runner.reflection import (
    DONE_SIGNAL_DEFAULT,
    REFLECTION_PROMPT_TEMPLATE,
    ReflectionResult,
    contains_done_signal,
    run_with_reflection,
)


# ---------------------------------------------------------------------------
# contains_done_signal
# ---------------------------------------------------------------------------


def test_contains_done_signal_explicit_match() -> None:
    assert contains_done_signal("I am done.")
    assert contains_done_signal("Some prose then I am done — really")


def test_contains_done_signal_alternate_phrasings() -> None:
    assert contains_done_signal("I'm done refining.")
    assert contains_done_signal("No further refinement is needed here.")
    assert contains_done_signal("Nothing to add, this is final.")


def test_contains_done_signal_negative() -> None:
    assert not contains_done_signal("Refining further: ...")
    assert not contains_done_signal("")


def test_contains_done_signal_custom_signal() -> None:
    assert contains_done_signal("STOP", explicit_signal="STOP")
    # default regex still also fires on canonical phrasing
    assert contains_done_signal("I am done", explicit_signal="STOP")


# ---------------------------------------------------------------------------
# ReflectionResult
# ---------------------------------------------------------------------------


def test_reflection_result_final_picks_last_nonempty() -> None:
    r = ReflectionResult(drafts=["first", "second", ""])
    assert r.final == "second"


def test_reflection_result_final_empty_when_no_drafts() -> None:
    r = ReflectionResult()
    assert r.final == ""


# ---------------------------------------------------------------------------
# run_with_reflection
# ---------------------------------------------------------------------------


def test_run_with_reflection_full_loop_runs_max_rounds() -> None:
    counter = {"n": 0}

    def agent(prompt: str, tools: list[str]) -> str:
        counter["n"] += 1
        return f"DRAFT {counter['n']}"

    result = run_with_reflection(
        agent_fn=agent,
        initial_prompt="initial prompt",
        max_reflections=3,
    )
    # 1 initial + 3 refinements = 4 calls
    assert counter["n"] == 4
    assert result.iterations_used == 4
    assert result.final == "DRAFT 4"
    assert result.stopped_early is False


def test_run_with_reflection_stops_on_done_signal_in_initial() -> None:
    def agent(prompt: str, tools: list[str]) -> str:
        return "I am done — first draft is final."

    result = run_with_reflection(
        agent_fn=agent,
        initial_prompt="prompt",
        max_reflections=5,
    )
    assert result.iterations_used == 1
    assert result.stopped_early is True
    assert "I am done" in result.final


def test_run_with_reflection_stops_on_done_signal_mid_loop() -> None:
    responses = iter([
        "draft 1",
        "draft 2",
        "I am done. Stopping.",
        "draft 4 (should never run)",
    ])

    def agent(prompt: str, tools: list[str]) -> str:
        return next(responses)

    result = run_with_reflection(
        agent_fn=agent,
        initial_prompt="prompt",
        max_reflections=5,
    )
    assert result.iterations_used == 3
    assert result.stopped_early is True
    assert "should never run" not in result.final


def test_run_with_reflection_passes_tools_to_agent() -> None:
    seen_tools: list[list[str]] = []

    def agent(prompt: str, tools: list[str]) -> str:
        seen_tools.append(list(tools))
        return "draft"

    run_with_reflection(
        agent_fn=agent,
        initial_prompt="p",
        max_reflections=1,
        tools=["Read", "Grep"],
    )
    assert seen_tools[0] == ["Read", "Grep"]
    assert seen_tools[1] == ["Read", "Grep"]


def test_run_with_reflection_zero_reflections_returns_only_initial_draft() -> None:
    counter = {"n": 0}

    def agent(prompt: str, tools: list[str]) -> str:
        counter["n"] += 1
        return f"DRAFT {counter['n']}"

    result = run_with_reflection(
        agent_fn=agent,
        initial_prompt="p",
        max_reflections=0,
    )
    assert counter["n"] == 1
    assert result.iterations_used == 1
    assert result.final == "DRAFT 1"


def test_run_with_reflection_refinement_prompt_uses_template() -> None:
    """The refinement prompt should embed the prior draft + round numbers."""
    seen_prompts: list[str] = []

    def agent(prompt: str, tools: list[str]) -> str:
        seen_prompts.append(prompt)
        return f"draft after prompt {len(seen_prompts)}"

    run_with_reflection(
        agent_fn=agent,
        initial_prompt="ORIGINAL",
        max_reflections=2,
    )
    # First prompt is the original; later prompts mention "Round" and prior
    assert seen_prompts[0] == "ORIGINAL"
    assert "Round 1 of 2" in seen_prompts[1]
    assert "draft after prompt 1" in seen_prompts[1]
    assert "Round 2 of 2" in seen_prompts[2]


def test_done_signal_default_constant() -> None:
    assert DONE_SIGNAL_DEFAULT == "I am done"
    # Template contains the done-signal text so prompts are self-explanatory
    assert "I am done" in REFLECTION_PROMPT_TEMPLATE
