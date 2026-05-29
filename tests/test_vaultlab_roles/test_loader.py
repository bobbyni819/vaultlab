"""Tests for vaultlab.roles — markdown+YAML role template loader.

Verifies the 8 roles lifted from bobby_ailab._roles.py load correctly,
expose non-empty prompt + metadata, and preserve the substantive content
of the original Python string literals (round-trip check via signature
substrings — exact matches up to whitespace/normalization).
"""

from __future__ import annotations

import pytest

EXPECTED_ROLE_IDS = {
    "data_analyst",
    "literature_surveyor",
    "domain_expert",
    "methods_critic",
    "literature_critic",
    "synthesizer",
    "narrator",
    "figure_lead",
    "team_lead",
    "figure_reader",
    "rigor_auditor",
    # SPEC-B meta-agent roles (shipped 2026-05-08)
    "journal_reviewer",
    "expert_reviewer",
    "adoption_evaluator",
    "publication_guideline_compliance",
}


# Distinctive substrings from each role's original system_prompt in
# bobby_ailab._roles.py. If the prompt was lifted faithfully, every one of
# these must appear in the corresponding role's prompt text.
ROUND_TRIP_SIGNATURES: dict[str, list[str]] = {
    "data_analyst": [
        "You are a Data Analyst.",
        "Your ONLY job is to load data and report exact values.",
        "Never describe data from memory",
        "Flag outliers (>2 SD from mean) explicitly",
    ],
    "literature_surveyor": [
        "You are a Literature Surveyor.",
        "Never cite papers from memory",
        "paperclip MCP",
        "Rate each paper's relevance to the specific finding (HIGH/MEDIUM/LOW)",
    ],
    "domain_expert": [
        "You are a Domain Expert.",
        "EXPECTED",
        "NOVEL",
        "SURPRISING",
        "UNEXPLAINED",
        "Propose a mechanism",
    ],
    "methods_critic": [
        "You are a Methods Critic.",
        "ROBUST",
        "NEEDS_VALIDATION",
        "WEAK",
        "UNSUPPORTED",
        "Multiple testing",
    ],
    "literature_critic": [
        "You are a Literature Critic.",
        "STRONG_CONSENSUS",
        "EMERGING_EVIDENCE",
        "SINGLE_STUDY",
        "CONTESTED",
        "Replication",
    ],
    "synthesizer": [
        "You are a Research Synthesizer.",
        "Cross-finding connections",
        "Narrative arc",
        "Tier 1",
        "Tier 2",
        "Tier 3",
    ],
    "narrator": [
        "You are a Finding Narrator.",
        "plain-English explanation",
        "One finding per file",
    ],
    "figure_lead": [
        "You are a Figure Lead.",
        "FIGURE PLAN",
        "visual hook",
        "2-6 panels",
    ],
    "team_lead": [
        "Principal Investigator",
        "Team Member Input",
        "Recommendation",
        "Next Steps",
    ],
    "figure_reader": [
        "You are a Figure Reader.",
        "block structure",
        "sign reversals",
        "Read tool",
    ],
    "rigor_auditor": [
        "You are a Rigor Auditor.",
        "final gate before a document ships",
        "Page-marker integrity",
        "passed",
    ],
    # SPEC-B meta-agent roles (signatures match prompts authored 2026-05-08)
    "journal_reviewer": [
        "You are a Journal Reviewer.",
        "Cell",
        "Nature",
        "eLife",
        "structured verdict",
    ],
    "expert_reviewer": [
        "You are an Expert Reviewer.",
        "PI",
        "advisor",
        "would_signoff_for_grant",
        "Anticipated PI / advisor questions",
    ],
    "adoption_evaluator": [
        "You are an Adoption Evaluator.",
        "fresh new user",
        "first 30 minutes",
        "what_they_see",
    ],
    "publication_guideline_compliance": [
        "You are a Publication Guideline Compliance",
        "DPI",
        "journal_guidelines",
        "fig_dpi",
    ],
}


class TestListRoles:
    def test_returns_full_catalog(self) -> None:
        from vaultlab.roles import list_roles

        roles = list_roles()
        assert len(roles) == len(EXPECTED_ROLE_IDS), (
            f"expected {len(EXPECTED_ROLE_IDS)} roles, got {len(roles)}: {roles}"
        )

    def test_returns_expected_ids(self) -> None:
        from vaultlab.roles import list_roles

        assert set(list_roles()) == EXPECTED_ROLE_IDS

    def test_returns_sorted(self) -> None:
        from vaultlab.roles import list_roles

        roles = list_roles()
        assert roles == sorted(roles)


