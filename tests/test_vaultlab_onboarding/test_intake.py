"""Tests for vaultlab.onboarding.intake — fillable intake template.

Covers:
- Empty template rendering produces something parseable.
- Round-trip parse → render → parse is stable on key fields.
- Required-field validation raises IntakeValidationError.
- Checkbox parsing handles `[x]`, `[X]`, `[✓]`, `[ ]`.
- Free-form sections preserve user prose.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vaultlab.onboarding.intake import (
    INTAKE_SCHEMA,
    IntakeForm,
    IntakeValidationError,
    parse_intake_md,
    render_intake_template,
)

# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------


class TestRenderTemplate:
    def test_template_has_frontmatter(self) -> None:
        out = render_intake_template()
        assert out.startswith("---")
        assert "schema: vaultlab-intake/v1" in out

    def test_template_has_all_nine_sections(self) -> None:
        out = render_intake_template()
        for n in range(1, 10):
            assert f"## {n}." in out, f"section {n} missing from template"

    def test_template_has_required_field_markers(self) -> None:
        out = render_intake_template()
        # required: topic, goal, audience all explicitly marked
        assert "## 1. Topic (required)" in out
        assert "## 2. Goal (required)" in out
        assert "## 3. Audience (required)" in out

    def test_template_has_checkbox_lists(self) -> None:
        out = render_intake_template()
        # at minimum, multi-select sections must use checkbox syntax
        assert out.count("- [ ]") >= 10


# ---------------------------------------------------------------------------
# Parse — required fields
# ---------------------------------------------------------------------------


class TestParseRequired:
    def test_empty_template_fails_validation(self, tmp_path: Path) -> None:
        intake_p = tmp_path / "project_intake.md"
        intake_p.write_text(render_intake_template(), encoding="utf-8")
        with pytest.raises(IntakeValidationError, match="topic"):
            parse_intake_md(intake_p)

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            parse_intake_md(tmp_path / "nope.md")

    def test_topic_only_still_fails_for_goals(self, tmp_path: Path) -> None:
        intake_p = tmp_path / "project_intake.md"
        intake_p.write_text(_minimal_filled(topic="X"), encoding="utf-8")
        with pytest.raises(IntakeValidationError, match="goals"):
            parse_intake_md(intake_p)

    def test_topic_and_goal_still_fails_for_audience(self, tmp_path: Path) -> None:
        intake_p = tmp_path / "project_intake.md"
        intake_p.write_text(
            _minimal_filled(topic="X", goal_checked=True),
            encoding="utf-8",
        )
        with pytest.raises(IntakeValidationError, match="audiences"):
            parse_intake_md(intake_p)

    def test_required_fields_pass(self, tmp_path: Path) -> None:
        intake_p = tmp_path / "project_intake.md"
        intake_p.write_text(
            _minimal_filled(
                topic="spatial transcriptomics in PDAC",
                goal_checked=True,
                audience_checked=True,
            ),
            encoding="utf-8",
        )
        form = parse_intake_md(intake_p)
        assert form.topic == "spatial transcriptomics in PDAC"
        assert len(form.goals) >= 1
        assert len(form.audiences) >= 1


# ---------------------------------------------------------------------------
# Parse — checkbox handling
# ---------------------------------------------------------------------------


class TestCheckboxParsing:
    def test_lowercase_x(self, tmp_path: Path) -> None:
        intake_p = tmp_path / "i.md"
        intake_p.write_text(
            _build_md(
                topic="T",
                goals_block="- [x] Understand a literature field\n",
                audiences_block="- [x] Yourself (personal notes)\n",
            ),
            encoding="utf-8",
        )
        form = parse_intake_md(intake_p)
        assert "understand_literature" in form.goals

    def test_uppercase_X(self, tmp_path: Path) -> None:
        intake_p = tmp_path / "i.md"
        intake_p.write_text(
            _build_md(
                topic="T",
                goals_block="- [X] Understand a literature field\n",
                audiences_block="- [X] Yourself (personal notes)\n",
            ),
            encoding="utf-8",
        )
        form = parse_intake_md(intake_p)
        assert "understand_literature" in form.goals

    def test_unicode_check_mark(self, tmp_path: Path) -> None:
        intake_p = tmp_path / "i.md"
        intake_p.write_text(
            _build_md(
                topic="T",
                goals_block="- [✓] Understand a literature field\n",
                audiences_block="- [✓] Yourself (personal notes)\n",
            ),
            encoding="utf-8",
        )
        form = parse_intake_md(intake_p)
        assert "understand_literature" in form.goals

    def test_unchecked_skipped(self, tmp_path: Path) -> None:
        intake_p = tmp_path / "i.md"
        intake_p.write_text(
            _build_md(
                topic="T",
                goals_block=(
                    "- [x] Understand a literature field\n- [ ] Write a journal-club deck\n"
                ),
                audiences_block="- [x] Yourself (personal notes)\n",
            ),
            encoding="utf-8",
        )
        form = parse_intake_md(intake_p)
        assert "understand_literature" in form.goals
        assert "build_journal_club_deck" not in form.goals


# ---------------------------------------------------------------------------
# Parse — free-form prose
# ---------------------------------------------------------------------------


class TestFreeFormParsing:
    def test_pi_preferences_captured(self, tmp_path: Path) -> None:
        intake_p = tmp_path / "i.md"
        body = _build_md(
            topic="T",
            goals_block="- [x] Understand a literature field\n",
            audiences_block="- [x] PI / weekly meeting\n",
            pi_text="John prefers diagrams over text",
        )
        intake_p.write_text(body, encoding="utf-8")
        form = parse_intake_md(intake_p)
        assert "John prefers diagrams" in form.pi_preferences

    def test_free_form_captured(self, tmp_path: Path) -> None:
        intake_p = tmp_path / "i.md"
        body = _build_md(
            topic="T",
            goals_block="- [x] Understand a literature field\n",
            audiences_block="- [x] Yourself (personal notes)\n",
            free_form_text="This is a side project for fun.",
        )
        intake_p.write_text(body, encoding="utf-8")
        form = parse_intake_md(intake_p)
        assert "side project for fun" in form.free_form


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


class TestRoundTrip:
    def test_form_to_markdown_back_to_form(self, tmp_path: Path) -> None:
        original = IntakeForm(
            topic="CODEX cellular neighborhoods in PDAC",
            goals=["understand_literature", "build_journal_club_deck"],
            audiences=["pi", "journal_club"],
            have=["pdfs", "wet_lab_data"],
            exclusions={"exclude_preprints": True, "min_year": 2015},
            style=["hedged"],
            pi_preferences="John likes author-year",
            deadlines=["weekly"],
            free_form="High-priority project for Q2",
        )
        md_text = original.to_markdown()
        intake_p = tmp_path / "round.md"
        intake_p.write_text(md_text, encoding="utf-8")

        reloaded = parse_intake_md(intake_p)
        assert reloaded.topic == original.topic
        assert set(reloaded.goals) == set(original.goals)
        assert set(reloaded.audiences) == set(original.audiences)
        assert set(reloaded.have) == set(original.have)
        assert "hedged" in reloaded.style
        assert "John likes author-year" in reloaded.pi_preferences
        assert "weekly" in reloaded.deadlines
        assert "Q2" in reloaded.free_form

    def test_schema_round_trips(self, tmp_path: Path) -> None:
        form = IntakeForm(
            topic="X",
            goals=["understand_literature"],
            audiences=["self"],
        )
        md_text = form.to_markdown()
        assert INTAKE_SCHEMA in md_text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_md(
    *,
    topic: str = "",
    goals_block: str = "- [ ] Understand a literature field\n",
    audiences_block: str = "- [ ] Yourself (personal notes)\n",
    pi_text: str = "",
    free_form_text: str = "",
) -> str:
    """Build a custom intake markdown for testing."""
    return f"""---
template: project_intake
schema: vaultlab-intake/v1
---

# Project intake — test

## 1. Topic (required)

YOUR ANSWER: {topic}

## 2. Goal (required)

{goals_block}

## 3. Audience (required)

{audiences_block}

## 4. What you already have

- [ ] Nothing — vaultlab starts from scratch

## 5. What you don't want

- [ ] Skip non-English papers

## 6. Style / voice

- [ ] No preference

## 7. PI preferences (if relevant)

YOUR ANSWER: {pi_text}

## 8. Deadlines

- [ ] One-shot — output delivered ASAP, no follow-up

## 9. Anything else

YOUR ANSWER: {free_form_text}
"""


def _minimal_filled(
    *,
    topic: str = "",
    goal_checked: bool = False,
    audience_checked: bool = False,
) -> str:
    goal_mark = "x" if goal_checked else " "
    aud_mark = "x" if audience_checked else " "
    return _build_md(
        topic=topic,
        goals_block=f"- [{goal_mark}] Understand a literature field\n",
        audiences_block=f"- [{aud_mark}] Yourself (personal notes)\n",
    )
