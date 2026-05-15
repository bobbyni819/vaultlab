"""Incident-timeline HTML consumer — Thariq's pattern #17.

Renders a structured incident / pipeline-run-postmortem report as a
single-file HTML document. Composes existing primitives from
:mod:`vaultlab.report._components`:

- :func:`timeline` (minute-by-minute event list)
- :func:`tabbed_block` (timeline vs raw log excerpts vs followup
  checklist)
- :func:`status_chip` (severity badges per entry)
- :func:`tldr_box` (headline summary + resolution status)

Pattern source: ``docs/html-pattern-coverage.md`` (#17 "Incident
Timeline"). Use cases inside vaultlab:

- Pipeline-run postmortems (e.g. lit-arc partial-failure reports).
- ``/goodnight`` overnight failure reports.
- ``research-pipeline`` self-correction loop summaries when a phase had
  to be retried.

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
from datetime import datetime
from pathlib import Path
from typing import Any

from vaultlab.report import _components as c
from vaultlab.report.html import render_report


# ---------------------------------------------------------------------------
# Public dataclasses


@dataclass
class TimelineEntry:
    """One event in the incident timeline.

    Attributes
    ----------
    timestamp:
        ``datetime`` when the event occurred.
    event:
        Short human description, e.g. ``"Crosstalk round 2 stuck"``.
    severity:
        One of ``"info"`` / ``"warning"`` / ``"error"`` / ``"resolution"``.
        Drives the per-entry status chip colour:

        - ``info`` → neutral
        - ``warning`` → warn (yellow)
        - ``error`` → bad (red)
        - ``resolution`` → good (green)
    log_excerpt:
        Optional raw log lines. Rendered in the "Log excerpts" tab as a
        ``<pre>`` block. Empty for entries with no captured log.
    """

    timestamp: datetime
    event: str
    severity: str = "info"  # "info" | "warning" | "error" | "resolution"
    log_excerpt: str = ""


@dataclass
class IncidentChecklist:
    """One followup checklist item.

    Attributes
    ----------
    item:
        Free-form description of the followup action.
    done:
        Whether the item has been completed.
    """

    item: str
    done: bool = False


@dataclass
class IncidentReport:
    """Top-level structured input for the incident-timeline view.

    Attributes
    ----------
    title:
        Headline, e.g.
        ``"Lit-arc pipeline run, 2026-05-12, partial failure"``.
    summary:
        Paragraph summary rendered in the TL;DR box.
    started:
        ``datetime`` when the incident began.
    resolved:
        ``datetime`` when the incident was resolved, or ``None`` if
        still open. Drives the "OPEN" vs "RESOLVED" header chip.
    entries:
        Ordered list of :class:`TimelineEntry` events. The renderer
        preserves the supplied order (callers typically sort by
        ``timestamp``).
    followup_checklist:
        Optional list of :class:`IncidentChecklist` followup items.
        Empty omits the section.
    """

    title: str
    summary: str
    started: datetime
    resolved: datetime | None = None
    entries: list[TimelineEntry] = field(default_factory=list)
    followup_checklist: list[IncidentChecklist] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal helpers


_SEVERITY_LEVEL = {
    "info": "neutral",
    "warning": "warn",
    "error": "bad",
    "resolution": "good",
}


def _safe(text: Any) -> str:
    return _html.escape(str(text or ""))


def _fmt_ts(ts: datetime) -> str:
    """Format a timestamp for the timeline ``ts`` column."""
    return ts.strftime("%Y-%m-%d %H:%M:%S")


def _duration_str(start: datetime, end: datetime) -> str:
    """Human-readable duration between two timestamps."""
    delta = end - start
    total_seconds = int(delta.total_seconds())
    if total_seconds < 0:
        total_seconds = 0
    if total_seconds < 60:
        return f"{total_seconds}s"
    if total_seconds < 3600:
        return f"{total_seconds // 60}m{total_seconds % 60:02d}s"
    hours, rem = divmod(total_seconds, 3600)
    minutes = rem // 60
    return f"{hours}h{minutes:02d}m"


def _entry_to_timeline_tuple(entry: TimelineEntry) -> tuple[str, str, str]:
    """Convert a :class:`TimelineEntry` to the (ts, label, body) tuple
    expected by :func:`vaultlab.report._components.timeline`.

    The label embeds a severity chip; the body is the event description
    (and a short log preview when present — full text lives in the
    "Log excerpts" tab).
    """
    sev = _SEVERITY_LEVEL.get(entry.severity, "neutral")
    label = f"{c.status_chip(entry.severity, sev)}"  # type: ignore[arg-type]
    body_parts: list[str] = [
        f'<p style="margin:0 0 6px;color:var(--ink);font-size:14px;">'
        f"{_safe(entry.event)}</p>"
    ]
    if entry.log_excerpt:
        # Short preview only — full excerpt goes to the dedicated tab.
        preview = entry.log_excerpt.strip().splitlines()[0] if entry.log_excerpt else ""
        body_parts.append(
            '<div style="font-size:11px;color:var(--muted);font-style:italic;">'
            f"log: {_safe(preview)}"
            "</div>"
        )
    return (_fmt_ts(entry.timestamp), label, "".join(body_parts))


def _log_excerpt_block(entries: list[TimelineEntry]) -> str:
    """Render the per-entry log excerpts as a stacked ``<pre>`` list."""
    blocks: list[str] = []
    for entry in entries:
        if not entry.log_excerpt:
            continue
        blocks.append(
            '<div style="margin:8px 0;">'
            f'<div style="font-size:12px;color:var(--muted);">'
            f"{_safe(_fmt_ts(entry.timestamp))} · {_safe(entry.event)}"
            "</div>"
            '<pre style="margin:4px 0 0;padding:8px 10px;background:var(--bg-soft);'
            "border-radius:4px;font-size:12px;color:var(--ink-soft);"
            'white-space:pre-wrap;">'
            f"{_safe(entry.log_excerpt)}"
            "</pre>"
            "</div>"
        )
    if not blocks:
        return (
            '<p style="margin:0;color:var(--muted);">'
            "No log excerpts attached.</p>"
        )
    return "".join(blocks)


def _checklist_block(items: list[IncidentChecklist]) -> str:
    """Render the followup checklist as labeled rows."""
    if not items:
        return ""
    rows: list[str] = []
    for ci in items:
        chip = c.status_chip("done" if ci.done else "open", "good" if ci.done else "warn")
        rows.append(
            '<li style="margin:6px 0;display:flex;gap:8px;align-items:center;">'
            f"{chip}<span>{_safe(ci.item)}</span></li>"
        )
    return (
        '<ul style="margin:6px 0 0;padding:0;list-style:none;font-size:14px;'
        f'color:var(--ink-soft);">{"".join(rows)}</ul>'
    )


# ---------------------------------------------------------------------------
# Public API


def build_incident_timeline_html(report: IncidentReport) -> str:
    """Compose the incident-timeline HTML as a self-contained string.

    Section order: TL;DR + header chips (status, duration, severity
    counts), tabbed block (Timeline / Log excerpts / Followups), then
    the followup checklist as a flat fallback when no logs exist.
    Empty ``entries`` still produces a well-formed document with an
    explicit empty-state placeholder.
    """
    report_title = report.title or "Incident report"

    # Status + duration chips
    status_label = "RESOLVED" if report.resolved else "OPEN"
    status_level = "good" if report.resolved else "bad"
    duration_label = _duration_str(
        report.started,
        report.resolved or report.started,
    )
    header_chips: list[str] = [
        c.status_chip(status_label, status_level),  # type: ignore[arg-type]
        c.status_chip(f"duration: {duration_label}", "neutral"),
    ]
    # Severity counts
    counts: dict[str, int] = {}
    for entry in report.entries:
        counts[entry.severity] = counts.get(entry.severity, 0) + 1
    for sev_name in ("error", "warning", "info", "resolution"):
        if counts.get(sev_name):
            header_chips.append(
                c.status_chip(
                    f"{counts[sev_name]} {sev_name}",
                    _SEVERITY_LEVEL.get(sev_name, "neutral"),  # type: ignore[arg-type]
                )
            )

    sections: list[str] = []

    # TL;DR + chip band
    intro_parts: list[str] = [
        c.tldr_box(report.summary or "No summary."),
        f'<div style="margin:14px 0;">{"".join(header_chips)}</div>',
        '<div style="font-size:12px;color:var(--muted);">'
        f"Started {_safe(_fmt_ts(report.started))}"
        + (
            f" · resolved {_safe(_fmt_ts(report.resolved))}"
            if report.resolved
            else " · still open"
        )
        + "</div>",
    ]
    sections.append(c.section(None, *intro_parts))

    # Tabbed timeline / logs / followups block
    tabs: dict[str, str] = {}
    if report.entries:
        events = [_entry_to_timeline_tuple(e) for e in report.entries]
        tabs["Timeline"] = c.timeline(events)
    else:
        tabs["Timeline"] = (
            '<p style="color:var(--muted);">No timeline entries recorded.</p>'
        )

    any_logs = any(e.log_excerpt for e in report.entries)
    if any_logs:
        tabs["Log excerpts"] = _log_excerpt_block(report.entries)

    if report.followup_checklist:
        tabs["Followups"] = _checklist_block(report.followup_checklist)

    sections.append(c.section("Incident detail", c.tabbed_block(tabs)))

    return render_report(
        title=report_title,
        eyebrow="vaultlab · incident timeline",
        subtitle=status_label.title(),
        meta=f"started {_safe(_fmt_ts(report.started))} · {len(report.entries)} entries",
        sections=sections,
    )


def write_incident_timeline_html(
    report: IncidentReport,
    output_path: Path | str,
) -> Path:
    """Render and write the incident-timeline HTML to ``output_path``.

    Also writes AGENTS.md Red Line #2 sidecars (``.provenance.json`` +
    ``.method.md``) next to the output via
    :func:`vaultlab.provenance.write_receipts`. Best-effort — a failure
    to write receipts does not block the HTML write.

    Returns the resolved output Path.
    """
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(build_incident_timeline_html(report), encoding="utf-8")

    try:
        from vaultlab.provenance import ProvenanceRecord, write_receipts

        counts: dict[str, int] = {}
        for entry in report.entries:
            counts[entry.severity] = counts.get(entry.severity, 0) + 1
        record = ProvenanceRecord(
            generated_by="vaultlab.report.incident_timeline_html",
            kind="incident_timeline_html",
            inputs=[],
            params={
                "title": report.title,
                "started": report.started.isoformat(),
                "resolved": report.resolved.isoformat() if report.resolved else "",
                "entry_count": len(report.entries),
                "followup_count": len(report.followup_checklist),
                "severity_counts": counts,
                "any_log_excerpts": any(e.log_excerpt for e in report.entries),
            },
        )
        write_receipts(str(p), record)
    except Exception:  # pragma: no cover — defensive
        import logging

        logging.getLogger(__name__).exception(
            "write_receipts failed for incident-timeline %s", p
        )

    return p


__all__ = [
    "IncidentChecklist",
    "IncidentReport",
    "TimelineEntry",
    "build_incident_timeline_html",
    "write_incident_timeline_html",
]
