"""Whitespace detection - find blank zones in a figure for marker placement.

Per Bobby 2026-04-29 figure-annotation decision tree: marker placement should
not be guess-by-eye. After identifying each element's bbox, programmatically
find nearby whitespace and offset the marker to land there.

Approach
--------
1. Convert image to HSV.
2. Whitespace mask = pixels with very high value (V > 0.9) AND very low
   saturation (S < 0.1). That captures both pure white AND off-white card
   backgrounds (which BioRender uses).
3. For each query bbox, search radially outward (in 4 directions: top, right,
   bottom, left) for the nearest patch large enough to fit a marker.
4. Return the best ``marker_offset_px`` to use, or ``None`` if no close
   whitespace exists (caller falls back to default top-left).
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import numpy as np
from PIL import Image
from skimage import color as skcolor

Direction = Literal["top", "right", "bottom", "left", "top-left", "top-right", "bottom-left", "bottom-right"]


def whitespace_mask(image_path: str | Path) -> np.ndarray:
    """Return a boolean mask of whitespace pixels in the image.

    Whitespace = high value (V > 0.9) AND low saturation (S < 0.1). Captures
    pure white plus near-white BioRender card backgrounds.
    """
    rgb = np.asarray(Image.open(Path(image_path)).convert("RGB"))
    hsv = skcolor.rgb2hsv(rgb)
    s = hsv[..., 1]
    v = hsv[..., 2]
    return (v > 0.90) & (s < 0.10)


def find_marker_offset(
    image_path: str | Path,
    bbox: tuple[int, int, int, int],
    *,
    marker_size_px: int = 120,
    search_radius_px: int = 400,
    preferred_directions: tuple[Direction, ...] = (
        "left", "top", "right", "bottom", "top-left", "top-right",
    ),
    avoid_other_bboxes: tuple[tuple[int, int, int, int], ...] = (),
) -> tuple[int, int] | None:
    """Find a whitespace offset near the bbox where a marker would fit.

    Parameters
    ----------
    image_path
        Source figure.
    bbox
        ``(x0, y0, x1, y1)`` of the element being annotated, in source pixels.
    marker_size_px
        Square edge length of the marker in source pixels (rough — used to
        reserve a square of whitespace).
    search_radius_px
        How far from the bbox to search for whitespace (each direction).
    preferred_directions
        Order in which to test directions. First match wins.
    avoid_other_bboxes
        Other annotation bboxes (or their existing markers) - we won't place
        the marker on top of these.

    Returns
    -------
    tuple[int, int] | None
        ``(dx, dy)`` offset from bbox top-left where the marker should be
        placed. ``None`` if no whitespace candidate found - caller should
        fall back to default placement.
    """
    mask = whitespace_mask(image_path)
    H, W = mask.shape
    x0, y0, x1, y1 = bbox

    # Candidate marker positions per direction, expressed as the marker's
    # top-left (mx, my) relative to the BOX top-left (x0, y0).
    # Each candidate has a small inset so the marker isn't flush with the
    # box edge.
    inset = 30
    candidates: dict[Direction, tuple[int, int]] = {
        "left": (-marker_size_px - inset, (y1 - y0) // 2 - marker_size_px // 2),
        "right": ((x1 - x0) + inset, (y1 - y0) // 2 - marker_size_px // 2),
        "top": ((x1 - x0) // 2 - marker_size_px // 2, -marker_size_px - inset),
        "bottom": ((x1 - x0) // 2 - marker_size_px // 2, (y1 - y0) + inset),
        "top-left": (-marker_size_px - inset, -marker_size_px - inset),
        "top-right": ((x1 - x0) + inset, -marker_size_px - inset),
        "bottom-left": (-marker_size_px - inset, (y1 - y0) + inset),
        "bottom-right": ((x1 - x0) + inset, (y1 - y0) + inset),
    }

    for direction in preferred_directions:
        dx, dy = candidates[direction]
        # Absolute marker position
        mx = x0 + dx
        my = y0 + dy
        # Outside image?
        if mx < 0 or my < 0 or mx + marker_size_px > W or my + marker_size_px > H:
            continue
        # Collides with another bbox?
        if _collides(
            (mx, my, mx + marker_size_px, my + marker_size_px),
            avoid_other_bboxes,
        ):
            continue
        # Whitespace fraction in the patch
        patch = mask[my:my + marker_size_px, mx:mx + marker_size_px]
        if patch.size == 0:
            continue
        ws_frac = float(patch.mean())
        if ws_frac >= 0.6:  # at least 60% whitespace
            return (dx, dy)

    return None


def _collides(
    rect: tuple[int, int, int, int],
    others: tuple[tuple[int, int, int, int], ...],
) -> bool:
    rx0, ry0, rx1, ry1 = rect
    for ox0, oy0, ox1, oy1 in others:
        if not (rx1 <= ox0 or ox1 <= rx0 or ry1 <= oy0 or oy1 <= ry0):
            return True
    return False


__all__ = ["find_marker_offset", "whitespace_mask"]
