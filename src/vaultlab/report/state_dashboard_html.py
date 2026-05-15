"""Vaultlab state dashboard — HTML render of system-state-<date>.md + module map.

Composes three of Thariq's HTML-effectiveness patterns into a single
consumer (Pattern #16 Weekly Status + Pattern #6 Module Map + Pattern
#15 Concept Explainer):

- **Pattern #16 — Weekly Status header**: project chip, date, metrics,
  shipped / in-flight / blockers as severity card grids.
- **Pattern #6 — Module Map**: ``vaultlab.*`` package graph rendered
  with :func:`vaultlab.report.components.svg_arg_graph` from a list of
  ``(module_name, short_desc, downstream_modules)`` triples.
- **Pattern #15 — Concept Explainer** *(optional)*: an inline
  diagram panel for the active research arc / mechanism.

This is consumer #8 of :mod:`vaultlab.report` (after the v0.0.5 weekly-
status slice). Composition follows the same shape as
:mod:`vaultlab.slides.audit_html`, :mod:`vaultlab.kb.dossier_html`, and
:mod:`vaultlab.report.weekly_status_html`: ``build_<name>_html`` returns
a complete HTML string; ``write_<name>_html`` writes to disk and emits
AGENTS.md Red Line #2 provenance sidecars via
:func:`vaultlab.provenance.write_receipts`.

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
# Public dataclass


@dataclass
class StateDashboard:
    """Structured input for the state-dashboard HTML view.

    All string fields are caller-supplied free-form text; the renderer
    HTML-escapes them before composing the report. Empty lists / dicts
    cause their respective sections to be omitted gracefully.

    Attributes
    ----------
    project:
        Project name (a chip in the header band, e.g. ``"vaultlab"``).
    date:
        Human-readable date label, e.g. ``"2026-05-15"``.
    status_summary:
        One-paragraph headline summary, rendered in the TL;DR box.
    metrics:
        Mapping of metric name to formatted value, e.g.
        ``{"tests": "1734 passing", "modules": "11"}``. Each becomes
        a stat tile in the metrics card grid.
    shipped:
        Pairs of ``(item_title, item_description)`` for recent wins.
        Rendered as severity_card (severity=good) items in a card_grid.
    in_flight:
        Pairs of ``(item_title, item_description)`` for in-progress work.
        Rendered as severity_card (severity=warn) items.
    blockers:
        Pairs of ``(blocker_title, blocker_description)`` for stuck
        items. Rendered as severity_card (severity=bad) items.
    module_map:
        Triples of ``(module_name, short_desc, downstream_modules)``
        describing the package graph. Rendered via
        :func:`vaultlab.report.components.svg_arg_graph` plus a
        card_grid legend.
    concept_explainer:
        Optional dict describing an inline concept explainer panel
        (Pattern #15). Recognized keys: ``title`` (str), ``summary``
        (str), ``nodes`` (list of node dicts for ``svg_arg_graph``),
        ``edges`` (list of (from_id, to_id) tuples), ``hot_path``
        (optional list of node ids to highlight). When ``None``, the
        explainer section is omitted entirely.
    """

    project: str
    date: str
    status_summary: str
    metrics: dict[str, str] = field(default_factory=dict)
    shipped: list[tuple[str, str]] = field(default_factory=list)
    in_flight: list[tuple[str, str]] = field(default_factory=list)
    blockers: list[tuple[str, str]] = field(default_factory=list)
    module_map: list[tuple[str, str, list[str]]] = field(default_factory=list)
    concept_explainer: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Internal helpers


def _safe(text: Any) -> str:
    return _html.escape(str(text or ""))


def _item_cards(items: list[tuple[str, str]], severity: str) -> list[str]:
    """Render (title, description) pairs as severity cards."""
    cards: list[str] = []
    for title, description in items:
        body = (
            f'<p style="margin:0;color:var(--ink-soft);font-size:13px;">'
            f"{_safe(description)}</p>"
            if description
            else ""
        )
        cards.append(c.severity_card(title, body=body, severity=severity))
    return cards


def _metric_cards(metrics: dict[str, str]) -> list[str]:
    """Render the metrics dict as stat tiles."""
    cards: list[str] = []
    for name, value in metrics.items():
        body = (
            f'<div style="font-size:24px;font-weight:600;line-height:1.2;">'
            f"{_safe(value)}</div>"
        )
        cards.append(c.severity_card(name, body=body, severity="neutral"))
    return cards


def _layout_module_nodes(
    module_map: list[tuple[str, str, list[str]]],
    *,
    width: int,
    height: int,
) -> tuple[list[dict[str, Any]], list[tuple[str, str]]]:
    """Place modules on a simple ring layout suitable for ``svg_arg_graph``.

    Returns (nodes, edges). Each node has the keys expected by
    ``svg_arg_graph``: ``id``, ``x``, ``y``, ``label``. Edges are
    pruned so they only reference declared modules.
    """
    import math

    n = len(module_map)
    if n == 0:
        return [], []

    cx, cy = width / 2, height / 2
    # Choose radius that leaves comfortable margin for node labels.
    radius = min(width, height) * 0.36
    nodes: list[dict[str, Any]] = []
    declared = {name for name, _, _ in module_map}
    for i, (name, _desc, _downstream) in enumerate(module_map):
        # Start at top, go clockwise, so single-node case sits at top.
        angle = -math.pi / 2 + (2 * math.pi * i / max(n, 1))
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        nodes.append(
            {
                "id": name,
                "x": round(x, 1),
                "y": round(y, 1),
                "label": name.split(".")[-1],  # short label
                "r": 30,
            }
        )

    edges: list[tuple[str, str]] = []
    for name, _desc, downstream in module_map:
        for target in downstream:
            if target in declared and target != name:
                edges.append((name, target))
    return nodes, edges


def _module_legend_cards(
    module_map: list[tuple[str, str, list[str]]],
) -> list[str]:
    """Render a small legend of (module, description) pairs as neutral cards."""
    cards: list[str] = []
    for name, desc, downstream in module_map:
        downstream_chips = (
            "".join(c.status_chip(d, "neutral") for d in downstream)
            if downstream
            else ""
        )
        body = (
            f'<p style="margin:0 0 6px;color:var(--ink-soft);font-size:13px;">'
            f"{_safe(desc)}</p>"
            f'<div style="margin-top:4px;">{downstream_chips}</div>'
        )
        cards.append(c.severity_card(name, body=body, severity="neutral"))
    return cards


def _explainer_section(explainer: dict[str, Any]) -> str:
    """Render the optional concept-explainer panel (Pattern #15).

    Accepts the keys documented on :class:`StateDashboard.concept_explainer`.
    Missing keys degrade gracefully — the panel renders whatever is present.
    """
    title = str(explainer.get("title") or "Concept explainer")
    summary = str(explainer.get("summary") or "")
    nodes = explainer.get("nodes") or []
    edges = explainer.get("edges") or []
    hot_path = explainer.get("hot_path") or None

    parts: list[str] = []
    if summary:
        parts.append(c.tldr_box(summary, label="In one line"))
    if nodes:
        # svg_arg_graph expects list[tuple[str, str]] for edges; coerce if list.
        coerced_edges = [tuple(e) for e in edges if len(e) == 2]
        parts.append(
            c.svg_arg_graph(
                nodes,
                coerced_edges,
                hot_path=hot_path,
                width=560,
                height=320,
            )
        )
    if not parts:
        # Nothing to render — return an empty section silently.
        return ""
    return c.section(title, *parts)


# ---------------------------------------------------------------------------
# Public API


def build_state_dashboard_html(state: StateDashboard) -> str:
    """Compose the state dashboard HTML.

    Returns a self-contained HTML string. Sections render in the order:
    TL;DR + header chips, metrics, shipped, in-flight, blockers, module
    map (graph + legend), optional concept explainer. Empty sections
    are silently omitted.
    """
    report_title = f"{state.project} — state dashboard"

    # Header chips
    header_chips = [
        c.status_chip(state.project, "neutral"),
        c.status_chip(state.date, "neutral"),
    ]
    if state.shipped:
        header_chips.append(c.status_chip(f"{len(state.shipped)} shipped", "good"))
    if state.in_flight:
        header_chips.append(
            c.status_chip(f"{len(state.in_flight)} in flight", "warn")
        )
    if state.blockers:
        plural = "s" if len(state.blockers) != 1 else ""
        header_chips.append(
            c.status_chip(f"{len(state.blockers)} blocker{plural}", "bad")
        )
    if state.module_map:
        header_chips.append(
            c.status_chip(f"{len(state.module_map)} modules", "neutral")
        )

    sections: list[str] = []

    # TL;DR + chip band
    sections.append(
        c.section(
            None,
            c.tldr_box(state.status_summary),
            f'<div style="margin:14px 0;">{"".join(header_chips)}</div>',
        )
    )

    # Metrics
    if state.metrics:
        sections.append(
            c.section(
                "Metrics",
                c.card_grid(_metric_cards(state.metrics), min_width=180),
            )
        )

    # Shipped
    if state.shipped:
        sections.append(
            c.section(
                "Shipped",
                c.card_grid(_item_cards(state.shipped, "good")),
            )
        )

    # In flight
    if state.in_flight:
        sections.append(
            c.section(
                "In flight",
                c.card_grid(_item_cards(state.in_flight, "warn")),
            )
        )

    # Blockers
    if state.blockers:
        sections.append(
            c.section(
                "Blockers",
                c.card_grid(_item_cards(state.blockers, "bad")),
            )
        )

    # Module map (Pattern #6)
    if state.module_map:
        width, height = 600, 360
        nodes, edges = _layout_module_nodes(
            state.module_map, width=width, height=height
        )
        sections.append(
            c.section(
                "Module map",
                c.svg_arg_graph(nodes, edges, width=width, height=height),
                c.card_grid(_module_legend_cards(state.module_map), min_width=220),
            )
        )

    # Concept explainer (Pattern #15)
    if state.concept_explainer:
        explainer_html = _explainer_section(state.concept_explainer)
        if explainer_html:
            sections.append(explainer_html)

    return render_report(
        title=report_title,
        eyebrow=f"vaultlab · state dashboard · {state.project}",
        subtitle=state.date,
        meta=f"{_safe(state.date)}",
        sections=sections,
    )


def write_state_dashboard_html(
    state: StateDashboard,
    output_path: Path | str,
) -> Path:
    """Render the state dashboard and write it to ``output_path``.

    Also writes AGENTS.md Red Line #2 sidecars (``.provenance.json``
    and ``.method.md``) next to the output via
    :func:`vaultlab.provenance.write_receipts`. Provenance is best-effort
    — a failure to write receipts does not prevent the HTML from being
    produced.

    Returns the resolved output Path.
    """
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(build_state_dashboard_html(state), encoding="utf-8")

    try:
        from vaultlab.provenance import ProvenanceRecord, write_receipts

        record = ProvenanceRecord(
            generated_by="vaultlab.report.state_dashboard_html",
            kind="state_dashboard_html",
            inputs=[],
            params={
                "project": state.project,
                "date": state.date,
                "shipped_count": len(state.shipped),
                "in_flight_count": len(state.in_flight),
                "blocker_count": len(state.blockers),
                "metric_count": len(state.metrics),
                "module_count": len(state.module_map),
                "has_concept_explainer": state.concept_explainer is not None,
            },
        )
        write_receipts(str(p), record)
    except Exception:  # pragma: no cover — defensive
        import logging

        logging.getLogger(__name__).exception(
            "write_receipts failed for state-dashboard %s", p
        )

    return p


__all__ = [
    "StateDashboard",
    "build_state_dashboard_html",
    "write_state_dashboard_html",
]
