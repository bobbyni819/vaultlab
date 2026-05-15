"""Three-approaches comparison HTML — Thariq's HTML-effectiveness pattern #1.

Renders an "Approach A / B / C" decision view as a single-file HTML
report — composes :func:`vaultlab.report.components.compare_panel` (for
two-way views) and :func:`vaultlab.report.components.card_grid` (for
three-or-more approaches) plus a decision-rationale TL;DR box.

Pattern source: Thariq Shihipar's HTML-effectiveness gallery (#1, "Three
Code Approaches"). Use cases inside vaultlab:

- SPEC-A/B/C/D/E/F dossier HTML output (the pending SPEC backlog calls
  for "approach A/B/C with trade-offs" presentation explicitly).
- Architecture decision records (ADRs) inside ``docs/`` or KB notes.
- ``/grill-me`` outputs that compare design directions before code.

Composition follows the same shape as
:mod:`vaultlab.report.weekly_status_html` and
:mod:`vaultlab.slides.audit_html`: ``build_<name>`` returns a complete
HTML string; ``write_<name>`` writes to disk plus AGENTS.md Red Line
#2 provenance sidecars.

No new primitives are introduced — every visual element comes from
:mod:`vaultlab.report._components`.
"""

from __future__ import annotations

import html as _html
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vaultlab.report import _components as c
from vaultlab.report.html import render_report


# ---------------------------------------------------------------------------
# Public dataclasses


@dataclass
class Approach:
    """One candidate approach in a decision matrix.

    Attributes
    ----------
    name:
        Human-readable label, e.g. ``"Approach A: Subagent dispatch"``.
    summary:
        One-paragraph description of what this approach does.
    pros:
        Bullet list of upsides.
    cons:
        Bullet list of downsides.
    estimated_effort:
        Free-form effort estimate, e.g. ``"4 hours"`` or ``"1 sprint"``.
        Empty string means unknown / not estimated.
    recommended:
        When True, this approach renders with the ``good`` severity
        accent and a ``"RECOMMENDED"`` chip — at most one approach
        should set this (the renderer does not enforce uniqueness).
    """

    name: str
    summary: str
    pros: list[str] = field(default_factory=list)
    cons: list[str] = field(default_factory=list)
    estimated_effort: str = ""
    recommended: bool = False


@dataclass
class ApproachesCompare:
    """Top-level decision view comparing N candidate approaches.

    Attributes
    ----------
    title:
        Decision title, e.g. ``"How to parallelize the plan"``.
    approaches:
        Ordered list of :class:`Approach` candidates. Two approaches
        render side-by-side via ``compare_panel``; three or more render
        as a responsive ``card_grid``.
    decision_rationale:
        Paragraph explaining why the recommendation won. Rendered in
        the closing TL;DR box. Empty string omits the section.
    context:
        Optional preamble paragraph explaining the problem being
        decided. Rendered above the approach grid.
    """

    title: str
    approaches: list[Approach] = field(default_factory=list)
    decision_rationale: str = ""
    context: str = ""


# ---------------------------------------------------------------------------
# Internal helpers


def _safe(text: Any) -> str:
    return _html.escape(str(text or ""))


def _bullet_block(items: list[str], *, label: str, accent: str) -> str:
    """Render a small labeled bullet block.

    ``accent`` is one of ``"good"`` / ``"bad"`` / ``"neutral"`` and
    controls the left-border colour via the same CSS vars that
    :func:`vaultlab.report.components.severity_card` uses.
    """
    if not items:
        return ""
    color_var = {"good": "var(--good)", "bad": "var(--bad)", "neutral": "var(--line)"}.get(
        accent, "var(--line)"
    )
    li_html = "".join(f"<li>{_safe(i)}</li>" for i in items)
    return (
        '<div style="margin:8px 0;padding:6px 10px;'
        f"border-left:3px solid {color_var};background:var(--bg-soft);"
        'border-radius:0 4px 4px 0;">'
        f'<div style="font-size:11px;font-weight:600;color:var(--ink-soft);'
        f'text-transform:uppercase;letter-spacing:0.04em;">{_safe(label)}</div>'
        f'<ul style="margin:4px 0 2px;padding-left:18px;font-size:13px;'
        f'color:var(--ink-soft);">{li_html}</ul>'
        "</div>"
    )