class TestLoadRole:
    @pytest.mark.parametrize("role_id", sorted(EXPECTED_ROLE_IDS))
    def test_each_role_loads(self, role_id: str) -> None:
        from vaultlab.roles import load_role

        role = load_role(role_id)
        assert role.id == role_id

    @pytest.mark.parametrize("role_id", sorted(EXPECTED_ROLE_IDS))
    def test_prompt_non_empty(self, role_id: str) -> None:
        from vaultlab.roles import load_role

        role = load_role(role_id)
        assert role.system_prompt.strip(), f"{role_id} has empty prompt"
        assert len(role.system_prompt) > 100, f"{role_id} prompt suspiciously short"

    @pytest.mark.parametrize("role_id", sorted(EXPECTED_ROLE_IDS))
    def test_name_non_empty(self, role_id: str) -> None:
        from vaultlab.roles import load_role

        role = load_role(role_id)
        assert role.name.strip()

    @pytest.mark.parametrize("role_id", sorted(EXPECTED_ROLE_IDS))
    def test_focus_areas_non_empty(self, role_id: str) -> None:
        from vaultlab.roles import load_role

        role = load_role(role_id)
        assert role.focus_areas, f"{role_id} has no focus areas"

    @pytest.mark.parametrize("role_id", sorted(EXPECTED_ROLE_IDS))
    def test_evaluation_criteria_non_empty(self, role_id: str) -> None:
        from vaultlab.roles import load_role

        role = load_role(role_id)
        assert role.evaluation_criteria, f"{role_id} has no evaluation criteria"

    @pytest.mark.parametrize("role_id", sorted(EXPECTED_ROLE_IDS))
    def test_mode_is_recognized(self, role_id: str) -> None:
        from vaultlab.roles import load_role

        role = load_role(role_id)
        assert role.mode in {"data_analysis", "literature_review"}

    @pytest.mark.parametrize("role_id", sorted(EXPECTED_ROLE_IDS))
    def test_output_format_non_empty(self, role_id: str) -> None:
        from vaultlab.roles import load_role

        role = load_role(role_id)
        assert role.output_format.strip(), f"{role_id} has no output format"

    def test_unknown_role_raises(self) -> None:
        from vaultlab.roles import RoleNotFoundError, load_role

        with pytest.raises(RoleNotFoundError):
            load_role("nonexistent_role")

    def test_rigor_auditor_has_descriptive_carveout(self) -> None:
        """B014 fix: descriptive arithmetic must be exempt from citation."""
        from vaultlab.roles import load_role

        prompt = load_role("rigor_auditor").system_prompt
        # The carve-out is present and names descriptive stats.
        assert "Descriptive-arithmetic carve-out" in prompt
        assert "statistical_summary_without_method_citation" in prompt
        # The inferential boundary is preserved (not a blanket stats pass).
        assert "INFERENTIAL results still require grounding" in prompt
        assert "significant" in prompt
        # The inline-method grounding is scoped to the pipeline's own
        # recomputed lines and must NOT generalize to manuscript prose.
        assert "Scope of inline-method grounding (NARROW)" in prompt
        assert "It does NOT generalize" in prompt


class TestRoundTrip:
    """Each lifted prompt must contain the signature substrings of its source.

    These substrings are taken verbatim from bobby_ailab/_roles.py, so any
    drift from the original (e.g., paraphrasing during the lift) is caught.
    """

    @pytest.mark.parametrize("role_id", sorted(EXPECTED_ROLE_IDS))
    def test_signatures_present(self, role_id: str) -> None:
        from vaultlab.roles import load_role

        role = load_role(role_id)
        signatures = ROUND_TRIP_SIGNATURES[role_id]
        for sig in signatures:
            assert sig in role.system_prompt, (
                f"{role_id} prompt is missing expected signature {sig!r} — "
                f"prompt may have been paraphrased instead of lifted verbatim"
            )


class TestLoadAllRoles:
    def test_returns_all_roles(self) -> None:
        from vaultlab.roles import load_all_roles

        roles = load_all_roles()
        assert set(roles.keys()) == EXPECTED_ROLE_IDS

    def test_each_keyed_by_id(self) -> None:
        from vaultlab.roles import load_all_roles

        for rid, role in load_all_roles().items():
            assert role.id == rid


class TestPublicAPI:
    def test_exports(self) -> None:
        import vaultlab.roles as mod

        assert hasattr(mod, "Role")
        assert hasattr(mod, "load_role")
        assert hasattr(mod, "list_roles")
        assert hasattr(mod, "load_all_roles")
        assert hasattr(mod, "RoleNotFoundError")

    def test_role_dataclass_shape(self) -> None:
        from vaultlab.roles import load_role

        role = load_role("data_analyst")
        # Verify the dataclass exposes the expected attributes
        for attr in (
            "id",
            "name",
            "system_prompt",
            "mode",
            "icon",
            "focus_areas",
            "evaluation_criteria",
            "communication_style",
            "output_format",
            "tools_allowed",
        ):
            assert hasattr(role, attr), f"Role missing attribute: {attr}"
