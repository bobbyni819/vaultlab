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
    "GoalRisk",
    "NeedsHumanApproval",
    "TaskKind",
    "classify_goal_risk",
    "rounds_for_spread",
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
    critic_spread: float | None = None
    """Disagreement among critic outputs from a PRIOR run (0..1), or None.
    Consumed by :func:`rounds_for_spread` for adaptive round sizing."""


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


# ---------------------------------------------------------------------------
# Safety gate (AI co-scientist input safety review — Gottweis et al. 2025)
# ---------------------------------------------------------------------------


class NeedsHumanApproval(Exception):
    """Raised when a goal must pause for explicit human approval before work
    proceeds. Carries the human-readable reason. Orchestrators catch this and
    surface a blocking confirmation rather than proceeding autonomously — see
    CLAUDE.md "Where blocking confirmation IS still required"."""


GoalRisk = Literal["low", "needs_human", "block"]

# HIGH-PRECISION phrase lists (multi-word where possible) so the screen does NOT
# false-positive on ordinary biology. A goal about "gene deletion", "gain-of-
# function mutations", "patient cohorts", or a "phi coefficient" stays "low".
# The screen catches only unambiguous harm-intent or explicit outward actions;
# it is high-precision / low-recall ON PURPOSE — the real safety net is human
# oversight, which this supplements, never replaces.
_BLOCK_PHRASES: tuple[str, ...] = (
    "bioweapon",
    "biological weapon",
    "bioterror",
    "nerve agent",
    "chemical weapon",
    "mass-casualty weapon",
    "mass casualty weapon",
    "build a bomb",
)
_NEEDS_HUMAN_PHRASES: tuple[str, ...] = (
    "submit to journal",
    "submit the manuscript",
    "send an email",
    "send email",
    "post to twitter",
    "post to x.com",
    "post publicly",
    "deploy to production",
    "issue a press release",
)


def classify_goal_risk(goal: str) -> GoalRisk:
    """Coarse, deterministic safety pre-screen of a research goal.

    A safety input-review lifted from the AI co-scientist (Gottweis et al.
    2025): an unsafe goal is flagged on input rather than pursued. This is a
    phrase scan — NO LLM, no prompt file — so it is fast, auditable, and cannot
    itself hallucinate.

    Returns:

    - ``"block"`` — unambiguous harm-intent (bioweapon / mass-casualty); the
      caller should refuse, e.g. ``raise NeedsHumanApproval(reason)``.
    - ``"needs_human"`` — an explicit outward / irreversible action named in the
      goal (submit, send, deploy, press release); requires human go-ahead.
    - ``"low"`` — no known red flag; proceed.

    HIGH-PRECISION BY DESIGN: ordinary biology ("gene deletion", "gain of
    function", "patient cohort", "phi coefficient") stays ``"low"``. A ``"low"``
    result is the ABSENCE of a known red flag, not a safety guarantee — human
    oversight remains the ground truth.
    """
    text = (goal or "").lower()
    if any(phrase in text for phrase in _BLOCK_PHRASES):
        return "block"
    if any(phrase in text for phrase in _NEEDS_HUMAN_PHRASES):
        return "needs_human"
    return "low"


# ---------------------------------------------------------------------------
# Adaptive allocation (AI co-scientist — spend compute where critics disagree)
# ---------------------------------------------------------------------------


def rounds_for_spread(
    ctx: CrosstalkContext, base_rounds: int = 3, max_rounds: int = 5
) -> int:
    """Recommend a round count from observed critic spread (adaptive allocation).

    Returns ``base_rounds`` when there is no spread signal
    (``ctx.critic_spread is None``) — fully backward-compatible. When spread is
    high (critics still finding new objections), scales linearly up toward
    ``max_rounds`` so contested findings get more debate; low spread stays at
    base. Pure + deterministic. Callers pass the ``critic_spread`` from a prior
    ``CrosstalkResult`` to size a follow-up run.

    (AI co-scientist: the Supervisor re-weights compute toward what is still
    productive — see INSPIRATIONS.md.)
    """
    spread = ctx.critic_spread
    if spread is None:
        return base_rounds
    extra = max(0.0, min(1.0, spread)) * (max_rounds - base_rounds)
    return min(max_rounds, base_rounds + round(extra))