def _approach_body(app: Approach) -> str:
    """Render the inner body of an Approach card / pane.

    Used by both the two-way ``compare_panel`` and the N-way
    ``card_grid`` rendering paths so the visual layout stays
    consistent regardless of how many approaches there are.
    """
    parts: list[str] = []
    if app.summary:
        parts.append(
            f'<p style="margin:0 0 8px;color:var(--ink-soft);font-size:13px;">'
            f"{_safe(app.summary)}</p>"
        )
    parts.append(_bullet_block(app.pros, label="Pros", accent="good"))
    parts.append(_bullet_block(app.cons, label="Cons", accent="bad"))
    if app.estimated_effort:
        parts.append(
            '<div style="margin-top:6px;font-size:12px;color:var(--muted);">'
            f"<strong>Effort:</strong> {_safe(app.estimated_effort)}</div>"
        )
    return "".join(parts)


def _approach_card(app: Approach) -> str:
    """Render one approach as a severity_card (used in N-way card_grid view)."""
    severity: str | None = "good" if app.recommended else "neutral"
    badges: list[tuple[str, str]] = []
    if app.recommended:
        badges.append(("RECOMMENDED", "good"))
    if app.estimated_effort:
        badges.append((app.estimated_effort, "neutral"))
    return c.severity_card(
        app.name,
        body=_approach_body(app),
        severity=severity,
        badges=badges or None,
    )


# ---------------------------------------------------------------------------
# Public API


def build_approaches_compare_html(comp: ApproachesCompare) -> str:
    """Compose the approach-comparison HTML.

    Two approaches → side-by-side ``compare_panel``.
    Three or more → responsive ``card_grid``.
    Zero → an explicit empty-state placeholder.

    Returns a self-contained HTML string.
    """
    report_title = comp.title or "Approach comparison"
    n = len(comp.approaches)

    header_chips = [
        c.status_chip(f"{n} approach{'es' if n != 1 else ''}", "neutral"),
    ]
    recommended = next((a for a in comp.approaches if a.recommended), None)
    if recommended:
        header_chips.append(c.status_chip(f"Recommended: {recommended.name}", "good"))

    sections: list[str] = []

    # Context + header chip band
    context_parts: list[str] = []
    if comp.context:
        context_parts.append(c.tldr_box(comp.context, label="Context"))
    context_parts.append(
        f'<div style="margin:14px 0;">{"".join(header_chips)}</div>'
    )
    sections.append(c.section(None, *context_parts))

    # The approach grid
    if n == 0:
        sections.append(
            c.section(
                "Approaches",
                '<p style="color:var(--muted);">No approaches supplied.</p>',
            )
        )
    elif n == 2:
        left, right = comp.approaches
        left_label = left.name + (" (recommended)" if left.recommended else "")
        right_label = right.name + (" (recommended)" if right.recommended else "")
        sections.append(
            c.section(
                "Approaches",
                c.compare_panel(
                    left_label,
                    _approach_body(left),
                    right_label,
                    _approach_body(right),
                ),
            )
        )
    else:
        cards = [_approach_card(a) for a in comp.approaches]
        sections.append(
            c.section(
                "Approaches",
                c.card_grid(cards, min_width=300),
            )
        )

    # Decision rationale
    if comp.decision_rationale:
        sections.append(
            c.section(
                "Decision rationale",
                c.tldr_box(comp.decision_rationale, label="Why"),
            )
        )

    return render_report(
        title=report_title,
        eyebrow="vaultlab · approach comparison",
        subtitle=f"{n} approach{'es' if n != 1 else ''}",
        meta="SPEC-style decision matrix · trade-offs + recommendation",
        sections=sections,
    )


def write_approaches_compare_html(
    comp: ApproachesCompare,
    output_path: Path | str,
) -> Path:
    """Render and write the approach-comparison HTML to ``output_path``.

    Also emits AGENTS.md Red Line #2 provenance sidecars next to the
    output via :func:`vaultlab.provenance.write_receipts`. Best-effort
    — a failure to write receipts does not block the HTML.

    Returns the resolved output Path.
    """
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(build_approaches_compare_html(comp), encoding="utf-8")

    try:
        from vaultlab.provenance import ProvenanceRecord, write_receipts

        record = ProvenanceRecord(
            generated_by="vaultlab.report.approaches_compare_html",
            kind="approaches_compare",
            inputs=[],
            params={
                "title": comp.title,
                "approach_count": len(comp.approaches),
                "recommended": next(
                    (a.name for a in comp.approaches if a.recommended),
                    "",
                ),
                "has_rationale": bool(comp.decision_rationale),
            },
        )
        write_receipts(str(p), record)
    except Exception:  # pragma: no cover — defensive
        import logging

        logging.getLogger(__name__).exception(
            "write_receipts failed for approaches-compare %s", p
        )

    return p


__all__ = [
    "Approach",
    "ApproachesCompare",
    "build_approaches_compare_html",
    "write_approaches_compare_html",
]
