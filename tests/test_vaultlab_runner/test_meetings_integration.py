"""Integration smoke test — meetings + roles wired end-to-end.

Verifies that a Role loaded from disk via :func:`vaultlab.roles.load_role`
is structurally identical to the runner's expected Role shape, and that
``build_meeting`` + ``compose_turns`` consume it without any adapter
indirection (no ``_to_vaultlab_role`` re-pack, no ``bobby_ailab`` import).

Guards against regressions of the structural mismatch the
``_to_vaultlab_role`` kludge previously bridged.
"""

from __future__ import annotations

from vaultlab.roles import ROLE_TEMPLATES, list_roles, load_role
from vaultlab.runner import (
    Agenda,
    MeetingMode,
    Mode,
    build_meeting,
    compose_turns,
)
from vaultlab.runner.models import Role as RunnerRole


class TestLoadedRoleIsRunnerRole:
    def test_load_role_returns_runner_role_type(self) -> None:
        role = load_role("data_analyst")
        # The canonical Role lives at vaultlab.runner.models.Role; the
        # loader must return that exact class so isinstance checks
        # downstream (e.g. inside Role.prompt_for) land correctly.
        assert isinstance(role, RunnerRole)

    def test_loaded_role_has_prompt_for(self) -> None:
        role = load_role("data_analyst")
        assert callable(getattr(role, "prompt_for", None))

    def test_loaded_role_mode_is_runner_mode(self) -> None:
        role = load_role("data_analyst")
        assert isinstance(role.mode, Mode)
        assert role.mode == Mode.DATA_ANALYSIS

    def test_literature_role_mode_swaps(self) -> None:
        role = load_role("literature_surveyor")
        assert role.mode == Mode.LITERATURE_REVIEW


class TestRoleTemplatesCatalog:
    def test_role_templates_dict_like_access(self) -> None:
        synth = ROLE_TEMPLATES["synthesizer"]
        assert isinstance(synth, RunnerRole)
        assert synth.id == "synthesizer"

    def test_role_templates_membership(self) -> None:
        assert "data_analyst" in ROLE_TEMPLATES
        assert "no_such_role" not in ROLE_TEMPLATES

    def test_role_templates_covers_full_disk_catalog(self) -> None:
        assert set(ROLE_TEMPLATES.keys()) == set(list_roles())


class TestBuildMeetingFromLoadedRoles:
    def test_round_table_with_explicit_loaded_roles(self) -> None:
        analyst = load_role("data_analyst")
        expert = load_role("domain_expert")
        agenda = Agenda(
            topic="LPI epithelial enrichment",
            statement="Survey what the data show across all 15 regions.",
            questions=["What is the strongest signal?"],
        )
        meeting = build_meeting(
            topic=agenda.topic,
            meeting_type="round_table",
            session_context="ctx: metabolomics, 15 regions",
            mode=Mode.DATA_ANALYSIS,
            agenda=agenda,
            roles=[analyst, expert],
        )
        assert meeting.mode == MeetingMode.ROUND_TABLE
        turns = compose_turns(meeting, task=agenda)
        assert len(turns) == 2
        # No PRIOR AGENT OUTPUTS in round-table; agenda block must render
        for turn in turns:
            assert "PRIOR AGENT OUTPUTS" not in turn.prompt
            assert "AGENDA" in turn.prompt

    def test_default_role_resolution_uses_disk_catalog(self) -> None:
        # build_meeting with no explicit roles delegates to roles_for(),
        # which now reads vaultlab.roles. The resulting role objects must
        # carry prompt_for and produce a usable prompt.
        meeting = build_meeting(
            topic="t", meeting_type="reasoning", session_context="ctx"
        )
        assert [r.id for r in meeting.roles] == [
            "data_analyst",
            "domain_expert",
            "methods_critic",
        ]
        turns = compose_turns(meeting, task="investigate")
        # Adversarial: turn 1+ must see prior placeholder for turn 0
        assert "PRIOR AGENT OUTPUTS" in turns[1].prompt

    def test_team_meeting_resolves_team_lead(self) -> None:
        # team_lead/figure_reader were NOT in vaultlab.roles before the
        # reconciliation; this test guards their presence.
        meeting = build_meeting(
            topic="t", meeting_type="team_meeting", session_context="ctx"
        )
        assert meeting.roles[0].id == "team_lead"
        assert meeting.mode == MeetingMode.TEAM

    def test_figure_read_resolves_figure_reader(self) -> None:
        meeting = build_meeting(
            topic="t", meeting_type="figure_read", session_context="ctx"
        )
        assert meeting.roles[0].id == "figure_reader"
        assert meeting.mode == MeetingMode.INDIVIDUAL


class TestNoBobbyAilabInRunner:
    """Static guard — vaultlab.runner.meetings must not import bobby_ailab."""

    def test_meetings_module_has_no_bobby_ailab_imports(self) -> None:
        import vaultlab.runner.meetings as meetings_mod
        from pathlib import Path

        source = Path(meetings_mod.__file__).read_text(encoding="utf-8")
        # Allow doc references in module docstrings if any survive, but
        # forbid actual imports.
        forbidden = ("from bobby_ailab", "import bobby_ailab")
        for needle in forbidden:
            assert needle not in source, (
                f"vaultlab.runner.meetings still contains forbidden token: {needle!r}"
            )
