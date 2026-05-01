"""Tests for the numeric-rubric ensemble aggregation module.

The critical design test: a 4-vs-1 disagreement must NOT be silently
averaged out. The mean alone hides the dissent; the ensemble score
must surface both mean AND spread so the synthesizer can investigate.
"""

from __future__ import annotations

from vaultlab.research.rubric import (
    DEFAULT_METHODS_RUBRIC,
    RubricItem,
    RubricScore,
    aggregate_rubric_scores,
    rubric_section_for_prompt,
)


# ---------------------------------------------------------------------------
# Default rubric structure
# ---------------------------------------------------------------------------


def test_default_rubric_has_nine_items():
    assert len(DEFAULT_METHODS_RUBRIC) == 9
    ids = {item.id for item in DEFAULT_METHODS_RUBRIC}
    # Lifted-from-AI-Scientist core
    assert "originality" in ids
    assert "soundness" in ids
    assert "significance" in ids
    assert "presentation" in ids
    assert "contribution" in ids
    assert "overall" in ids
    # Vaultlab-specific
    assert "provenance" in ids
    assert "novelty_vs_prior_work" in ids
    assert "claim_evidence_fit" in ids


def test_default_rubric_uses_5_point_scale():
    for item in DEFAULT_METHODS_RUBRIC:
        assert item.min_score == 1
        assert item.max_score == 5


# ---------------------------------------------------------------------------
# Aggregation — basic shape
# ---------------------------------------------------------------------------


def test_aggregate_handles_empty_scores_list():
    result = aggregate_rubric_scores([])
    assert result.n_critics == 0
    assert result.dissent_flagged == []
    # Each rubric item present but with empty stats
    for item in DEFAULT_METHODS_RUBRIC:
        stats = result.per_item[item.id]
        assert stats["mean"] is None
        assert stats["all_scores"] == []


def test_aggregate_records_critic_count():
    scores = [
        RubricScore("c1", {"originality": 4, "soundness": 4}),
        RubricScore("c2", {"originality": 4, "soundness": 5}),
        RubricScore("c3", {"originality": 4, "soundness": 4}),
    ]
    result = aggregate_rubric_scores(scores)
    assert result.n_critics == 3


def test_aggregate_preserves_per_critic_scores():
    """The aggregate keeps the original per-critic scores so the
    synthesizer can drill into a dissenter's rationale."""
    scores = [
        RubricScore("c1", {"originality": 4}, rationale="solid"),
        RubricScore("c2", {"originality": 1}, rationale="fatal flaw"),
    ]
    result = aggregate_rubric_scores(scores)
    assert len(result.per_critic) == 2
    assert any(s.rationale == "fatal flaw" for s in result.per_critic)


# ---------------------------------------------------------------------------
# THE CRITICAL TEST — 4-vs-1 disagreement must surface
# ---------------------------------------------------------------------------


def test_anti_pattern_guard_4_vs_1_disagreement_surfaces_dissent():
    """If 4 of 5 critics say 'soundness 4' and 1 says 'soundness 1',
    the aggregate must show:
    * The mean (3.4) so the synthesizer sees the central tendency
    * The spread (3) so the synthesizer ALSO sees that one critic
      strongly disagreed
    * The item flagged in dissent_flagged
    * All 5 individual scores preserved

    This is exactly the failure mode AI-Scientist's perform_review.py
    has — they collapse to int-mean and lose the dissent. Vaultlab's
    aggregate refuses to do that.
    """
    scores = [
        RubricScore(f"c{i}", {"soundness": 4}) for i in range(4)
    ] + [
        RubricScore("c5_dissenter", {"soundness": 1}, rationale="fatal flaw"),
    ]
    result = aggregate_rubric_scores(scores)

    soundness = result.per_item["soundness"]
    # Mean is 3.4, NOT 4 — but more importantly, mean alone isn't the answer
    assert 3.0 < soundness["mean"] <= 3.5
    # Spread captures the disagreement
    assert soundness["spread"] == 3  # 4 - 1
    assert soundness["min"] == 1
    assert soundness["max"] == 4
    # All raw scores preserved
    assert sorted(soundness["all_scores"]) == [1, 4, 4, 4, 4]
    # Dissent flagged
    assert "soundness" in result.dissent_flagged


