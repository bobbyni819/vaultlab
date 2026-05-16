"""Component variants contact-sheet HTML — Thariq's pattern #8.

Renders a grid of component states / sizes / intents — the "library
contact sheet" for vaultlab's slide-layout inventory and any other
"here are all the variants of X" inventory output. Composes the
``card_grid`` primitive in dense mode, with optional tag-based grouping
so multi-axis inventories (theme × layout × state) stay scannable.

Pattern source: Thariq Shihipar's HTML-effectiveness gallery (#8,
"Component Variants"). Use cases inside vaultlab:

- Slide-layout inventory — every ``vaultlab.slides.layouts.*`` layout
  rendered with a preview at a glance.
- Report primitive showcase — every ``vaultlab.report._components.*``
  primitive demonstrated in one HTML page.
- Plot-style inventory — every figure style + its swatch.

Composition follows the same shape as
:mod:`vaultlab.report.visual_designs_html` and
:mod:`vaultlab.report.flowchart_html`: ``build_<name>`` returns a
complete HTML string; ``write_<name>`` writes to disk plus AGENTS.md
Red Line #2 provenance sidecars.

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
class ComponentVariant:
    """One row in the contact sheet.

    Attributes
    ----------
    name:
        Human-readable label, e.g. ``"Title slide — light"``.
    description:
        Short caption explaining the variant.
    preview_html:
        Optional inline HTML preview (trusted — *not* escaped).
        Use a small SVG, a thumbnail ``<img>``, or a styled
        ``<div>`` snippet.
    tags:
        Free-form tag list. The first tag drives grouping when
        :attr:`ComponentInventory.group_by_tag` is True.
    """

    name: str
    description: str = ""
    preview_html: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class ComponentInventory:
    """Top-level structured input for the component-variants view.

    Attributes
    ----------
    title:
        Inventory title, e.g. ``"vaultlab slide layouts"``.
    intro:
        Preamble paragraph rendered in a TL;DR box. Empty omits the
        intro section.
    variants:
        Ordered list of :class:`ComponentVariant` rows.
    group_by_tag:
        When True (the default), variants are grouped into sections
        keyed by their first tag (variants with no tag go to
        ``"untagged"``). When False, all variants render in one flat
        grid.
    """

    title: str
    intro: str = ""
    variants: list[ComponentVariant] = field(default_factory=list)
    group_by_tag: bool = True


# ---------------------------------------------------------------------------
# Internal helpers


def _safe(text: Any) -> str:
    return _html.escape(str(text or ""))


def _variant_body(v: ComponentVariant) -> str:
    parts: list[str] = []
    if v.preview_html:
        parts.append(
            '<div style="margin:0 0 8px;padding:6px;border:1px solid var(--line);'
            'border-radius:4px;background:var(--bg-soft);overflow:hidden;">'
            f"{v.preview_html}</div>"
        )
    if v.description:
        parts.append(
            f'<p style="margin:0;color:var(--ink-soft);font-size:13px;">'
            f"{_safe(v.description)}</p>"
        )
    if not parts:
        parts.append(
            '<p style="margin:0;color:var(--muted);font-size:12px;">'
            "No description.</p>"
        )
    return "".join(parts)


def _variant_card(v: ComponentVariant) -> str:
    badges: list[tuple[str, str]] = [(t, "neutral") for t in v.tags]
    return c.severity_card(
        v.name,
        body=_variant_body(v),
        severity="neutral",
        badges=badges or None,
    )


def _group_variants(
    variants: list[ComponentVariant],
) -> list[tuple[str, list[ComponentVariant]]]:
    """Group variants by their first tag, preserving first-seen order.

    Variants with no tag go to a single ``"untagged"`` group. The
    return order matches first appearance of each group in
    ``variants``.
    """
    order: list[str] = []
    buckets: dict[str, list[ComponentVariant]] = {}
    for v in variants:
        key = v.tags[0] if v.tags else "untagged"
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(v)
    return [(k, buckets[k]) for k in order]


# ---------------------------------------------------------------------------
# Public API


def build_component_variants_html(inventory: ComponentInventory) -> str:
    """Compose the component-variants HTML as a self-contained string.

    Section order: optional intro TL;DR + header chips, then either one
    grouped section per first-tag (when ``group_by_tag``) or one flat
    contact-sheet grid. Empty inputs degrade gracefully.
    """
    report_title = inventory.title or "Component variants"
    n = len(inventory.variants)

    tag_set = sorted({t for v in inventory.variants for t in v.tags})
    header_chips = [
        c.status_chip(
            f"{n} variant" + ("s" if n != 1 else ""),
            "neutral",
        ),
    ]
    if tag_set:
        header_chips.append(
            c.status_chip(
                f"{len(tag_set)} tag" + ("s" if len(tag_set) != 1 else ""),
                "neutral",
            )
        )

    sections: list[str] = []

    intro_parts: list[str] = []
    if inventory.intro:
        intro_parts.append(c.tldr_box(inventory.intro))
    intro_parts.append(
        f'<div style="margin:14px 0;">{"".join(header_chips)}</div>'
    )
    sections.append(c.section(None, *intro_parts))

    if not inventory.variants:
        sections.append(
            c.section(
                "Variants",
                '<p style="color:var(--muted);">No variants supplied.</p>',
            )
        )
    elif inventory.group_by_tag:
        for tag, group in _group_variants(inventory.variants):
            cards = [_variant_card(v) for v in group]
            sections.append(
                c.section(
                    tag,
                    c.card_grid(cards, min_width=240),
                )
            )
    else:
        cards = [_variant_card(v) for v in inventory.variants]
        sections.append(c.section("Variants", c.card_grid(cards, min_width=240)))

    return render_report(
        title=report_title,
        eyebrow="vaultlab · component variants",
        subtitle=f"{n} variant" + ("s" if n != 1 else ""),
        meta="Contact sheet · grouped by tag" if inventory.group_by_tag else "Contact sheet",
        sections=sections,
    )


def write_component_variants_html(
    inventory: ComponentInventory,
    output_path: Path | str,
) -> Path:
    """Render and write the component-variants HTML to ``output_path``.

    Also writes AGENTS.md Red Line #2 sidecars (``.provenance.json`` +
    ``.method.md``) next to the output via
    :func:`vaultlab.provenance.write_receipts`. Best-effort — a failure
    to write receipts does not block the HTML.

    Returns the resolved output Path.
    """
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(build_component_variants_html(inventory), encoding="utf-8")

    try:
        from vaultlab.provenance import ProvenanceRecord, write_receipts

        record = ProvenanceRecord(
            generated_by="vaultlab.report.component_variants_html",
            kind="component_variants_html",
            inputs=[],
            params={
                "title": inventory.title,
                "variant_count": len(inventory.variants),
                "tag_count": len(
                    {t for v in inventory.variants for t in v.tags}
                ),
                "group_by_tag": inventory.group_by_tag,
                "has_preview": any(
                    bool(v.preview_html) for v in inventory.variants
                ),
            },
        )
        write_receipts(str(p), record)
    except Exception:  # pragma: no cover — defensive
        import logging

        logging.getLogger(__name__).exception(
            "write_receipts failed for component-variants %s", p
        )

    return p


__all__ = [
    "ComponentInventory",
    "ComponentVariant",
    "build_component_variants_html",
    "write_component_variants_html",
]
