"""Tests for vaultlab.runner.models — core data classes."""

from __future__ import annotations

from vaultlab.runner import (
    Meeting,
    MeetingMode,
    MeetingResult,
    MeetingTurn,
    Mode,
    Role,
)


def test_mode_enum_values() -> None:
    assert Mode.DATA_ANALYSIS.value == "data_analysis"
    assert Mode.LITERATURE_REVIEW.value == "literature_review"


def test_meeting_mode_enum_values() -> None:
    assert MeetingMode.ROUND_TABLE.value == "round_table"
    assert MeetingMode.ADVERSARIAL.value == "adversarial"
    assert MeetingMode.SYNTHESIS.value == "synthesis"
    assert MeetingMode.INDIVIDUAL.value == "individual"


def test_role_defaults() -> None:
    role = Role(id="x", name="X", system_prompt="hi")
    assert role.mode == Mode.DATA_ANALYSIS
    assert role.focus_areas == []
    assert role.evaluation_criteria == []
    assert role.output_format == ""


def test_meeting_can_be_constructed() -> None:
    role = Role(id="x", name="X", system_prompt="p")
    meeting = Meeting(
        topic="LPI correlations",
        mode=MeetingMode.ADVERSARIAL,
        roles=[role],
        session_context="ctx",
    )
    assert meeting.topic == "LPI correlations"
    assert meeting.round_num == 1
    assert len(meeting.roles) == 1


def test_meeting_turn_defaults() -> None:
    turn = MeetingTurn(role_id="x", prompt="p")
    assert turn.output == ""
    assert turn.output_path == ""


def test_meeting_result_holds_turns() -> None:
    result = MeetingResult(
        topic="t",
        mode=MeetingMode.SYNTHESIS,
        round_num=1,
        turns=[MeetingTurn(role_id="synthesizer", prompt="p", output="done")],
    )
    assert result.turns[0].output == "done"


def test_models_importable_from_models_submodule() -> None:
    """Tests/callers may import directly from ``vaultlab.runner.models``."""
    from vaultlab.runner.models import Agenda, InvestigationMode, Meeting

    a = Agenda(topic="t", statement="s", investigation_mode=InvestigationMode.EXPLORATORY)
    assert a.investigation_mode == InvestigationMode.EXPLORATORY
    # Sanity: rendered agenda contains the mode header
    assert "EXPLORATORY" in a.render()
    assert Meeting is not None
