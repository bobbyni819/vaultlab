"""HTML keynav preview of a deck plan.

Consumer #6 of ``vaultlab.report``. Renders a deck plan dict (or an actual
.pptx file when ``python-pptx`` is installed) as a single-file HTML
slideshow with arrow-key navigation, slide thumbnails, and per-slide
content (title, subtitle, bullets, caption, figure path).

Use cases:

- Verify a generated .pptx remotely / on phone without opening PowerPoint.
- Preview a deck plan dict before building the actual .pptx.
- Share a quick read-only preview with a collaborator.

Pattern source: Thariq Shihipar #13 (Arrow-Key Slide Deck) at
thariqs.github.io/html-effectiveness/09-slide-deck.html.
"""

from __future__ import annotations

import base64
import html as _html
from pathlib import Path
from typing import Any

from vaultlab.report import components as c
from vaultlab.report import render_report


def _safe(text: Any) -> str:
    return _html.escape(str(text or ""))


def _figure_inline_block(figure_path: Path | str | None) -> str:
    """Embed a figure as inline base64 if it exists; otherwise show a placeholder."""
    if not figure_path:
        return ""
    p = Path(figure_path)
    if not p.exists():
        return f'<div style="color:var(--muted);font-style:italic;">[figure not found: <code>{_safe(p)}</code>]</div>'
    try:
        data = p.read_bytes()
    except OSError:
        return f'<div style="color:var(--bad);">[figure unreadable: <code>{_safe(p)}</code>]</div>'
    suffix = p.suffix.lower().lstrip(".")
    mime = {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
        "svg": "image/svg+xml",
        "webp": "image/webp",
    }.get(suffix, "application/octet-stream")
    b64 = base64.b64encode(data).decode("ascii")
    return (
        f'<img src="data:{mime};base64,{b64}" '
        f'style="max-width:100%;max-height:340px;display:block;'
        f'margin:14px auto;border-radius:4px;border:1px solid var(--line-soft);">'
    )


def _bullets_block(bullets: list[str]) -> str:
    if not bullets:
        return ""
    items = "".join(f"<li>{_safe(b)}</li>" for b in bullets[:8])
    return (
        f'<ul style="font-size:16px;line-height:1.6;margin:14px 0;padding-left:24px;">{items}</ul>'
    )


def _references_block(refs: list[str]) -> str:
    if not refs:
        return ""
    items = "".join(
        f'<li style="font-size:12px;color:var(--ink-soft);margin-bottom:4px;">{_safe(r)}</li>'
        for r in refs[:30]
    )
    return (
        '<div style="margin-top:14px;padding-top:10px;border-top:1px solid var(--line-soft);">'
        '<div style="font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:0.04em;margin-bottom:6px;">References</div>'
        f'<ol style="margin:0;padding-left:24px;">{items}</ol></div>'
    )


def _slide_content(
    slide: dict[str, Any],
    *,
    embed_figures: bool = True,
) -> str:
    """Compose one slide's HTML body from a plan-dict slide."""
    parts: list[str] = []
    if slide.get("subtitle"):
        parts.append(
            f'<div style="color:var(--muted);font-size:14px;margin-bottom:6px;">'
            f"{_safe(slide['subtitle'])}</div>"
        )
    bullets = slide.get("bullets") or []
    if bullets:
        parts.append(_bullets_block(bullets))
    if slide.get("caption"):
        parts.append(
            f'<p style="font-size:13px;color:var(--ink-soft);font-style:italic;margin-top:12px;">'
            f"{_safe(slide['caption'])}</p>"
        )
    if embed_figures and slide.get("figure"):
        parts.append(_figure_inline_block(slide["figure"]))
    elif slide.get("figure"):
        parts.append(
            f'<div style="color:var(--muted);font-size:12px;margin-top:10px;">'
            f"figure: <code>{_safe(slide['figure'])}</code></div>"
        )
    if slide.get("citation_source"):
        parts.append(
            f'<div style="font-size:11px;color:var(--muted);margin-top:8px;">'
            f"source: {_safe(slide['citation_source'])}</div>"
        )
    refs = slide.get("references") or []
    if refs:
        parts.append(_references_block(refs))
    if not parts:
        parts.append(
            '<p style="color:var(--muted);font-style:italic;">(no content on this slide)</p>'
        )
    slide_type = slide.get("type") or "?"
    parts.insert(
        0,
        f'<div style="font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:0.04em;margin-bottom:14px;">'
        f"{_safe(slide_type)}</div>",
    )
    return "".join(parts)


def build_deck_preview_html(
    plan: dict[str, Any],
    *,
    title: str | None = None,
    embed_figures: bool = True,
) -> str:
    """Render a deck plan dict as an arrow-key navigable HTML slideshow.

    Parameters
    ----------
    plan:
        Deck plan dict with ``title`` and ``slides`` (each slide has
        ``type``, ``title``, optional ``subtitle``, ``bullets``, ``caption``,
        ``figure``, ``citation_source``, ``references``).
    title:
        Override report title.
    embed_figures:
        If True (default), embed referenced figure files as inline base64
        (works offline). If False, just show the figure path.
    """
    slides = plan.get("slides", []) or []
    deck_title = plan.get("title", "(untitled deck)")
    report_title = title or f"Deck preview — {deck_title}"

    slide_pairs: list[tuple[str, str]] = []
    for i, slide in enumerate(slides):
        slide_title = slide.get("title") or f"Slide {i + 1}"
        slide_pairs.append((slide_title, _slide_content(slide, embed_figures=embed_figures)))

    if not slide_pairs:
        slide_pairs = [("(empty deck)", "<p>No slides in plan.</p>")]

    sections = [
        c.section(
            None,
            c.tldr_box(
                [
                    f"{len(slides)} slide{'s' if len(slides) != 1 else ''} previewed.",
                    "Use ← / → arrow keys to navigate. Click outside the deck to release focus.",
                ]
            ),
        ),
        c.section(
            None,
            c.keynav_deck(slide_pairs),
        ),
    ]

    return render_report(
        title=report_title,
        eyebrow="vaultlab · deck preview",
        subtitle=deck_title,
        meta=f"{len(slides)} slides",
        sections=sections,
    )


def write_deck_preview(
    out_path: Path | str,
    plan: dict[str, Any],
    **kwargs: Any,
) -> Path:
    """Render and write the HTML deck preview."""
    html_str = build_deck_preview_html(plan, **kwargs)
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(html_str, encoding="utf-8")
    return p


__all__ = ["build_deck_preview_html", "write_deck_preview"]
