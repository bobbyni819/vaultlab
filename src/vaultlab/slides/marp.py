"""Marp markdown mirror for vaultlab.slides.

Lifted from ``bobby_slides._marp`` (bobby-tools, 2026-04). Renders a deck
plan dict (the same shape consumed by
:func:`vaultlab.slides.deck.build_from_plan`) to Marp-compatible markdown so
the same deck is editable in Obsidian or any markdown editor.

Marp reference: https://marp.app/
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from vaultlab.slides.notes import format_speaker_notes


def deck_plan_to_marp(plan: dict[str, Any]) -> str:
    """Convert a deck-plan dict to Marp markdown.

    Args:
        plan: a deck plan with keys ``"title"``, ``"author"``, ``"slides"``
            (list of slide dicts). See
            :func:`vaultlab.slides.deck.build_from_plan` for the schema.

    Returns:
        A Marp-formatted markdown string.
    """
    lines: list[str] = []

    lines.extend(
        [
            "---",
            "marp: true",
            "theme: default",
            "paginate: true",
            "size: 16:9",
            "---",
            "",
        ]
    )

    slides = plan.get("slides", [])
    for i, slide in enumerate(slides):
        if i > 0:
            lines.extend(["", "---", ""])
        lines.append(_render_slide(slide))

    return "\n".join(lines).rstrip() + "\n"


def write_marp(plan: dict[str, Any], output: Path | str) -> Path:
    """Render plan to Marp and write to disk. Returns the output path."""
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(deck_plan_to_marp(plan), encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# Slide-type renderers
# ---------------------------------------------------------------------------


def _render_slide(slide: dict[str, Any]) -> str:
    stype = slide.get("type", "text")
    handler = _RENDERERS.get(stype, _render_text)
    body = handler(slide)
    notes = slide.get("speaker_notes")
    if notes:
        formatted = format_speaker_notes(notes)
        body = body + "\n\n<!--\n" + formatted + "\n-->"
    return body


def _render_title(slide: dict[str, Any]) -> str:
    title = slide.get("title", "")
    subtitle = slide.get("subtitle", "")
    author = slide.get("author", "")
    parts = [f"# {title}"]
    if subtitle:
        parts.append(f"## {subtitle}")
    if author:
        parts.append(f"**{author}**")
    return "\n\n".join(parts)


def _render_section(slide: dict[str, Any]) -> str:
    return f"# {slide.get('title', '')}"


def _render_figure(slide: dict[str, Any]) -> str:
    parts: list[str] = []
    if slide.get("title"):
        parts.append(f"## {slide['title']}")
    img = slide.get("image_path", "")
    if img:
        parts.append(f"![]({img})")
    if slide.get("caption"):
        parts.append(f"*{slide['caption']}*")
    bullets = slide.get("bullets") or []
    if bullets:
        parts.append("\n".join(f"- {b}" for b in bullets))
    if slide.get("citation_source"):
        parts.append(f"<sub>Source: {slide['citation_source']}</sub>")
    return "\n\n".join(parts)


def _render_multi_figure(slide: dict[str, Any]) -> str:
    parts: list[str] = []
    if slide.get("title"):
        parts.append(f"## {slide['title']}")
    figures = slide.get("figures", [])
    for fig in figures:
        label = fig.get("label", "")
        prefix = f"**{label}**" if label else ""
        img = f"![]({fig['path']})" if fig.get("path") else ""
        cap = f"*{fig['caption']}*" if fig.get("caption") else ""
        block = "\n".join(p for p in (prefix, img, cap) if p)
        if block:
            parts.append(block)
    sources = [f.get("citation_source", "") for f in figures]
    sources = [s for s in sources if s]
    if sources:
        joined = " | ".join(dict.fromkeys(sources))
        parts.append(f"<sub>Source: {joined}</sub>")
    return "\n\n".join(parts)


def _render_text(slide: dict[str, Any]) -> str:
    parts: list[str] = []
    if slide.get("title"):
        parts.append(f"## {slide['title']}")
    bullets = slide.get("bullets") or []
    if bullets:
        parts.append("\n".join(f"- {b}" for b in bullets))
    return "\n\n".join(parts)


def _render_references(slide: dict[str, Any]) -> str:
    parts: list[str] = [f"## {slide.get('title', 'References')}"]
    refs = slide.get("references", [])
    if refs:
        parts.append("\n".join(f"- {r}" for r in refs))
    return "\n\n".join(parts)


_RENDERERS: dict[str, Any] = {
    "title": _render_title,
    "section_divider": _render_section,
    "figure": _render_figure,
    "multi_figure": _render_multi_figure,
    "text": _render_text,
    "references": _render_references,
}


__all__ = ["deck_plan_to_marp", "write_marp"]
