"""SVG figure sheet HTML — Thariq's pattern #11.

Renders a standalone schematic library — N inline-SVG diagrams, each
with a label, description, copy-SVG button, and a related-concepts
cross-ref list. The "physics textbook back-cover figure sheet" view.

Pattern source: Thariq Shihipar's HTML-effectiveness gallery (#11,
"SVG Figure Sheet"). Use cases inside vaultlab:

- Architecture diagrams in ``docs/`` (single page collecting every
  ``vaultlab.*`` schematic).
- KB schematic appendix for a dossier (paste the architecture
  pictures next to the wiki concepts they reference).
- Multi-diagram research-pipeline overview (one HTML, every flow).

The copy-SVG affordance reuses the ``severity_card`` ``actions=``
hook, which already wires up a ``data-copy`` click handler in
:mod:`vaultlab.report._js`. The diagram framing — small viewport,
fixed aspect, soft border — matches the look used by
:func:`vaultlab.report.components.svg_arg_graph`.

No new primitives are introduced. ``svg_source`` is treated as
trusted HTML and inlined verbatim, exactly as ``svg_arg_graph``
already does for its own SVG markup.
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
class Schematic:
    """One inline-SVG schematic.

    Attributes
    ----------
    label:
        Human-readable label, e.g. ``"Crosstalk pipeline"``.
    description:
        Paragraph describing what the schematic depicts.
    svg_source:
        Inline SVG markup (trusted HTML — *not* escaped). Should be a
        complete ``<svg>...</svg>`` element with a viewBox so it
        scales inside the diagram frame.
    related_concepts:
        Free-form list of wiki-style cross-refs. Rendered as
        ``status_chip`` pills underneath the diagram.
    """

    label: str
    description: str = ""
    svg_source: str = ""
    related_concepts: list[str] = field(default_factory=list)


@dataclass
class FigureSheet:
    """Top-level structured input for the figure-sheet view.

    Attributes
    ----------
    title:
        Sheet title, e.g. ``"vaultlab architecture schematics"``.
    intro:
        Preamble paragraph rendered in a TL;DR box. Empty omits the
        intro section.
    schematics:
        Ordered list of :class:`Schematic` items. Each gets its own
        framed block with a copy-SVG button + concept list.
    """

    title: str
    intro: str = ""
    schematics: list[Schematic] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal helpers


def _safe(text: Any) -> str:
    return _html.escape(str(text or ""))


def _related_pills(concepts: list[str]) -> str:
    if not concepts:
        return ""
    chips = "".join(c.status_chip(name, "neutral") for name in concepts)
    return (
        '<div style="margin-top:10px;">'
        '<div style="font-size:11px;font-weight:600;color:var(--ink-soft);'
        'text-transform:uppercase;letter-spacing:0.04em;margin-bottom:4px;">'
        "Related concepts</div>"
        f"{chips}</div>"
    )


def _diagram_block(s: Schematic) -> str:
    """Framed SVG block + description + copy button + concept chips."""
    parts: list[str] = []
    parts.append(
        f'<h3 style="margin:0 0 6px;font-size:16px;">{_safe(s.label)}</h3>'
    )
    if s.description:
        parts.append(
            f'<p style="margin:0 0 10px;color:var(--ink-soft);font-size:13px;">'
            f"{_safe(s.description)}</p>"
        )
    # Inline SVG container.
    if s.svg_source:
        parts.append(
            '<div class="vl-graph" '
            'style="padding:8px;background:var(--bg-soft);'
            'border:1px solid var(--line);border-radius:4px;overflow:auto;">'
            f"{s.svg_source}</div>"
        )
    else:
        parts.append(
            '<p style="color:var(--muted);font-size:12px;">'
            "No SVG source supplied.</p>"
        )
    # Copy-SVG button reuses the standard data-copy click handler.
    if s.svg_source:
        # Escape the SVG source for use as an HTML attribute value.
        copy_attr = _html.escape(s.svg_source, quote=True)
        parts.append(
            '<div class="actions" style="margin-top:8px;">'
            f'<button data-copy="{copy_attr}">Copy SVG</button>'
            "</div>"
        )
    parts.append(_related_pills(s.related_concepts))
    return (
        '<article style="margin:16px 0;padding:14px;border:1px solid var(--line);'
        'border-radius:6px;background:var(--bg);">'
        f"{''.join(parts)}</article>"
    )


# ---------------------------------------------------------------------------
# Public API


def build_svg_figure_sheet_html(sheet: FigureSheet) -> str:
    """Compose the figure-sheet HTML as a self-contained string.

    Section order: optional intro TL;DR + header chips, then one
    framed diagram block per schematic. Empty inputs degrade
    gracefully — zero schematics still produces a well-formed
    placeholder document.
    """
    report_title = sheet.title or "Figure sheet"
    n = len(sheet.schematics)
    concept_total = sum(len(s.related_concepts) for s in sheet.schematics)

    header_chips = [
        c.status_chip(
            f"{n} schematic" + ("s" if n != 1 else ""),
            "neutral",
        ),
    ]
    if concept_total:
        header_chips.append(
            c.status_chip(
                f"{concept_total} concept ref"
                + ("s" if concept_total != 1 else ""),
                "neutral",
            )
        )

    sections: list[str] = []

    intro_parts: list[str] = []
    if sheet.intro:
        intro_parts.append(c.tldr_box(sheet.intro))
    intro_parts.append(
        f'<div style="margin:14px 0;">{"".join(header_chips)}</div>'
    )
    sections.append(c.section(None, *intro_parts))

    if sheet.schematics:
        blocks = "".join(_diagram_block(s) for s in sheet.schematics)
        sections.append(c.section("Schematics", blocks))
    else:
        sections.append(
            c.section(
                "Schematics",
                '<p style="color:var(--muted);">No schematics supplied.</p>',
            )
        )

    return render_report(
        title=report_title,
        eyebrow="vaultlab · figure sheet",
        subtitle=f"{n} schematic" + ("s" if n != 1 else ""),
        meta="Copyable inline-SVG schematic library",
        sections=sections,
    )


def write_svg_figure_sheet_html(
    sheet: FigureSheet,
    output_path: Path | str,
) -> Path:
    """Render and write the figure-sheet HTML to ``output_path``.

    Also writes AGENTS.md Red Line #2 sidecars (``.provenance.json`` +
    ``.method.md``) next to the output via
    :func:`vaultlab.provenance.write_receipts`. Best-effort — a failure
    to write receipts does not block the HTML.

    Returns the resolved output Path.
    """
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(build_svg_figure_sheet_html(sheet), encoding="utf-8")

    try:
        from vaultlab.provenance import ProvenanceRecord, write_receipts

        record = ProvenanceRecord(
            generated_by="vaultlab.report.svg_figure_sheet_html",
            kind="svg_figure_sheet_html",
            inputs=[],
            params={
                "title": sheet.title,
                "schematic_count": len(sheet.schematics),
                "concept_ref_total": sum(
                    len(s.related_concepts) for s in sheet.schematics
                ),
                "has_svg_total": sum(
                    1 for s in sheet.schematics if s.svg_source
                ),
            },
        )
        write_receipts(str(p), record)
    except Exception:  # pragma: no cover — defensive
        import logging

        logging.getLogger(__name__).exception(
            "write_receipts failed for figure-sheet %s", p
        )

    return p


__all__ = [
    "FigureSheet",
    "Schematic",
    "build_svg_figure_sheet_html",
    "write_svg_figure_sheet_html",
]
