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


# ---------------------------------------------------------------------------
# Panel detection — XY-cut gutter projection (sub-goal 5.5)
# ---------------------------------------------------------------------------
#
# Comp-bio + wet-lab researchers regularly submit single-plot figures (one
# volcano, one UMAP, one bar chart). The old code paths assumed every figure
# was multi-panel; panel-cutting those subdivided legend boxes / axis labels
# into bogus "panels". Sub-goal 5.5 adds:
#
#   * detect_panels(image_path) — recursive XY-cut: project the whitespace
#     mask onto X and Y axes, find contiguous high-whitespace gutters, split
#     and recurse.
#   * is_single_plot(image_path) — convenience predicate.
#
# Why this works:
#   The whitespace mask already excludes glyph-adjacent pixels (edge-dilation
#   covers ≥30px radius around any text or axis line). So a corner-legend
#   does NOT carve out a gutter — the legend glyphs anchor an edge-zone that
#   prevents the projection from registering a clean cut. Only structural
#   gutters between subplots survive.
#
# Algorithm parameters (chosen empirically against matplotlib-default output
# at dpi=100, bbox_inches="tight"):
#   - min gutter thickness: 3% of the corresponding axis
#   - min gutter purity:    99% of pixels along the projected band must be
#                           true whitespace
#   - min panel side:       12% of the corresponding axis (smaller candidate
#                           splits are rejected — they're usually padding
#                           around the figure edge, not real panels)
#   - max recursion depth:  3 (so a 2×2 grid splits into 4 panels but we
#                           don't keep slicing inside each panel forever)


def _project_whitespace(mask, axis: int):
    """Per-row (axis=1) or per-column (axis=0) whitespace fraction in [0, 1]."""
    return mask.mean(axis=axis)


def _find_gutters(
    profile,
    *,
    min_run: int,
    purity: float = 0.99,
) -> list[tuple[int, int]]:
    """Find contiguous runs in ``profile`` where value ≥ ``purity``.

    Returns list of ``(start, end_exclusive)``. Runs shorter than ``min_run``
    are dropped.
    """
    runs: list[tuple[int, int]] = []
    in_run = False
    start = 0
    for i, v in enumerate(profile):
        if v >= purity:
            if not in_run:
                start = i
                in_run = True
        else:
            if in_run:
                if i - start >= min_run:
                    runs.append((start, i))
                in_run = False
    if in_run and len(profile) - start >= min_run:
        runs.append((start, len(profile)))
    return runs


def _split_by_gutters(
    length: int, gutters: list[tuple[int, int]], *, min_side: int
) -> list[tuple[int, int]]:
    """Convert gutter runs into the inter-gutter segments to keep.

    Drop segments shorter than ``min_side`` (they're padding or sliver text).
    """
    if not gutters:
        return [(0, length)]
    # Outer padding gutters (touching either edge) are not real splits — they
    # just bound the figure. Filter them out so a centered chart with a wide
    # outside margin doesn't get classed as "two panels" (the chart + a void).
    interior = [g for g in gutters if g[0] > 0 and g[1] < length]
    if not interior:
        return [(0, length)]
    segments: list[tuple[int, int]] = []
    cursor = 0
    for gs, ge in interior:
        if gs - cursor >= min_side:
            segments.append((cursor, gs))
        cursor = ge
    if length - cursor >= min_side:
        segments.append((cursor, length))
    return segments


