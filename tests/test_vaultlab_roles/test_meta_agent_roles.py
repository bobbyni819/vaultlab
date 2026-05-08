"""Tests for the four SPEC-B meta-agent roles.

Validates that each role loads cleanly, has the required metadata fields,
and that its prompt + schema match the SPEC's requirements.

Smoke-test only — does NOT exercise an LLM. Runtime testing of role
outputs against real artifacts lives in
tests/test_vaultlab_roles/test_meta_agent_smoke.py (manual, requires
the runner + KB context preamble).
"""

from __future__ import annotations

import pytest

from vaultlab.roles import load_role, list_roles


META_AGENT_ROLES = [
    "journal_reviewer",
    "expert_reviewer",
    "adoption_evaluator",
    "publication_guideline_compliance",
]


@pytest.mark.parametrize("role_id", META_AGENT_ROLES)
def test_role_loads_cleanly(role_id: str) -> None:
    """Each meta-agent role loads without error from disk."""
    role = load_role(role_id)
    assert role.id == role_id
    assert role.name  # non-empty


@pytest.mark.parametrize("role_id", META_AGENT_ROLES)
def test_role_has_substantive_prompt(role_id: str) -> None:
    """Each role's prompt is substantive (not boilerplate)."""
    role = load_role(role_id)
    assert len(role.system_prompt) > 1000, (
        f"{role_id} prompt is too short ({len(role.system_prompt)} chars); "
        f"expected detailed TASKS contract per SPEC-B."
    )


@pytest.mark.parametrize("role_id", META_AGENT_ROLES)
def test_role_has_focus_areas(role_id: str) -> None:
    """Each role declares ≥ 4 focus areas (per SPEC-B requirement)."""
    role = load_role(role_id)
    assert len(role.focus_areas) >= 4, (
        f"{role_id} has only {len(role.focus_areas)} focus areas; "
        f"SPEC-B requires ≥ 4."
    )


@pytest.mark.parametrize("role_id", META_AGENT_ROLES)
def test_role_has_evaluation_criteria(role_id: str) -> None:
    """Each role declares ≥ 4 evaluation criteria."""
    role = load_role(role_id)
    assert len(role.evaluation_criteria) >= 4, (
        f"{role_id} has only {len(role.evaluation_criteria)} criteria; "
        f"SPEC-B requires ≥ 4."
    )


@pytest.mark.parametrize("role_id", META_AGENT_ROLES)
def test_role_output_format_specifies_json(role_id: str) -> None:
    """Each role's output_format mandates structured JSON (not free text)."""
    role = load_role(role_id)
    fmt = role.output_format.lower()
    assert "json" in fmt, (
        f"{role_id} output_format must specify JSON output; "
        f"SPEC-B requires structured-JSON-only outputs to prevent prompt drift."
    )


@pytest.mark.parametrize("role_id", META_AGENT_ROLES)
def test_role_lists_in_catalog(role_id: str) -> None:
    """Each role appears in the discoverable role catalog."""
    assert role_id in list_roles()


def test_journal_reviewer_uses_elife_axis() -> None:
    """journal_reviewer adopts eLife evidence-axis vocabulary."""
    role = load_role("journal_reviewer")
    fmt = role.output_format
    # eLife evidence vocabulary
    elife_terms = ["exceptional", "compelling", "convincing", "solid", "incomplete", "inadequate"]
    found = sum(1 for t in elife_terms if t in fmt.lower())
    assert found >= 5, (
        f"journal_reviewer output_format should reference the eLife evidence "
        f"vocabulary; found {found}/{len(elife_terms)} terms."
    )


def test_expert_reviewer_has_two_signoff_axes() -> None:
    """expert_reviewer distinguishes grant-readiness vs paper-readiness."""
    role = load_role("expert_reviewer")
    fmt = role.output_format
    assert "would_signoff_for_grant" in fmt
    assert "would_signoff_for_paper" in fmt
    assert "expert_questions" in fmt


def test_expert_reviewer_uses_elife_two_axis() -> None:
    """expert_reviewer uses eLife two-axis (significance × evidence) rubric."""
    role = load_role("expert_reviewer")
    fmt = role.output_format
    assert "significance_axis" in fmt
    assert "evidence_axis" in fmt


def test_expert_reviewer_uses_pi_archetype_as_gold_standard() -> None:
    """expert_reviewer leverages PI / advisor as the ideal-archetype.

    Per Bobby 2026-05-08: "PI / advisor / mentor" is the gold-standard
    archetype because they have full project oversight + domain expertise.
    The role is named expert_reviewer (audience-neutral) but the prompt
    leans on PI archetype as the simulated voice.
    """
    role = load_role("expert_reviewer")
    text = role.system_prompt + role.description
    text_lower = text.lower()
    # PI / advisor / mentor archetype must be present (gold standard)
    has_pi_archetype = (
        "pi" in text_lower or "advisor" in text_lower or "mentor" in text_lower
    )
    assert has_pi_archetype, (
        "expert_reviewer must reference the PI/advisor/mentor archetype "
        "as the gold standard for full-project-oversight expert review"
    )


def test_expert_reviewer_scales_beyond_academic_pi() -> None:
    """expert_reviewer also explicitly scales to non-academic-PI users.

    Solo researchers, postdocs, industry researchers, lab heads — the role
    must not be anchored only in formal academic PI structure.
    """
    role = load_role("expert_reviewer")
    text = role.system_prompt + role.description
    text_lower = text.lower()
    # Must mention at least one non-academic-PI user category
    non_pi_users = ["solo researcher", "postdoc", "industry", "lab head"]
    found = sum(1 for cat in non_pi_users if cat in text_lower)
    assert found >= 2, (
        "expert_reviewer must scale beyond academic-PI structure; "
        f"found {found}/{len(non_pi_users)} non-PI user categories mentioned"
    )


def test_adoption_evaluator_has_what_they_see() -> None:
    """adoption_evaluator's friction items include user-perspective field."""
    role = load_role("adoption_evaluator")
    fmt = role.output_format
    assert "what_they_see" in fmt, (
        "adoption_evaluator must surface user-perspective via what_they_see "
        "field per SPEC-B."
    )


def test_adoption_evaluator_has_bounce_risk_verdict() -> None:
    """adoption_evaluator has a bounce_risk verdict for severe friction."""
    role = load_role("adoption_evaluator")
    fmt = role.output_format
    assert "bounce_risk" in fmt


def test_publication_compliance_has_per_check_results() -> None:
    """publication_guideline_compliance outputs per-check structured results."""
    role = load_role("publication_guideline_compliance")
    fmt = role.output_format
    # Required check names
    required_checks = ["fig_dpi", "fig_font_min", "fig_color_blind_safe"]
    for check in required_checks:
        assert check in fmt, (
            f"publication_guideline_compliance must define {check} check"
        )


def test_publication_compliance_anchored_in_yaml() -> None:
    """publication_guideline_compliance references the journal_guidelines yaml bundle."""
    role = load_role("publication_guideline_compliance")
    prompt = role.system_prompt
    assert "journal_guidelines" in prompt, (
        "publication_guideline_compliance prompt must reference "
        "vaultlab/data/journal_guidelines/ yaml files"
    )


def test_all_four_roles_use_kb_paths() -> None:
    """All four meta-agent roles route outputs via vaultlab.kb.paths."""
    for role_id in META_AGENT_ROLES:
        role = load_role(role_id)
        prompt = role.system_prompt.lower()
        assert "kb output routing" in prompt or "vaultlab.kb.paths" in prompt, (
            f"{role_id} must reference KB output routing per AGENTS.md convention"
        )
