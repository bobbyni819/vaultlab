"""References slide — list of citation strings.

Lifted from ``bobby_slides._layout.add_references_slide`` (bobby-tools,
2026-04). References are rendered at the caption-min size (18pt) per the
sizing convention so a long reference list fits without breaking the
projector-readable rule.

For the typed Vancouver-style two-column references slide (used by the
``DeckPlan`` composer), see ``vaultlab.slides.deck._add_references_slide``.
"""

from __future__ import annotations

from typing import Any, Iterable

from vaultlab.slides.layouts._helpers import (
    Inches,
    apply_font,
    ensure_blank_layout,
    sizes,
)


_TWO_COLUMN_THRESHOLD = 7  # Switch to two-column layout when >N refs


def add_references_slide(
    pres: Any,
    references: Iterable[str],
    title: str = "References",
) -> Any:
    """Add a references slide. Uses two-column layout when many refs.

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

    tx = slide.shapes.add_textbox(
        Inches(0.5), Inches(0.3), Inches(sw_in - 1.0), Inches(1.2)
    )
    tx.text_frame.text = title

    tx.text_frame.word_wrap = True
    apply_font(tx.text_frame, size=sizes_d["heading"], bold=True, pres=pres)

    refs_list = list(references)
    if not refs_list:
        return slide

    # Two-column layout when many refs (avoids the over_bulleted audit warn
    # AND fits 14+ refs on one slide at 18pt).
    if len(refs_list) > _TWO_COLUMN_THRESHOLD:
        col_top = Inches(1.4)
        col_height = Inches(sh_in - 2.0)
        gap = 0.3
        col_width_in = (sw_in - 1.0 - gap) / 2
        col_left_left = Inches(0.5)
        col_left_right = Inches(0.5 + col_width_in + gap)

        # Split refs evenly across columns
        mid = (len(refs_list) + 1) // 2
        left_refs, right_refs = refs_list[:mid], refs_list[mid:]

        for col_left, col_refs in (
            (col_left_left, left_refs),
            (col_left_right, right_refs),
        ):
            if not col_refs:
                continue
            bx = slide.shapes.add_textbox(
                col_left, col_top, Inches(col_width_in), col_height
            )
            tf = bx.text_frame
            tf.word_wrap = True
            tf.text = col_refs[0]
            for r in col_refs[1:]:
                p = tf.add_paragraph()
                p.text = r
            apply_font(tf, size=sizes_d["caption"], pres=pres)
    else:
        # Single column for short lists
        bx = slide.shapes.add_textbox(
            Inches(0.5), Inches(1.4),
            Inches(sw_in - 1.0), Inches(sh_in - 2.0),
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
