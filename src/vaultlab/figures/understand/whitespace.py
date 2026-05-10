"""Whitespace detection - find blank zones in a figure for marker placement.

Per Bobby 2026-04-29 figure-annotation decision tree: marker placement should
not be guess-by-eye. After identifying each element's bbox, programmatically
find nearby whitespace and offset the marker to land there.

v2 approach (2026-04-29 with edge avoidance)
--------------------------------------------
The v1 version was fooled by text labels: a "Aberrantly Expressed Protein"
text label has ~85% white pixels and ~15% dark glyphs, so a 60%-whitespace
patch test passed and markers landed on top of text. The fix:

1. Color whitespace mask: HSV pixels with V > 0.92 AND S < 0.08.
2. Edge map via Canny. Dilate edges by ~15 px so the "near a glyph" zone
   is also excluded.
3. True-whitespace mask = color-white AND NOT near-edge.
4. Bumped patch threshold to 90% (was 60%) - real whitespace, no text.
5. Caching: per-image mask is cached, keyed by ``(image_path, mtime)``.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

import numpy as np
from PIL import Image
from skimage import color as skcolor
from skimage.feature import canny
from skimage.morphology import binary_dilation, disk

Direction = Literal[
    "top",
    "right",
    "bottom",
    "left",
    "top-left",
    "top-right",
    "bottom-left",
    "bottom-right",
]


def whitespace_mask(image_path: str | Path) -> np.ndarray:
    """Return a strict whitespace mask: white background AND no text/glyphs nearby.

    Strict = patches over text labels are EXCLUDED via edge dilation.
    """
    return _compute_mask(str(Path(image_path).resolve()), Path(image_path).stat().st_mtime)


@lru_cache(maxsize=8)
def _compute_mask(path_str: str, mtime: float) -> np.ndarray:
    """Cache key: (resolved path, mtime). Recomputes when the file changes."""
    rgb = np.asarray(Image.open(path_str).convert("RGB"))
    gray = skcolor.rgb2gray(rgb)
    hsv = skcolor.rgb2hsv(rgb)

    # White-ish color
    color_white = (hsv[..., 2] > 0.92) & (hsv[..., 1] < 0.08)

    # Edge map - Canny finds glyph strokes + line art
    edges = canny(gray, sigma=2.0)
    # Dilate edges aggressively so the "near a glyph or line" zone is excluded.
    # 30 px radius covers full text glyphs + their immediate margin so a 120px
    # marker patch over text gets caught.
    edges_dilated = binary_dilation(edges, disk(30))

    return color_white & ~edges_dilated


def find_marker_offset(
    image_path: str | Path,
    bbox: tuple[int, int, int, int],
    *,
    marker_size_px: int = 120,
    preferred_directions: tuple[Direction, ...] = (
        "top",
        "bottom",
        "left",
        "right",
        "top-left",
        "top-right",
        "bottom-left",
        "bottom-right",
    ),
    avoid_other_bboxes: tuple[tuple[int, int, int, int], ...] = (),
    min_whitespace_frac: float = 0.90,
    force_global: bool = False,
) -> tuple[int, int] | None:
    """Find a whitespace offset near the bbox where a marker would fit.

    Two-stage search:

    1. **Local ring** (default): try 8 directions × 3 radii relative to the
       bbox. This works for figures with predictable margins around elements.
    2. **Global fallback** (if local fails or ``force_global=True``): scan
       the whole figure for the largest free patch, ranked by closeness to
       the bbox center. Per Bobby 2026-04-29 v8: "you can just slot the label
       somewhere on the figure as long as it's not blocking underlying text."

    Parameters
    ----------
    image_path
        Source figure.
    bbox
        ``(x0, y0, x1, y1)`` of the element being annotated, in source pixels.
    marker_size_px
        Square edge length of the marker in source pixels (rough - used to
        reserve a square of whitespace).
    preferred_directions
        Order in which to test directions during the local stage.
    avoid_other_bboxes
        Other annotation bboxes (or their existing markers) - we won't place
        the marker on top of these.
    min_whitespace_frac
        Minimum fraction of the candidate patch that must be true whitespace
        (post-edge-dilation). 0.90 default - text labels won't pass.
    force_global
        If True, skip the local ring stage and go straight to the global
        fallback. Useful for elements in dense content regions.

    Returns
    -------
    tuple[int, int] | None
        ``(dx, dy)`` offset from bbox top-left where the marker should be
        placed. ``None`` only if NO whitespace patch exists anywhere on the
        figure (very rare; signals the figure has no margins at all).
    """
    mask = whitespace_mask(image_path)
    H, W = mask.shape
    x0, y0, x1, y1 = bbox

    if not force_global:
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

        for radius_mult in (1, 2, 3):
            for direction in preferred_directions:
                dx, dy = candidates[direction]
                dx *= radius_mult
                dy *= radius_mult
                mx = x0 + dx
                my = y0 + dy
                if mx < 0 or my < 0 or mx + marker_size_px > W or my + marker_size_px > H:
                    continue
                if _collides(
                    (mx, my, mx + marker_size_px, my + marker_size_px),
                    avoid_other_bboxes,
                ):
                    continue
                patch = mask[my : my + marker_size_px, mx : mx + marker_size_px]
                if patch.size == 0:
                    continue
                ws_frac = float(patch.mean())
                if ws_frac >= min_whitespace_frac:
                    return (dx, dy)

    # Global fallback: scan the figure on a coarse grid, score each candidate
    # by (whitespace_frac, -distance_to_bbox_center, no_collision). Bobby's
    # rule applies: anywhere on the figure is acceptable as long as it's not
    # blocking underlying text.
    cx = (x0 + x1) // 2
    cy = (y0 + y1) // 2
    step = max(marker_size_px // 3, 30)
    best: tuple[float, int, int] | None = None  # (score, mx, my) higher = better
    for my in range(0, H - marker_size_px, step):
        for mx in range(0, W - marker_size_px, step):
            if _collides(
                (mx, my, mx + marker_size_px, my + marker_size_px),
                avoid_other_bboxes,
            ):
                continue
            # Skip patches that overlap the bbox itself
            if not (mx + marker_size_px <= x0 or x1 <= mx or my + marker_size_px <= y0 or y1 <= my):
                continue
            patch = mask[my : my + marker_size_px, mx : mx + marker_size_px]
            if patch.size == 0:
                continue
            ws_frac = float(patch.mean())
            if ws_frac < min_whitespace_frac:
                continue
            # Score: prefer high whitespace fraction, prefer near bbox center.
            # Distance is normalized by figure diagonal so the two terms are
            # comparable.
            patch_cx = mx + marker_size_px // 2
            patch_cy = my + marker_size_px // 2
            dist = ((patch_cx - cx) ** 2 + (patch_cy - cy) ** 2) ** 0.5
            diag = (W * W + H * H) ** 0.5
            score = ws_frac - 0.5 * (dist / diag)
            if best is None or score > best[0]:
                best = (score, mx, my)

    if best is not None:
        _, mx, my = best
        return (mx - x0, my - y0)

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
