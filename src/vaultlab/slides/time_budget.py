"""Estimate per-slide speaking time + total deck duration.

Bobby's 2026-05-04 ask: each use-case template has a target duration
(prelim 35min talk, pitch 12min, JC 25min). The audit should know whether
the deck FITS its target so it warns the speaker before they're 12 slides
into a 10-minute slot.

Heuristics for default per-slide speaking time:

- title slide:           0.5 min
- text slide (≤4 bullets): 1.0 min + 0.3 per bullet
- text slide (>4 bullets): 1.5 min + 0.2 per bullet
- section_divider:       0.3 min (just a transition)
- figure slide:          1.5 min (figure walk-through + ~280-word script)
- multi_figure slide:    2.0 min (multiple panels to explain)
- two_figure_compare:    2.0 min
- quote slide:           0.5 min
- references:            0.5 min
- annotated_figure:      2.0 min (more click-builds to explain)

Override per-slide by setting ``"_estimated_minutes": <float>`` in the
slide_spec speaker_notes (already used by the prelim template).

API:

- :func:`estimate_slide_minutes(slide_spec)` → float
- :func:`estimate_deck_minutes(plan)` → float
- :func:`time_budget_audit(plan, target_minutes)` → :class:`TimeBudgetReport`
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


_DEFAULT_PER_TYPE_MINUTES = {
    "title": 0.5,
    "section_divider": 0.3,
    "figure": 1.5,
    "multi_figure": 2.0,
    "two_figure": 2.0,
    "annotated_figure": 2.0,
    "quote": 0.5,
    "references": 0.5,
}


def estimate_slide_minutes(slide_spec: dict[str, Any]) -> float:
    """Per-slide speaking-time estimate, in minutes."""
    notes = slide_spec.get("speaker_notes") or {}
    override = notes.get("_estimated_minutes") if isinstance(notes, dict) else None
    if override is not None:
        try:
            return float(override)
        except (ValueError, TypeError):
            pass

    stype = slide_spec.get("type", "text")
    if stype == "text":
        bullets = slide_spec.get("bullets") or []
        n = len(bullets)
        if n <= 4:
            return 1.0 + 0.3 * n
        return 1.5 + 0.2 * n

    return _DEFAULT_PER_TYPE_MINUTES.get(stype, 1.0)


def estimate_deck_minutes(plan: dict[str, Any]) -> float:
    """Total deck speaking-time estimate, in minutes."""
    slides = plan.get("slides") or []
    return sum(estimate_slide_minutes(s) for s in slides)


@dataclass
class TimeBudgetReport:
    """Result of a time-budget audit."""

    target_minutes: float
    estimated_minutes: float
    n_slides: int
    per_slide_minutes: list[float]
    severity: str  # "ok", "warn", "fail"

    @property
    def delta_minutes(self) -> float:
        return self.estimated_minutes - self.target_minutes

    @property
    def delta_pct(self) -> float:
        if self.target_minutes <= 0:
            return 0.0
        return self.delta_minutes / self.target_minutes * 100

    def to_markdown(self) -> str:
        sev_emoji = {"ok": "✅", "warn": "⚠️", "fail": "❌"}.get(self.severity, "?")
        lines = [
            f"### Time-budget audit",
            "",
            f"**Severity:** {sev_emoji} `{self.severity}`",
            "",
            f"- Target: **{self.target_minutes:.1f} min** ({self.n_slides} slides)",
            f"- Estimated: **{self.estimated_minutes:.1f} min**",
            f"- Delta: **{self.delta_minutes:+.1f} min** ({self.delta_pct:+.0f}%)",
            "",
        ]
        if self.severity != "ok":
            avg = self.estimated_minutes / max(1, self.n_slides)
            lines.append(f"_Average: {avg:.1f} min/slide. Trim or add slides to hit target._")
        return "\n".join(lines)


def time_budget_audit(
    plan: dict[str, Any],
    target_minutes: float | None = None,
    *,
    warn_pct: float = 10.0,
    fail_pct: float = 25.0,
) -> TimeBudgetReport:
    """Compare estimated speaking time vs target. Severity ok/warn/fail.

    ``target_minutes`` defaults to ``plan["_target_minutes"]`` if not given.
    Severity:
    - ok:   delta ≤ ``warn_pct`` (default 10%)
    - warn: delta ≤ ``fail_pct`` (default 25%)
    - fail: delta > fail_pct
    """
    if target_minutes is None:
        target_minutes = float(plan.get("_target_minutes", 0))

    slides = plan.get("slides") or []
    per_slide = [estimate_slide_minutes(s) for s in slides]
    estimated = sum(per_slide)
    n = len(slides)

    if target_minutes <= 0:
        # No target set — return ok with the estimate
        return TimeBudgetReport(
            target_minutes=0.0,
            estimated_minutes=estimated,
            n_slides=n,
            per_slide_minutes=per_slide,
            severity="ok",
        )

    delta_pct_abs = abs((estimated - target_minutes) / target_minutes * 100)
    if delta_pct_abs > fail_pct:
        sev = "fail"
    elif delta_pct_abs > warn_pct:
        sev = "warn"
    else:
        sev = "ok"

    return TimeBudgetReport(
        target_minutes=target_minutes,
        estimated_minutes=estimated,
        n_slides=n,
        per_slide_minutes=per_slide,
        severity=sev,
    )


__all__ = [
    "TimeBudgetReport",
    "estimate_deck_minutes",
    "estimate_slide_minutes",
    "time_budget_audit",
]
