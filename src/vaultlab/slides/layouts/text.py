"""Text-only slide layout — title + bullets.

Lifted from ``bobby_slides._layout.add_text_slide`` (bobby-tools, 2026-04).
"""

from __future__ import annotations

from typing import Any, Iterable

from vaultlab.slides.layouts._helpers import (
    Inches,
    apply_font,
    ensure_blank_layout,
    sizes,
)


def add_text_slide(
    pres: Any,
    title: str,
    bullets: Iterable[str],
) -> Any:
    """Add a text-only slide with title and bullets.

    Args:
        pres: python-pptx Presentation.
        title: Slide title (heading size).
        bullets: List of bullet strings (body size).

    Returns:
        The slide object.
    """
    slide = pres.slides.add_slide(ensure_blank_layout(pres))
    sw_in = pres.slide_width / 914400
    sh_in = pres.slide_height / 914400
    sizes_d = sizes()

    tx = slide.shapes.add_textbox(
        Inches(0.5), Inches(0.3), Inches(sw_in - 1.0), Inches(0.8)
    )
    tx.text_frame.text = title
    apply_font(tx.text_frame, size=sizes_d["heading"], bold=True, pres=pres)

    bullets_list = list(bullets)
    if bullets_list:
        bx = slide.shapes.add_textbox(
            Inches(0.7), Inches(1.4),
            Inches(sw_in - 1.4), Inches(sh_in - 2.0),
        )
        tf = bx.text_frame
        tf.word_wrap = True
        tf.text = bullets_list[0]
        for b in bullets_list[1:]:
            p = tf.add_paragraph()
            p.text = b
        apply_font(tf, size=sizes_d["body"], pres=pres)

    return slide


__all__ = ["add_text_slide"]
