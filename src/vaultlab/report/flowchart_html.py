"""Annotated flowchart HTML consumer — Thariq's pattern #12.

Renders a sequence of pipeline / workflow steps as a single-file HTML
document with a clickable SVG flow diagram (top) and an expandable
per-step detail panel (bottom). Composes primitives from
:mod:`vaultlab.report._components`:

- :func:`svg_arg_graph` for the diagram
- :func:`collapsible_step` for per-step description / timing / failure
  modes
- :func:`status_chip` for typical-duration + failure-count badges
- :func:`tldr_box` for the optional headline summary

Pattern source: ``docs/html-pattern-coverage.md`` (#12 "Annotated
Flowchart"). Use cases inside vaultlab:

- ``research-pipeline`` phase explainer (Phase 1 → 7, with typical
  durations + known failure modes per phase).
- KB ingest pipeline visualization (CrossRef → PubMed → S2 → corpus).
- Lit-arc retrieval cascade (frontmatter → indexes → wikilinks → corpus).

Composition follows the same shape as
:mod:`vaultlab.report.weekly_status_html` and
:mod:`vaultlab.report.state_dashboard_html`: ``build_<name>`` returns the
HTML string; ``write_<name>`` writes to disk plus AGENTS.md Red Line #2
provenance sidecars via :func:`vaultlab.provenance.write_receipts`.

No new primitives are introduced.
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
class FlowStep:
    """One step in the annotated flowchart.

    Attributes
    ----------
    step_id:
        Stable identifier (used as the SVG node id + ``collapsible_step``
        anchor). Example: ``"phase-1-verify-data"``.
    label:
        Short human-readable label drawn inside the SVG node. Example:
        ``"Phase 1: Verify Data"``.
    description:
        Paragraph describing what the step does. Rendered inside the
        expanded detail panel.
    typical_duration:
        Free-form duration string, e.g. ``"~15 min"``. Empty hides the
        duration chip.
    failure_modes:
        Bullet list of known failure modes / common bugs. Empty hides
        the failure section in the expanded panel.
    successors:
        ``step_id`` values this step can flow to. Unknown successors
        (not declared anywhere in ``Flowchart.steps``) are silently
        dropped so partial graphs render gracefully.
    """

    step_id: str
    label: str
    description: str
    typical_duration: str = ""
    failure_modes: list[str] = field(default_factory=list)
    successors: list[str] = field(default_factory=list)


@dataclass
class Flowchart:
    """Top-level structured input for the flowchart view.

    Attributes
    ----------
    title:
        Chart title, e.g. ``"research-pipeline phases"``.
    steps:
        Ordered list of :class:`FlowStep` items. The order also drives
        the SVG x-layout (left → right).
    entry_step_id:
        Which step starts the flow. Highlighted in the SVG diagram via
        ``hot_path``. When the value is not in ``steps``, the renderer
        silently degrades to no highlight.
    description:
        Optional headline paragraph rendered in a TL;DR box.
    """

    title: str
    steps: list[FlowStep]
    entry_step_id: str
    description: str = ""


# ---------------------------------------------------------------------------
# Internal helpers


def _safe(text: Any) -> str:
    return _html.escape(str(text or ""))


def _layout_flow_nodes(
    steps: list[FlowStep],
    *,
    width: int,
    height: int,
) -> tuple[list[dict[str, Any]], list[tuple[str, str]]]:
    """Place steps on a left-to-right rank layout suitable for ``svg_arg_graph``.

    Returns ``(nodes, edges)``. Edges referencing unknown ``successors``
    are silently dropped (additive-state-aware rule).
    """
    n = len(steps)
    if n == 0:
        return [], []

    margin_x = 70
    usable_w = max(width - 2 * margin_x, 1)
    cy = height / 2
    nodes: list[dict[str, Any]] = []
    declared = {s.step_id for s in steps}
    for i, step in enumerate(steps):
        # Single node centers; multiple spread evenly across usable_w.
        if n == 1:
            x = width / 2
        else:
            x = margin_x + usable_w * i / (n - 1)
        nodes.append(
            {
                "id": step.step_id,
                "x": round(x, 1),
                "y": round(cy, 1),
                "label": step.label,
                "r": 36,
            }
        )

    edges: list[tuple[str, str]] = []
    for step in steps:
        for target in step.successors:
            if target in declared and target != step.step_id:
                edges.append((step.step_id, target))
    return nodes, edges


def _step_detail(step: FlowStep) -> str:
    """Render the body of one ``collapsible_step`` for a flow step."""
    parts: list[str] = []
    chips: list[str] = []
    if step.typical_duration:
        chips.append(c.status_chip(step.typical_duration, "neutral"))
    if step.failure_modes:
        chips.append(
            c.status_chip(
                f"{len(step.failure_modes)} failure mode"
                + ("s" if len(step.failure_modes) != 1 else ""),
                "warn",
            )
        )
    if chips:
        parts.append(
            f'<div style="margin-bottom:8px;">{"".join(chips)}</div>'
        )
    if step.description:
        parts.append(
            f'<p style="margin:0 0 8px;color:var(--ink-soft);font-size:14px;">'
            f"{_safe(step.description)}</p>"
        )
    if step.failure_modes:
        bullets = "".join(f"<li>{_safe(fm)}</li>" for fm in step.failure_modes)
        parts.append(
            '<div style="margin-top:8px;">'
            '<div style="font-size:11px;font-weight:600;color:var(--ink-soft);'
            'text-transform:uppercase;letter-spacing:0.04em;">Failure modes</div>'
            f'<ul style="margin:4px 0 0;padding-left:18px;font-size:13px;'
            f'color:var(--ink-soft);">{bullets}</ul>'
            "</div>"
        )
    if step.successors:
        chips_html = "".join(c.status_chip(s, "neutral") for s in step.successors)
        parts.append(
            '<div style="margin-top:8px;font-size:12px;color:var(--muted);">'
            f'Successors: {chips_html}</div>'
        )
    if not parts:
        parts.append(
            '<p style="margin:0;color:var(--muted);">No detail recorded.</p>'
        )
    return "".join(parts)


# ---------------------------------------------------------------------------
# Public API


def build_flowchart_html(chart: Flowchart) -> str:
    """Compose the flowchart HTML as a self-contained string.

    Section order: optional TL;DR + header chips, SVG diagram,
    per-step ``collapsible_step`` list. Empty inputs degrade
    gracefully — an empty ``steps`` list still produces a well-formed
    placeholder document.
    """
    report_title = chart.title or "Flowchart"
    n = len(chart.steps)

    declared = {s.step_id for s in chart.steps}
    hot_path = [chart.entry_step_id] if chart.entry_step_id in declared else None

    header_chips = [
        c.status_chip(
            f"{n} step" + ("s" if n != 1 else ""),
            "neutral",
        ),
    ]
    if chart.entry_step_id in declared:
        header_chips.append(
            c.status_chip(f"entry: {chart.entry_step_id}", "good")
        )
    fail_count = sum(len(s.failure_modes) for s in chart.steps)
    if fail_count:
        header_chips.append(
            c.status_chip(
                f"{fail_count} failure mode"
                + ("s" if fail_count != 1 else ""),
                "warn",
            )
        )

    sections: list[str] = []

    intro_parts: list[str] = []
    if chart.description:
        intro_parts.append(c.tldr_box(chart.description))
    intro_parts.append(
        f'<div style="margin:14px 0;">{"".join(header_chips)}</div>'
    )
    sections.append(c.section(None, *intro_parts))

    # SVG diagram
    if chart.steps:
        width, height = 720, 220
        nodes, edges = _layout_flow_nodes(
            chart.steps, width=width, height=height
        )
        sections.append(
            c.section(
                "Flow diagram",
                c.svg_arg_graph(
                    nodes,
                    edges,
                    hot_path=hot_path,
                    width=width,
                    height=height,
                ),
            )
        )
    else:
        sections.append(
            c.section(
                "Flow diagram",
                '<p style="color:var(--muted);">No steps supplied.</p>',
            )
        )

    # Per-step collapsible details
    if chart.steps:
        step_html = "".join(
            c.collapsible_step(s.label, _step_detail(s)) for s in chart.steps
        )
        sections.append(c.section("Step details", step_html))

    return render_report(
        title=report_title,
        eyebrow="vaultlab · flowchart",
        subtitle=f"{n} step" + ("s" if n != 1 else ""),
        meta=f"entry: {_safe(chart.entry_step_id)}"
        if chart.entry_step_id
        else None,
        sections=sections,
    )


def write_flowchart_html(
    chart: Flowchart,
    output_path: Path | str,
) -> Path:
    """Render and write the flowchart HTML to ``output_path``.

    Also writes AGENTS.md Red Line #2 sidecars (``.provenance.json`` +
    ``.method.md``) next to the output via
    :func:`vaultlab.provenance.write_receipts`. Best-effort — a failure
    to write receipts does not block the HTML.

    Returns the resolved output Path.
    """
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(build_flowchart_html(chart), encoding="utf-8")

    try:
        from vaultlab.provenance import ProvenanceRecord, write_receipts

        record = ProvenanceRecord(
            generated_by="vaultlab.report.flowchart_html",
            kind="flowchart_html",
            inputs=[],
            params={
                "title": chart.title,
                "step_count": len(chart.steps),
                "entry_step_id": chart.entry_step_id,
                "failure_mode_total": sum(
                    len(s.failure_modes) for s in chart.steps
                ),
                "edge_count": sum(
                    len(s.successors) for s in chart.steps
                ),
            },
        )
        write_receipts(str(p), record)
    except Exception:  # pragma: no cover — defensive
        import logging

        logging.getLogger(__name__).exception(
            "write_receipts failed for flowchart %s", p
        )

    return p


__all__ = [
    "FlowStep",
    "Flowchart",
    "build_flowchart_html",
    "write_flowchart_html",
]
