"""Multi-figure slide layout — N figures auto-arranged in a grid.

Lifted from ``bobby_slides._layout.add_multi_figure_slide`` (bobby-tools,
2026-04). Auto-picks grid: 2 figs = 1×2, 3 figs = 1×3, 4 = 2×2, 5-6 = 2×3.

Each panel is a (picture + label + caption) group; the groups are attached
to ``slide._vaultlab_panel_groups`` so the animation engine can fire them
together as one click event per panel.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from vaultlab.slides.layouts._helpers import (
    Inches,
    add_picture_fit,
    apply_font,
    ensure_blank_layout,
    sizes,
)


def add_multi_figure_slide(
    pres: Any,
    figures: list[dict],
    title: str = "",
) -> Any:
    """Add a slide with multiple figures arranged in a grid.

    Args:
        pres: python-pptx Presentation.
        figures: List of dicts with keys ``"path"`` (required), ``"label"``
            (optional), ``"caption"`` (optional), ``"citation_source"``
            (optional).
        title: Slide title.

    Returns:
        The slide object. ``slide._vaultlab_panel_groups`` is set so panel
        build-up animation can fire the picture+label+caption together.
    """
    slide = pres.slides.add_slide(ensure_blank_layout(pres))
    sw_in = pres.slide_width / 914400
    sh_in = pres.slide_height / 914400
    sizes_d = sizes()

    if title:
        tx = slide.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(sw_in - 1.0), Inches(0.8))
        tx.text_frame.text = title
        apply_font(tx.text_frame, size=sizes_d["heading"], bold=True, pres=pres)

    n = len(figures)
    if n == 0:
        return slide

    # Pick grid
    if n == 1:
        rows, cols = 1, 1
    elif n == 2:
        rows, cols = 1, 2
    elif n == 3:
        rows, cols = 1, 3
    elif n == 4:
        rows, cols = 2, 2
    else:
        rows, cols = 2, 3

    grid_top = 1.3
    grid_height = sh_in - 2.0
    grid_left = 0.4
    grid_width = sw_in - 0.8
    cell_h = grid_height / rows
    cell_w = grid_width / cols

    panel_shape_groups: list[list[Any]] = []

    for i, fig in enumerate(figures[: rows * cols]):
        r, c = divmod(i, cols)
        cell_left_in = grid_left + c * cell_w + 0.1
        cell_top_in = grid_top + r * cell_h + 0.1
        cell_w_inner = cell_w - 0.2
        cell_h_inner = cell_h - 0.6  # reserve space for caption

        group: list[Any] = []
        img_path = Path(fig["path"])
        pic = add_picture_fit(
            slide,
            str(img_path),
            Inches(cell_left_in),
            Inches(cell_top_in),
            Inches(cell_w_inner),
            Inches(cell_h_inner),
        )
        if pic is not None:
            group.append(pic)

        label = fig.get("label", "")
        if label:
            lbl = slide.shapes.add_textbox(
                Inches(cell_left_in - 0.1),
                Inches(cell_top_in - 0.1),
                Inches(0.5),
                Inches(0.4),
            )
            lbl.text_frame.text = label
            apply_font(lbl.text_frame, size=24, bold=True, pres=pres)
            group.append(lbl)

        cap = fig.get("caption", "")
        if cap:
            cx = slide.shapes.add_textbox(
                Inches(cell_left_in),
                Inches(cell_top_in + cell_h_inner),
                Inches(cell_w_inner),
                Inches(0.5),
            )
            cx.text_frame.text = cap
            cx.text_frame.word_wrap = True
            apply_font(cx.text_frame, size=14, pres=pres)
            group.append(cx)

        if group:
            panel_shape_groups.append(group)

    slide._vaultlab_panel_groups = panel_shape_groups

    sources = [f.get("citation_source", "") for f in figures]
    sources = [s for s in sources if s]
    if sources:
        joined = " | ".join(dict.fromkeys(sources))  # dedupe, preserve order
        cit = slide.shapes.add_textbox(
            Inches(0.3),
            Inches(sh_in - 0.4),
            Inches(sw_in - 0.6),
            Inches(0.3),
        )
        cit.text_frame.text = joined
        apply_font(cit.text_frame, size=9, pres=pres)

    return slide


__all__ = ["add_multi_figure_slide"]
