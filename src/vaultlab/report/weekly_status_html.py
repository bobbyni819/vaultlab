"""Weekly-status HTML consumer — Thariq's HTML-effectiveness pattern #16.

Consumer #7 of ``vaultlab.report``. Renders a :class:`WeeklyStatusReport`
(a small structured input) as a single-file HTML status update — header
chips with the week label + project, TL;DR, metric cards, shipped /
in-flight / blocker grids, and a carryover list for next week.

Pattern source: ``docs/html-pattern-coverage.md`` (#16, top-fit for
biology research workflows where Bobby writes a state doc every few
days). Composition follows the same shape as :mod:`vaultlab.slides.
audit_html` and :mod:`vaultlab.kb.dossier_html`: a small ``build_*_html``
function composes existing primitives from
:mod:`vaultlab.report._components` and a ``write_*`` companion calls
:func:`vaultlab.provenance.write_receipts` to satisfy AGENTS.md Red Line
#2 ("every output writes provenance").
"""

from __future__ import annotations

import html as _html
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vaultlab.report import components as c
from vaultlab.report import render_report


# ---------------------------------------------------------------------------
# Public dataclass


@dataclass
class WeeklyStatusReport:
    """Structured input for the weekly-status HTML view.

    All string fields are caller-supplied free-form text; the renderer
    HTML-escapes them before composing the report. Empty lists / dicts
    cause their respective sections to be omitted.

    Attributes
    ----------
    week_label:
        Human-readable label, e.g. ``"Week of 2026-05-15"``.
    project:
        Project name (a chip in the header band).
    tldr:
        One-paragraph headline summary, rendered in a TL;DR box.
    shipped:
        Pairs of ``(item_title, item_description)`` for work that
        landed this week. Rendered as ``severity_card`` (level=good)
        items in a ``card_grid``.
    in_flight:
        Pairs of ``(item_title, item_description)`` for in-progress
        work. Rendered as ``severity_card`` (level=warn) items.
    blockers:
        Pairs of ``(blocker_title, blocker_description)`` for stuck
        items. Rendered as ``severity_card`` (level=bad) items.
    carryover_next_week:
        Bullet list of next-week priorities.
    metrics:
        Mapping of metric name to formatted value (e.g.
        ``{"commits": "12", "tests": "1734 passing"}``). Each metric
        becomes a card in the metrics card-grid.
    """

    week_label: str
    project: str
    tldr: str
    shipped: list[tuple[str, str]] = field(default_factory=list)
    in_flight: list[tuple[str, str]] = field(default_factory=list)
    blockers: list[tuple[str, str]] = field(default_factory=list)
    carryover_next_week: list[str] = field(default_factory=list)
    metrics: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Internal helpers


def _safe(text: Any) -> str:
    return _html.escape(str(text or ""))


def _item_cards(items: list[tuple[str, str]], severity: str) -> list[str]:
    """Render a list of (title, description) pairs as severity cards."""
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
    """Render the metrics dict as a row of neutral cards.

    Each metric card foregrounds the value (large) with the metric
    name underneath in muted text, matching the "stat tile" idiom used
    elsewhere in vaultlab reports.
    """
    cards: list[str] = []
    for name, value in metrics.items():
        body = (
            f'<div style="font-size:24px;font-weight:600;line-height:1.2;">'
            f"{_safe(value)}</div>"
        )
        cards.append(c.severity_card(name, body=body, severity="neutral"))
    return cards


def _carryover_block(items: list[str]) -> str:
    """Render the carryover list as a tight bulleted block."""
    if not items:
        return ""
    li_html = "".join(f"<li>{_safe(i)}</li>" for i in items)
    return (
        '<ul style="margin:6px 0 0;padding-left:22px;color:var(--ink-soft);'
        f'font-size:14px;">{li_html}</ul>'
    )


# ---------------------------------------------------------------------------
# Public API