def _xy_cut(
    mask, x0: int, y0: int, x1: int, y1: int, *, depth: int, max_depth: int
) -> list[tuple[int, int, int, int]]:
    """Recursive XY-cut on the slice ``mask[y0:y1, x0:x1]``.

    Returns a list of bboxes in **source-image coordinates**. Each step tries
    the dimension with the strongest gutter first; if it splits into ≥2
    segments, recurse into each segment on the orthogonal dimension. Stops
    when no gutter exists or ``depth >= max_depth``.
    """
    sub = mask[y0:y1, x0:x1]
    H, W = sub.shape
    if H == 0 or W == 0 or depth >= max_depth:
        return [(x0, y0, x1, y1)]

    min_run_x = max(int(W * 0.03), 4)
    min_run_y = max(int(H * 0.03), 4)
    min_side_x = max(int(W * 0.12), 20)
    min_side_y = max(int(H * 0.12), 20)

    col_profile = _project_whitespace(sub, axis=0)  # mean over rows → per-col
    row_profile = _project_whitespace(sub, axis=1)  # mean over cols → per-row

    vertical_gutters = _find_gutters(col_profile, min_run=min_run_x)
    horizontal_gutters = _find_gutters(row_profile, min_run=min_run_y)

    x_segments = _split_by_gutters(W, vertical_gutters, min_side=min_side_x)
    y_segments = _split_by_gutters(H, horizontal_gutters, min_side=min_side_y)

    # No interior gutter survived on either axis → this is a leaf panel.
    if len(x_segments) == 1 and len(y_segments) == 1:
        return [(x0, y0, x1, y1)]

    results: list[tuple[int, int, int, int]] = []
    # Take the cartesian product. For a 2×2 grid that's 4 cells; for a 1×N
    # row of panels one of the axes is a singleton segment.
    for ys, ye in y_segments:
        for xs, xe in x_segments:
            sub_x0 = x0 + xs
            sub_y0 = y0 + ys
            sub_x1 = x0 + xe
            sub_y1 = y0 + ye
            # Recurse one more level so an irregular composite (e.g. row of
            # 3 on top + 1 wide below) still gets split fully. With
            # max_depth=3 we never recurse forever.
            results.extend(
                _xy_cut(
                    mask,
                    sub_x0,
                    sub_y0,
                    sub_x1,
                    sub_y1,
                    depth=depth + 1,
                    max_depth=max_depth,
                )
            )
    return results


def detect_panels(
    image: str | Path | "Image.Image",
    *,
    max_depth: int = 3,
) -> list[tuple[int, int, int, int]]:
    """Detect panel bounding boxes in a figure via XY-cut whitespace gutters.

    Parameters
    ----------
    image
        Path to a PNG/JPG, or a ``PIL.Image.Image`` instance.
    max_depth
        Maximum recursion depth. Default 3 splits a 2×2 grid in one pass and
        bottoms out before pathological over-segmentation.

    Returns
    -------
    list[tuple[int, int, int, int]]
        ``(x0, y0, x1, y1)`` for each detected panel, in source pixels.
        Length 1 for single-plot figures; ≥2 for multi-panel figures.

    Notes
    -----
    The algorithm is intentionally conservative — it only splits where the
    whitespace mask shows a contiguous gutter of ≥3% of the corresponding
    axis at ≥99% true-whitespace purity. Because the whitespace mask
    excludes a 30-px edge-dilation zone around every glyph and axis line, a
    corner legend does not carve out an interior gutter.

    Used by :func:`is_single_plot` and by
    :func:`vaultlab.figures.contract.suggest_figure_layout` (sub-goal 5.5).
    """
    if isinstance(image, (str, Path)):
        mask = whitespace_mask(image)
    else:
        # PIL.Image input — bypass the cache (no stable mtime key).
        rgb = np.asarray(image.convert("RGB"))
        gray = skcolor.rgb2gray(rgb)
        hsv = skcolor.rgb2hsv(rgb)
        color_white = (hsv[..., 2] > 0.92) & (hsv[..., 1] < 0.08)
        edges = canny(gray, sigma=2.0)
        edges_dilated = binary_dilation(edges, disk(30))
        mask = color_white & ~edges_dilated

    H, W = mask.shape
    return _xy_cut(mask, 0, 0, W, H, depth=0, max_depth=max_depth)


def is_single_plot(image: str | Path | "Image.Image") -> bool:
    """True iff the figure has exactly one detected panel.

    Convenience predicate over :func:`detect_panels`. Use it in layout
    dispatch to skip panel-cutting for single-plot figures (volcano, UMAP,
    single bar chart, etc.).
    """
    return len(detect_panels(image)) == 1


__all__ = [
    "detect_panels",
    "find_marker_offset",
    "is_single_plot",
    "whitespace_mask",
]