def test_aggregate_no_dissent_flag_when_consensus():
    """When all critics agree, dissent_flagged is empty."""
    scores = [RubricScore(f"c{i}", {"soundness": 4}) for i in range(5)]
    result = aggregate_rubric_scores(scores)
    assert result.dissent_flagged == []
    assert result.per_item["soundness"]["spread"] == 0


def test_aggregate_dissent_threshold_is_configurable():
    """Spread of exactly 1 is below default threshold; spread of 2 is at threshold."""
    # Spread = 1 (3 vs 4) — below default threshold of 2 → no dissent flag
    scores_close = [
        RubricScore("c1", {"originality": 3}),
        RubricScore("c2", {"originality": 4}),
    ]
    assert "originality" not in aggregate_rubric_scores(scores_close).dissent_flagged

    # Spread = 2 (2 vs 4) — at default threshold → flagged
    scores_diff = [
        RubricScore("c1", {"originality": 2}),
        RubricScore("c2", {"originality": 4}),
    ]
    assert "originality" in aggregate_rubric_scores(scores_diff).dissent_flagged

    # Custom threshold = 3 — spread of 2 not flagged
    assert "originality" not in aggregate_rubric_scores(
        scores_diff, dissent_threshold=3
    ).dissent_flagged


# ---------------------------------------------------------------------------
# Robustness
# ---------------------------------------------------------------------------


def test_aggregate_skips_invalid_score_types():
    scores = [
        RubricScore("c1", {"originality": 4}),
        RubricScore("c2", {"originality": "not a number"}),  # type: ignore[dict-item]
        RubricScore("c3", {"originality": 5}),
    ]
    result = aggregate_rubric_scores(scores)
    # Bad value silently skipped; valid ones aggregated
    assert sorted(result.per_item["originality"]["all_scores"]) == [4, 5]


def test_aggregate_handles_partial_scores():
    """Critics can skip items they're not qualified to score."""
    scores = [
        RubricScore("c1", {"originality": 4, "soundness": 5}),
        RubricScore("c2", {"originality": 3}),  # skipped soundness
        RubricScore("c3", {"soundness": 4}),  # skipped originality
    ]
    result = aggregate_rubric_scores(scores)
    assert result.per_item["originality"]["all_scores"] == [4, 3]
    assert result.per_item["soundness"]["all_scores"] == [5, 4]


def test_aggregate_works_with_custom_rubric():
    """A caller can pass their own rubric instead of the default."""
    custom = (
        RubricItem("clarity", "Clarity", "is it clear", 1, 5),
        RubricItem("rigor", "Rigor", "is it rigorous", 1, 5),
    )
    scores = [
        RubricScore("c1", {"clarity": 4, "rigor": 5}),
        RubricScore("c2", {"clarity": 5, "rigor": 5}),
    ]
    result = aggregate_rubric_scores(scores, rubric=custom)
    # Only the custom rubric's items are present
    assert set(result.per_item.keys()) == {"clarity", "rigor"}


# ---------------------------------------------------------------------------
# Prompt fragment
# ---------------------------------------------------------------------------


def test_rubric_section_for_prompt_includes_each_item():
    text = rubric_section_for_prompt()
    for item in DEFAULT_METHODS_RUBRIC:
        assert item.id in text
        # Title appears too
        assert item.title in text


def test_rubric_section_for_prompt_emphasizes_honest_dissent():
    """The prompt fragment must instruct critics not to calibrate to consensus."""
    text = rubric_section_for_prompt()
    # The anti-conformity instruction is there
    assert "Honest dissent" in text or "honest dissent" in text
    assert "do NOT calibrate" in text


def test_rubric_section_for_prompt_returns_json_template():
    """Prompt includes a JSON template the critic should match."""
    text = rubric_section_for_prompt()
    assert '"scores"' in text
    assert '"rationale"' in text
