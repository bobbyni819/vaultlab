"""Data classes for figure understanding."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass
class ElementAnnotation:
    """A concept paired with its localized region in an image.

    The output of the full describe-find-match pipeline. The renderer in
    :mod:`vaultlab.figures.understand.render` consumes these to draw labeled
    overlays on the original figure.

    Attributes
    ----------
    label
        Short text drawn on the figure (e.g., "Introduced TCR").
    bbox_px
        Pixel-space (x0, y0, x1, y1) bounding box.
    explanation
        Long-form description for speaker notes / hover popups.
    motif_name
        Which :class:`ColorMotif` produced the region (provenance - useful when
        a user disputes the box and wants to know how it was derived).
    confidence
        Coarse 0.0-1.0 confidence; larger regions on rare motifs score higher.
        Currently a placeholder; future: combine area-fraction + motif-rarity
        + LLM verification verdict.
    use_box
        Whether to draw a bounding-box outline around the element. Default True.
        Set False when the element is small/narrow enough that just a numbered
        marker pointing at it is cleaner (e.g., a thin band that a box would
        awkwardly wrap around). Bobby 2026-04-29 flexibility ask.
    marker_offset_px
        Optional (dx, dy) pixel offset for the marker position relative to the
        box's top-left corner. Default None = standard top-left placement.
        Used to avoid marker collisions when multiple annotations are clustered;
        place markers in nearby whitespace instead of all stacking on top.
        Coordinates are SOURCE PIXELS (not inches) to keep the API consistent
        with bbox_px.
    bbox_shape
        Geometry of the box outline. ``"rect"`` (default) = rectangle.
        ``"circle"`` = ellipse fit to the bbox (use when the underlying figure
        element is a circular zoom-in / detail callout). Bobby 2026-04-29 v8:
        rectangular boxes around circular zoom-ins look loose and wrong.
    bbox_padding_px
        Override the global ``layout.bbox_padding_px`` for this annotation.
        Either a scalar (uniform) or a 4-tuple ``(top, right, bottom, left)``
        for asymmetric padding. ``None`` = use the layout default. Bobby
        2026-04-29 v8: some boxes need more padding on one side and less on
        another; uniform is too coarse.
    marker_force_global
        If True, skip the local 8-direction ring search and go straight to the
        global whitespace search (find the nearest large free patch on the
        whole figure). Useful when the element is in a content-dense region
        where local offsets all collide. Bobby 2026-04-29 v8: "you can just
        slot the label somewhere on the figure as long as it's not blocking
        underlying text."
    """

    label: str
    bbox_px: tuple[int, int, int, int]
    explanation: str = ""
    motif_name: str = ""
    confidence: float = 0.0
    use_box: bool = True
    marker_offset_px: tuple[int, int] | None = None
    bbox_shape: Literal["rect", "circle"] = "rect"
    bbox_padding_px: int | tuple[int, int, int, int] | None = None
    marker_force_global: bool = False


__all__ = ["ElementAnnotation"]
