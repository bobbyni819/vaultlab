"""Section-divider slide — large centered title only.

Lifted from ``bobby_slides._layout.add_section_divider`` (bobby-tools, 2026-04).
Use to break a deck into logical sections (Background, Methods, Results,
Discussion).
"""

from __future__ import annotations

from typing import Any

from vaultlab.slides.layouts._helpers import Inches, apply_font, ensure_blank_layout


def add_section_divider(pres: Any, title: str) -> Any:
    """Add a section divider — large centered 48pt bold title."""
    slide = pres.slides.add_slide(ensure_blank_layout(pres))
    sw_in = pres.slide_width / 914400
    sh_in = pres.slide_height / 914400

    tx = slide.shapes.add_textbox(
        Inches(0.5), Inches(sh_in / 2 - 0.5),
        Inches(sw_in - 1.0), Inches(1.5),
    )
    tx.text_frame.text = title
    apply_font(tx.text_frame, size=48, bold=True, pres=pres)
    return slide


__all__ = ["add_section_divider"]
