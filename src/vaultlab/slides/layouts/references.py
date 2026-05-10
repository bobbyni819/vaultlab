"""References slide — list of citation strings.

Lifted from ``bobby_slides._layout.add_references_slide`` (bobby-tools,
2026-04). References are rendered at the caption-min size (18pt) per the
sizing convention so a long reference list fits without breaking the
projector-readable rule.

For the typed Vancouver-style two-column references slide (used by the
``DeckPlan`` composer), see ``vaultlab.slides.deck._add_references_slide``.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from vaultlab.slides.layouts._helpers import (
    Inches,
    apply_font,
    ensure_blank_layout,
    sizes,
)


def add_references_slide(
    pres: Any,
    references: Iterable[str],
    title: str = "References",
) -> Any:
    """Add a single-column references slide.

    Args:
        pres: python-pptx Presentation.
        references: Iterable of reference strings.
        title: Slide title (default ``"References"``).

    Returns:
        The slide object.
    """
    slide = pres.slides.add_slide(ensure_blank_layout(pres))
    sw_in = pres.slide_width / 914400
    sh_in = pres.slide_height / 914400
    sizes_d = sizes()

    tx = slide.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(sw_in - 1.0), Inches(0.8))
    tx.text_frame.text = title
    apply_font(tx.text_frame, size=sizes_d["heading"], bold=True, pres=pres)

    refs_list = list(references)
    if refs_list:
        bx = slide.shapes.add_textbox(
            Inches(0.5),
            Inches(1.4),
            Inches(sw_in - 1.0),
            Inches(sh_in - 2.0),
        )
        tf = bx.text_frame
        tf.word_wrap = True
        tf.text = refs_list[0]
        for r in refs_list[1:]:
            p = tf.add_paragraph()
            p.text = r
        apply_font(tf, size=sizes_d["caption"], pres=pres)

    return slide


__all__ = ["add_references_slide"]