def build_weekly_status_html(report: WeeklyStatusReport) -> str:
    """Compose the weekly-status report as a self-contained HTML string.

    Uses :mod:`vaultlab.report` primitives (``tldr_box``, ``card_grid``,
    ``severity_card``, ``status_chip``, ``section``). Returns the rendered
    HTML string ready to write to disk.

    Empty sections (no shipped items, no metrics, no blockers, no
    carryover) are silently omitted so the report stays readable on
    quiet weeks.
    """
    report_title = f"{report.project} — {report.week_label}"

    # Header chips: week label + project + counts
    header_chips = [
        c.status_chip(report.project, "neutral"),
        c.status_chip(report.week_label, "neutral"),
    ]
    if report.shipped:
        header_chips.append(
            c.status_chip(
                f"{len(report.shipped)} shipped",
                "good",
            )
        )
    if report.in_flight:
        header_chips.append(
            c.status_chip(
                f"{len(report.in_flight)} in flight",
                "warn",
            )
        )
    if report.blockers:
        header_chips.append(
            c.status_chip(
                f"{len(report.blockers)} blocker"
                + ("s" if len(report.blockers) != 1 else ""),
                "bad",
            )
        )

    sections: list[str] = []

    # TL;DR + chip band
    sections.append(
        c.section(
            None,
            c.tldr_box(report.tldr),
            f'<div style="margin:14px 0;">{"".join(header_chips)}</div>',
        )
    )

    # Metrics row
    if report.metrics:
        sections.append(
            c.section(
                "Metrics",
                c.card_grid(_metric_cards(report.metrics), min_width=180),
            )
        )

    # Shipped this week
    if report.shipped:
        sections.append(
            c.section(
                "Shipped this week",
                c.card_grid(_item_cards(report.shipped, "good")),
            )
        )

    # In flight
    if report.in_flight:
        sections.append(
            c.section(
                "In flight",
                c.card_grid(_item_cards(report.in_flight, "warn")),
            )
        )

    # Blockers
    if report.blockers:
        sections.append(
            c.section(
                "Blockers",
                c.card_grid(_item_cards(report.blockers, "bad")),
            )
        )

    # Carryover
    if report.carryover_next_week:
        sections.append(
            c.section(
                "Carryover for next week",
                _carryover_block(report.carryover_next_week),
            )
        )

    return render_report(
        title=report_title,
        eyebrow=f"vaultlab · weekly status · {report.project}",
        meta=f"{_safe(report.week_label)}",
        sections=sections,
    )


def write_weekly_status_html(
    report: WeeklyStatusReport,
    output_path: Path | str,
) -> Path:
    """Render the weekly-status report and write it to ``output_path``.

    Also writes the AGENTS.md Red Line #2 sidecars (``.provenance.json``
    and ``.method.md``) next to the output via
    :func:`vaultlab.provenance.write_receipts`. Provenance is best-effort
    metadata — a failure to write receipts does not prevent the HTML
    from being produced.

    Returns the resolved output Path.
    """
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(build_weekly_status_html(report), encoding="utf-8")

    # Provenance receipts (Red Line #2). Best-effort: never gate the
    # actual HTML write on the sidecar succeeding.
    try:
        from vaultlab.provenance import ProvenanceRecord, write_receipts

        record = ProvenanceRecord(
            generated_by="vaultlab.report.weekly_status_html",
            kind="weekly_status_html",
            inputs=[],  # no source files for this consumer
            params={
                "project": report.project,
                "week_label": report.week_label,
                "shipped_count": len(report.shipped),
                "in_flight_count": len(report.in_flight),
                "blocker_count": len(report.blockers),
                "carryover_count": len(report.carryover_next_week),
                "metric_count": len(report.metrics),
            },
        )
        write_receipts(str(p), record)
    except Exception:  # pragma: no cover — defensive
        # Mirror the pattern in vaultlab.slides.deck: don't let a
        # provenance hiccup tank the user-visible artifact.
        import logging

        logging.getLogger(__name__).exception(
            "write_receipts failed for weekly-status %s", p
        )

    return p


__all__ = [
    "WeeklyStatusReport",
    "build_weekly_status_html",
    "write_weekly_status_html",
]
