"""Crosstalk invocation policy (SPEC-E, sub-goal 2.4).

Decides whether the multi-agent crosstalk round-table fires for a given
task, or whether a single-pass call suffices. Saves tokens on mechanical
transforms; preserves rigor on synthesis tasks.

Rule of thumb
-------------

Fire by default for synthesis (cross-evidence reasoning, manuscript
drafting, deep-think, journal-club analysis). Skip for mechanical
(format conversion, simple extraction, single-paper summarization,
audit-output rendering).

The policy is intentionally a pure, deterministic function — no LLM
calls, no I/O. The decision and a human-readable ``skip_reason`` (when
applicable) become part of every crosstalk caller's provenance manifest
so audits can reconstruct why a given run was or wasn't a round-table.

The default ``task_kind`` of a fresh :class:`CrosstalkContext` is
``"synthesis"`` so a caller that omits the kind gets the safe-default
fire-it behaviour rather than silently skipping.

See ``crosstalk_policy.md`` (SKILL.md sidecar) for the full rationale
and call-site map.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

__all__ = [
    "FIRE_KINDS",
    "SKIP_KINDS",
    "CrosstalkContext",
    "TaskKind",
    "should_invoke",
    "skip_reason",
]


# ---------------------------------------------------------------------------
# Task kinds
# ---------------------------------------------------------------------------


TaskKind = Literal[
    # Fire-by-default kinds — cross-evidence reasoning that benefits from
    # an analyst/critic/synthesizer rotation.
    "synthesis",
    "manuscript_draft",
    "deep_think",
    "journal_club",
    # Skip-by-default kinds — mechanical transforms where a single pass
    # is sufficient and the round-table just burns tokens.
    "mechanical",
    "extraction",
    "single_paper_summary",
    "audit_render",
]

FIRE_KINDS: frozenset[str] = frozenset(
    {
        "synthesis",
        "manuscript_draft",
        "deep_think",
        "journal_club",
    }
)
"""TaskKinds that fire crosstalk by default."""

SKIP_KINDS: frozenset[str] = frozenset(
    {
        "mechanical",
        "extraction",
        "single_paper_summary",
        "audit_render",
    }
)
"""TaskKinds that skip crosstalk by default."""


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------


@dataclass
class CrosstalkContext:
    """Context for deciding whether to invoke crosstalk.

    Attributes:
        task_kind: One of :data:`TaskKind`. Defaults to ``"synthesis"``
            so an empty context fires (safe default: favor rigor).
        n_evidence_sources: How many distinct papers / datasets feed
            this task. Informational — not currently consulted by the
            policy but plumbed for future calibration.
        n_rounds_budget: When > 0, the caller has explicitly chosen to
            fire crosstalk with this many rounds; the policy honours
            the budget regardless of ``task_kind``. The default of 0
            means "no explicit budget — let the policy decide".
        has_human_review_after: When True, a human reviews the output
            afterwards, so crosstalk is less critical. Informational
            for now; reserved for future calibration of skip rules.
    """

    task_kind: TaskKind = "synthesis"
    n_evidence_sources: int = 0
    n_rounds_budget: int = 0
    has_human_review_after: bool = False


# ---------------------------------------------------------------------------
# Decision
# ---------------------------------------------------------------------------


def should_invoke(ctx: CrosstalkContext) -> bool:
    """Return True if the crosstalk round-table should fire.

    Policy rules, in order:

    1. If ``ctx.n_rounds_budget > 0`` the caller has explicitly set a
       budget → fire.
    2. ``task_kind`` in :data:`FIRE_KINDS` → fire.
    3. ``task_kind`` in :data:`SKIP_KINDS` → skip.
    4. Default to firing (favor rigor over cost — Bobby's
       ``feedback_pipeline_run_through_tier_b`` memory: crosstalk is
       part of the pipeline by default, not a gated luxury).

    The function is pure and deterministic — same input → same output.
    """
    if ctx.n_rounds_budget > 0:
        return True
    if ctx.task_kind in FIRE_KINDS:
        return True
    if ctx.task_kind in SKIP_KINDS:
        return False
    return True


def skip_reason(ctx: CrosstalkContext) -> str | None:
    """Return a human-readable skip reason, or ``None`` if firing.

    Mirrors :func:`should_invoke` — when ``should_invoke`` returns True
    this returns ``None``; otherwise it returns a short string suitable
    for embedding in a provenance manifest's
    ``params.crosstalk_skip_reason`` field.
    """
    if should_invoke(ctx):
        return None
    return f"task_kind={ctx.task_kind!r} is mechanical/extraction; single-pass suffices"
