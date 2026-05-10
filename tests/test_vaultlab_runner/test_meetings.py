"""Tests for vaultlab.runner.meetings — meeting composition primitives.

Adapted from ``bobby-tools/tests/test_bobby_ailab/test_meetings.py``. The
imports point at the lifted ``vaultlab.runner`` surface; behaviour is
expected to be identical to the source.
"""

from __future__ import annotations

import pytest

from vaultlab.runner import (
    MeetingMode,
    Mode,
    adversarial_inject,
    build_meeting,
    compose_turns,
    merge_outputs,
)

# --- ADVERSARIAL --------------------------------------------------------------


def test_build_meeting_reasoning_data_mode() -> None:
    m = build_meeting(
        topic="LPI epithelial correlation",
        meeting_type="reasoning",
        session_context="domain: metabolomics",
    )
    assert m.mode == MeetingMode.ADVERSARIAL
    assert [r.id for r in m.roles] == ["data_analyst", "domain_expert", "methods_critic"]
    assert m.round_num == 1


def test_build_meeting_deep_think_includes_synthesizer_last() -> None:
    m = build_meeting(
        topic="full cycle",
        meeting_type="deep_think",
        session_context="ctx",
    )
    assert m.roles[-1].id == "synthesizer"


def test_compose_turns_adversarial_later_roles_see_placeholders() -> None:
    m = build_meeting(topic="t", meeting_type="reasoning", session_context="ctx")
    turns = compose_turns(m, task="investigate")
    assert "PRIOR AGENT OUTPUTS" not in turns[0].prompt  # analyst has no prior
    assert "PRIOR AGENT OUTPUTS" in turns[1].prompt  # expert sees analyst
    assert "PRIOR AGENT OUTPUTS" in turns[2].prompt  # critic sees both
    assert "Data Analyst output will be inserted" in turns[1].prompt


# --- ROUND_TABLE --------------------------------------------------------------


def test_compose_turns_round_table_no_priors() -> None:
    m = build_meeting(
        topic="t",
        meeting_type="round_table",
        session_context="ctx",
        roles=[
            build_meeting("t", "reasoning", "ctx").roles[0],
            build_meeting("t", "reasoning", "ctx").roles[2],
        ],
    )
    turns = compose_turns(m, task="analyze LPI")
    assert m.mode == MeetingMode.ROUND_TABLE
    assert len(turns) == 2
    for turn in turns:
        assert "PRIOR AGENT OUTPUTS" not in turn.prompt
        assert "analyze LPI" in turn.prompt
        assert "AGENDA" in turn.prompt


# --- SYNTHESIS ----------------------------------------------------------------


def test_build_meeting_synthesis_is_single_role() -> None:
    m = build_meeting(
        topic="arc",
        meeting_type="synthesis",
        session_context="ctx",
        prior_summary="F001: lpi rho 0.78",
    )
    assert m.mode == MeetingMode.SYNTHESIS
    assert len(m.roles) == 1
    assert m.roles[0].id == "synthesizer"


def test_compose_turns_synthesis_receives_prior_summary() -> None:
    m = build_meeting(
        topic="arc",
        meeting_type="synthesis",
        session_context="ctx",
        prior_summary="F001: lpi rho 0.78 ROBUST",
    )
    turns = compose_turns(m, task="integrate")
    assert len(turns) == 1
    assert "F001: lpi rho 0.78 ROBUST" in turns[0].prompt


# --- INDIVIDUAL ---------------------------------------------------------------


def test_compose_turns_individual_requires_exactly_one_role() -> None:
    m = build_meeting(topic="t", meeting_type="narrate", session_context="ctx")
    turns = compose_turns(m, task="narrate F001")
    assert m.mode == MeetingMode.INDIVIDUAL
    assert len(turns) == 1
    assert turns[0].role_id == "narrator"


# --- Round header / merge / inject -------------------------------------------


def test_compose_turns_round_includes_round_header() -> None:
    m = build_meeting(topic="t", meeting_type="reasoning", session_context="ctx", round_num=3)
    turns = compose_turns(m, task="x")
    assert "ROUND: 3" in turns[0].prompt


def test_merge_outputs_checks_role_order() -> None:
    m = build_meeting(topic="t", meeting_type="reasoning", session_context="ctx")
    turns = compose_turns(m, task="x")
    # swap two turns — should raise
    swapped = [turns[1], turns[0], turns[2]]
    with pytest.raises(ValueError, match="do not match"):
        merge_outputs(m, swapped)


def test_merge_outputs_happy_path() -> None:
    m = build_meeting(topic="t", meeting_type="reasoning", session_context="ctx")
    turns = compose_turns(m, task="x")
    for turn in turns:
        turn.output = f"{turn.role_id} said something"
    result = merge_outputs(m, turns)
    assert result.round_num == 1
    assert len(result.turns) == 3
    assert result.turns[2].output.endswith("said something")


def test_adversarial_inject_substitutes_real_priors() -> None:
    m = build_meeting(topic="t", meeting_type="reasoning", session_context="ctx")
    turns = compose_turns(m, task="x")
    turns[0].output = "rho = 0.78 for LPI"
    rewritten = adversarial_inject(turns)
    # expert (index 1) now sees analyst's actual output
    assert "rho = 0.78 for LPI" in rewritten[1].prompt
    assert "will be inserted here by the runner" not in rewritten[1].prompt
    # critic (index 2) also sees analyst's real output; expert's slot just drops
    # until expert has produced output
    assert "rho = 0.78 for LPI" in rewritten[2].prompt
    assert "will be inserted here by the runner" not in rewritten[2].prompt


def test_adversarial_inject_chains_multiple_outputs() -> None:
    m = build_meeting(topic="t", meeting_type="reasoning", session_context="ctx")
    turns = compose_turns(m, task="x")
    turns[0].output = "analyst says A"
    turns[1].output = "expert says B"
    rewritten = adversarial_inject(turns)
    critic_prompt = rewritten[2].prompt
    assert "analyst says A" in critic_prompt
    assert "expert says B" in critic_prompt


def test_build_meeting_literature_mode_swaps_roles() -> None:
    m = build_meeting(
        topic="t",
        meeting_type="reasoning",
        session_context="ctx",
        mode=Mode.LITERATURE_REVIEW,
    )
    ids = [r.id for r in m.roles]
    assert "literature_surveyor" in ids
    assert "literature_critic" in ids
    assert "data_analyst" not in ids
