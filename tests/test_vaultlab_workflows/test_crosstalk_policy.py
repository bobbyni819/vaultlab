"""Tests for vaultlab.workflows.crosstalk_policy — invocation gate.

Covers the decision matrix for ``should_invoke(CrosstalkContext)``:
fire by default for synthesis tasks, skip for mechanical / extraction
tasks, and respect an explicit ``n_rounds_budget`` override.
"""

from __future__ import annotations

import pytest

from vaultlab.workflows.crosstalk_policy import (
    CrosstalkContext,
    skip_reason,
    should_invoke,
)


# ---------------------------------------------------------------------------
# Decision-by-task_kind matrix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "task_kind",
    [
        "synthesis",
        "manuscript_draft",
        "deep_think",
        "journal_club",
    ],
)
def test_synthesis_kinds_fire_by_default(task_kind: str) -> None:
    """Synthesis-class tasks fire by default."""
    ctx = CrosstalkContext(task_kind=task_kind)  # type: ignore[arg-type]
    assert should_invoke(ctx) is True
    assert skip_reason(ctx) is None


@pytest.mark.parametrize(
    "task_kind",
    [
        "mechanical",
        "extraction",
        "single_paper_summary",
        "audit_render",
    ],
)
def test_mechanical_kinds_skip_by_default(task_kind: str) -> None:
    """Mechanical / extraction / render tasks skip crosstalk by default."""
    ctx = CrosstalkContext(task_kind=task_kind)  # type: ignore[arg-type]
    assert should_invoke(ctx) is False
    reason = skip_reason(ctx)
    assert reason is not None
    assert task_kind in reason


# ---------------------------------------------------------------------------
# Budget override
# ---------------------------------------------------------------------------


def test_budget_override_fires_even_for_mechanical_kind() -> None:
    """When the caller has explicitly set n_rounds_budget > 0, fire."""
    ctx = CrosstalkContext(task_kind="mechanical", n_rounds_budget=2)
    assert should_invoke(ctx) is True
    assert skip_reason(ctx) is None


def test_budget_override_fires_for_unknown_kind() -> None:
    """Budget override beats every other rule, including unknown kinds."""
    ctx = CrosstalkContext(task_kind="extraction", n_rounds_budget=1)
    assert should_invoke(ctx) is True


def test_zero_budget_does_not_override() -> None:
    """n_rounds_budget=0 (the default) doesn't trigger the override."""
    ctx = CrosstalkContext(task_kind="mechanical", n_rounds_budget=0)
    assert should_invoke(ctx) is False


def test_negative_budget_does_not_override() -> None:
    """Defensive: a negative budget isn't an override."""
    ctx = CrosstalkContext(task_kind="mechanical", n_rounds_budget=-1)
    assert should_invoke(ctx) is False


# ---------------------------------------------------------------------------
# Forward-compat / safe default
# ---------------------------------------------------------------------------


def test_unknown_task_kind_defaults_to_fire() -> None:
    """A task_kind not in the known matrix defaults to firing (favor rigor)."""
    ctx = CrosstalkContext(task_kind="some_future_kind")  # type: ignore[arg-type]
    assert should_invoke(ctx) is True


def test_empty_context_defaults_to_fire() -> None:
    """An empty context (default task_kind) defaults to firing."""
    # The default task_kind is 'synthesis' which fires.
    ctx = CrosstalkContext(task_kind="synthesis")
    assert should_invoke(ctx) is True


# ---------------------------------------------------------------------------
# Context attributes
# ---------------------------------------------------------------------------


def test_context_default_attributes() -> None:
    """CrosstalkContext exposes the expected default fields."""
    ctx = CrosstalkContext(task_kind="synthesis")
    assert ctx.task_kind == "synthesis"
    assert ctx.n_evidence_sources == 0
    assert ctx.n_rounds_budget == 0
    assert ctx.has_human_review_after is False


def test_context_accepts_optional_fields() -> None:
    """Optional fields plumb through without affecting the decision matrix."""
    ctx = CrosstalkContext(
        task_kind="synthesis",
        n_evidence_sources=12,
        n_rounds_budget=0,
        has_human_review_after=True,
    )
    assert should_invoke(ctx) is True
    assert ctx.n_evidence_sources == 12


# ---------------------------------------------------------------------------
# skip_reason details
# ---------------------------------------------------------------------------


def test_skip_reason_returns_human_readable_string() -> None:
    """skip_reason() returns a short, human-readable string when skipping."""
    ctx = CrosstalkContext(task_kind="mechanical")
    reason = skip_reason(ctx)
    assert isinstance(reason, str)
    assert len(reason) > 0


def test_skip_reason_is_none_when_firing() -> None:
    """skip_reason() returns None when crosstalk would fire."""
    assert skip_reason(CrosstalkContext(task_kind="synthesis")) is None
    assert (
        skip_reason(CrosstalkContext(task_kind="mechanical", n_rounds_budget=2))
        is None
    )


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_policy_is_deterministic() -> None:
    """Same context → same decision, every call."""
    ctx = CrosstalkContext(task_kind="synthesis", n_evidence_sources=5)
    decisions = {should_invoke(ctx) for _ in range(20)}
    assert decisions == {True}

    ctx2 = CrosstalkContext(task_kind="mechanical")
    decisions2 = {should_invoke(ctx2) for _ in range(20)}
    assert decisions2 == {False}
