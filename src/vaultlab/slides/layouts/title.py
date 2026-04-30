"""Title-slide layout — large centered title + optional subtitle and author.

Lifted from ``bobby_slides._layout.add_title_slide`` (bobby-tools, 2026-04).
Honors the dark/light theme via the shared ``apply_font`` helper.
"""

from __future__ import annotations

from typing import Any

from vaultlab.slides.layouts._helpers import (
    Inches,
    apply_font,
    ensure_blank_layout,
    sizes,
)


def add_title_slide(
    pres: Any,
    title: str,
    subtitle: str = "",
    author: str = "",
) -> Any:
    """Add a title slide.

    Args:
        pres: python-pptx Presentation.
        title: Main title (rendered at 48pt bold).
        subtitle: Smaller line below title (32pt).
        author: Bottom-line author/affiliation (24pt).

    Returns:
        The slide object.
    """
    slide = pres.slides.add_slide(ensure_blank_layout(pres))
    sizes_d = sizes()

    left = Inches(0.5)
    top = Inches(2.0)
    width = Inches(pres.slide_width / 914400 - 1.0)
    height = Inches(2.0)
    tx = slide.shapes.add_textbox(left, top, width, height)
    tx.text_frame.text = title
    apply_font(tx.text_frame, size=48, bold=True, pres=pres)

    if subtitle:
        sub = slide.shapes.add_textbox(left, Inches(4.2), width, Inches(1.0))
        sub.text_frame.text = subtitle
        apply_font(sub.text_frame, size=32, pres=pres)

    if author:
        au = slide.shapes.add_textbox(left, Inches(5.5), width, Inches(0.8))
        au.text_frame.text = author
        apply_font(au.text_frame, size=sizes_d["body"], pres=pres)

    return slide


__all__ = ["add_title_slide"]
