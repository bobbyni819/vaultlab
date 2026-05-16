"""Visual design directions HTML — Thariq's HTML-effectiveness pattern #2.

Renders 3-4 design directions side-by-side with palette swatches and
optional layout previews — used by figure-contract draft mode (and any
other "pick one of N visual directions before plotting" workflow) to
present archetype layouts before any plotting code is written.

Pattern source: Thariq Shihipar's HTML-effectiveness gallery (#2,
"Visual Design Directions"). Use cases inside vaultlab:

- ``vaultlab.figures.contract_html`` (planned) — figure-contract
  draft preview showing 2-4 candidate panel layouts.
- Slide-template direction sheets — pick a colour palette + layout
  for a deck before generating.
- KB note design notes — record "we considered A/B/C, chose A
  because…" as a renderable HTML artifact.

Composition follows the same shape as
:mod:`vaultlab.report.approaches_compare_html` and
:mod:`vaultlab.report.flowchart_html`: ``build_<name>`` returns a
complete HTML string; ``write_<name>`` writes to disk plus AGENTS.md
Red Line #2 provenance sidecars.

No new primitives are introduced — every visual element comes from
:mod:`vaultlab.report._components` plus the trusted-HTML
``inline_svg_preview`` escape hatch.
"""

from __future__ import annotations

import html as _html
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vaultlab.report import _components as c
from vaultlab.report.html import render_report


# ---------------------------------------------------------------------------
# Public dataclasses


@dataclass
class DesignOption:
    """One candidate design direction.

    Attributes
    ----------
    name:
        Human-readable label, e.g. ``"NMI Pastel"``.
    rationale:
        One-line "why this fits" — rendered under the name.
    swatch_colors:
        Ordered list of CSS colour strings (``"#a8d8ea"`` or
        ``"rgb(...)"`` etc.). Rendered as an inline SVG colour strip.
    archetype:
        Optional archetype tag, e.g. ``"discovery"``, ``"methods"``,
        ``"dataset"``, ``"clinical"``. Empty hides the chip.
    inline_svg_preview:
        Optional inline SVG snippet for a layout preview (trusted
        HTML — *not* escaped). Empty omits the preview block.
    """

    name: str
    rationale: str
    swatch_colors: list[str] = field(default_factory=list)
    archetype: str = ""
    inline_svg_preview: str = ""


@dataclass
class VisualDesigns:
    """Top-level structured input for the visual-designs view.

    Attributes
    ----------
    title:
        Sheet title, e.g. ``"Figure 2 design directions"``.
    context:
        Preamble paragraph explaining what is being chosen. Empty
        omits the TL;DR box.
    options:
        Ordered list of :class:`DesignOption` candidates. Renders as
        a responsive ``card_grid``.
    """

    title: str
    context: str = ""
    options: list[DesignOption] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal helpers


_COLOR_RE = re.compile(r"^[#a-zA-Z0-9_(),.% \-]+$")


def _safe(text: Any) -> str:
    return _html.escape(str(text or ""))


def _safe_color(color: str) -> str:
    """Validate a CSS colour value to keep it out of attribute-injection paths.

    Any value that fails the conservative regex falls back to ``#cccccc``.
    """
    color = (color or "").strip()
    if _COLOR_RE.match(color):
        return color
    return "#cccccc"


def _swatch_svg(colors: list[str]) -> str:
    """Render an inline SVG colour strip for a palette.

    Returns an empty string if no colours were supplied — callers can
    test for that before composing the block.
    """
    if not colors:
        return ""
    n = len(colors)
    cell = 40
    height = 36
    width = n * cell
    parts = [
        f'<svg viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" '
        f'xmlns="http://www.w3.org/2000/svg" '
        f'role="img" aria-label="palette swatches">'
    ]
    for i, raw in enumerate(colors):
        fill = _safe_color(raw)
        parts.append(
            f'<rect x="{i * cell}" y="0" width="{cell}" height="{height}" '
            f'fill="{fill}"/>'
        )
    parts.append("</svg>")
    return "".join(parts)


def _swatch_labels(colors: list[str]) -> str:
    """Inline tag list of the literal colour strings (so values are visible)."""
    if not colors:
        return ""
    pills = "".join(
        f'<code style="background:var(--bg-soft);padding:1px 6px;'
        f"border-radius:3px;font-size:11px;color:var(--ink-soft);"
        f'margin-right:4px;">{_safe(col)}</code>'
        for col in colors
    )
    return (
        '<div style="margin-top:6px;font-size:12px;color:var(--muted);'
        'word-break:break-all;">'
        f"{pills}</div>"
    )


def _option_body(opt: DesignOption) -> str:
    parts: list[str] = []
    if opt.rationale:
        parts.append(
            f'<p style="margin:0 0 8px;color:var(--ink-soft);font-size:13px;">'
            f"{_safe(opt.rationale)}</p>"
        )
    swatch = _swatch_svg(opt.swatch_colors)
    if swatch:
        parts.append(
            '<div style="margin:8px 0;border:1px solid var(--line);'
            'border-radius:4px;overflow:hidden;background:var(--bg-soft);'
            'display:inline-block;">'
            f"{swatch}</div>"
        )
    parts.append(_swatch_labels(opt.swatch_colors))
    if opt.inline_svg_preview:
        parts.append(
            '<div style="margin-top:10px;padding:8px;'
            'background:var(--bg-soft);border:1px solid var(--line);'
            'border-radius:4px;">'
            f"{opt.inline_svg_preview}</div>"
        )
    return "".join(parts)


def _option_card(opt: DesignOption) -> str:
    badges: list[tuple[str, str]] = []
    if opt.archetype:
        badges.append((opt.archetype, "neutral"))
    return c.severity_card(
        opt.name,
        body=_option_body(opt),
        severity="neutral",
        badges=badges or None,
    )


# ---------------------------------------------------------------------------
# Public API


def build_visual_designs_html(designs: VisualDesigns) -> str:
    """Compose the visual-designs HTML as a self-contained string.

    Section order: optional context TL;DR + header chips, responsive
    card grid (one card per design option). Empty inputs degrade
    gracefully — zero options still produces a well-formed placeholder.
    """
    report_title = designs.title or "Visual design directions"
    n = len(designs.options)

    header_chips = [
        c.status_chip(
            f"{n} direction" + ("s" if n != 1 else ""),
            "neutral",
        ),
    ]
    archetypes = sorted({o.archetype for o in designs.options if o.archetype})
    for arch in archetypes:
        header_chips.append(c.status_chip(arch, "neutral"))

    sections: list[str] = []

    intro_parts: list[str] = []
    if designs.context:
        intro_parts.append(c.tldr_box(designs.context, label="Context"))
    intro_parts.append(
        f'<div style="margin:14px 0;">{"".join(header_chips)}</div>'
    )
    sections.append(c.section(None, *intro_parts))

    if designs.options:
        cards = [_option_card(o) for o in designs.options]
        sections.append(c.section("Directions", c.card_grid(cards, min_width=280)))
    else:
        sections.append(
            c.section(
                "Directions",
                '<p style="color:var(--muted);">No design options supplied.</p>',
            )
        )

    return render_report(
        title=report_title,
        eyebrow="vaultlab · visual designs",
        subtitle=f"{n} direction" + ("s" if n != 1 else ""),
        meta="Palette + layout swatches · figure-contract draft mode",
        sections=sections,
    )


def write_visual_designs_html(
    designs: VisualDesigns,
    output_path: Path | str,
) -> Path:
    """Render and write the visual-designs HTML to ``output_path``.

    Also writes AGENTS.md Red Line #2 sidecars (``.provenance.json`` +
    ``.method.md``) next to the output via
    :func:`vaultlab.provenance.write_receipts`. Best-effort — a failure
    to write receipts does not block the HTML.

    Returns the resolved output Path.
    """
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(build_visual_designs_html(designs), encoding="utf-8")

    try:
        from vaultlab.provenance import ProvenanceRecord, write_receipts

        record = ProvenanceRecord(
            generated_by="vaultlab.report.visual_designs_html",
            kind="visual_designs_html",
            inputs=[],
            params={
                "title": designs.title,
                "option_count": len(designs.options),
                "archetype_count": len(
                    {o.archetype for o in designs.options if o.archetype}
                ),
                "swatch_total": sum(
                    len(o.swatch_colors) for o in designs.options
                ),
                "has_inline_preview": any(
                    bool(o.inline_svg_preview) for o in designs.options
                ),
            },
        )
        write_receipts(str(p), record)
    except Exception:  # pragma: no cover — defensive
        import logging

        logging.getLogger(__name__).exception(
            "write_receipts failed for visual-designs %s", p
        )

    return p


__all__ = [
    "DesignOption",
    "VisualDesigns",
    "build_visual_designs_html",
    "write_visual_designs_html",
]
