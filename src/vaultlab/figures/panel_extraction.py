"""Detect panels in a multi-panel publication figure via recursive XY-cut.

Bobby's 2026-05-04 ask: when a figure has panels A/B/C/D/E/F/G arranged
in non-uniform grids ("E is big and spans the height of F+G stacked"),
let the deck builder grab a SINGLE panel without showing the others.

Approach: classic XY-cut algorithm.

1. Binarize the figure (white ≈ background, dark ≈ content).
2. Trim global whitespace margin to get the figure's content bounding box.
3. Recursively cut: at each step, find the LONGEST spanning whitespace
   gap (horizontal OR vertical) wider than ``min_gap_px``. Cut along it.
4. Recurse until no more cuts possible. Leaves are individual panels.
5. Sort panels by reading order (top-to-bottom in rows, then left-to-
   right within each row) and label A, B, C, ...

The XY-cut handles non-uniform grids correctly: when E is full-height on
the left and F/G are stacked on the right, the first cut is VERTICAL
(splits left from right column), then the right column gets a HORIZONTAL
cut (splits F from G). E stays as one leaf because no whitespace gap
spans its bounding box internally.

Public API:

- :func:`detect_panels(image_path)` → list[Panel]
- :class:`Panel` — bbox (px), label (auto-assigned), area
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Panel:
    """One detected panel within a multi-panel figure."""

    bbox_px: tuple[int, int, int, int]  # (x0, y0, x1, y1)
    label: str = ""
    area_px: int = 0

    @property
    def width(self) -> int:
        return self.bbox_px[2] - self.bbox_px[0]

    @property
    def height(self) -> int:
        return self.bbox_px[3] - self.bbox_px[1]


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------


def _load_grayscale(image_path: Path | str) -> np.ndarray:
    """Open an image as a 2-D grayscale numpy array (uint8)."""
    img = Image.open(image_path).convert("L")
    return np.asarray(img)


def _binarize(arr: np.ndarray, threshold: int = 240) -> np.ndarray:
    """Binarize: 1 = white background, 0 = content."""
    return (arr >= threshold).astype(np.uint8)


def _global_content_bbox(
    binarized: np.ndarray, white_tolerance: float = 0.999
) -> tuple[int, int, int, int]:
    """Return the bbox of non-background pixels — strips the figure's outer margin.

    A row is "all-white" when ≥ ``white_tolerance`` of its pixels are white.
    Likewise for columns. Returns (x0, y0, x1, y1) in pixel coordinates,
    with x1/y1 EXCLUSIVE.
    """
    h, w = binarized.shape
    if h == 0 or w == 0:
        return (0, 0, 0, 0)

    # Row-wise: a row is all-white if >= tolerance of pixels are white
    row_white_frac = binarized.mean(axis=1)
    col_white_frac = binarized.mean(axis=0)

    non_white_rows = np.where(row_white_frac < white_tolerance)[0]
    non_white_cols = np.where(col_white_frac < white_tolerance)[0]

    if non_white_rows.size == 0 or non_white_cols.size == 0:
        # Image is all white
        return (0, 0, w, h)

    y0, y1 = int(non_white_rows[0]), int(non_white_rows[-1]) + 1
    x0, x1 = int(non_white_cols[0]), int(non_white_cols[-1]) + 1
    return (x0, y0, x1, y1)


# ---------------------------------------------------------------------------
# XY-cut — find spanning whitespace gaps + split recursively
# ---------------------------------------------------------------------------


def _find_white_runs(
    profile: np.ndarray, white_tolerance: float, min_gap: int
) -> list[tuple[int, int]]:
    """Return (start, end) ranges where ``profile`` is "all white" for ≥min_gap.

    profile[i] is the fraction-white of row i (or column i).
    A run is a contiguous block of indices where profile[i] >= white_tolerance.
    """
    is_white = profile >= white_tolerance
    runs: list[tuple[int, int]] = []
    in_run = False
    run_start = 0
    for i, w in enumerate(is_white):
        if w and not in_run:
            run_start = i
            in_run = True
        elif not w and in_run:
            if i - run_start >= min_gap:
                runs.append((run_start, i))
            in_run = False
    if in_run and len(profile) - run_start >= min_gap:
        runs.append((run_start, len(profile)))
    return runs


def _xy_cut(
    binarized: np.ndarray,
    bbox: tuple[int, int, int, int],
    *,
    min_gap_px: int,
    white_tolerance: float,
    min_panel_dim: int,
    depth: int = 0,
    max_depth: int = 8,
) -> list[tuple[int, int, int, int]]:
    """Recursively split ``bbox`` along the largest internal whitespace gap.

    Returns a list of leaf bboxes (each (x0, y0, x1, y1)).
    """
    x0, y0, x1, y1 = bbox
    h = y1 - y0
    w = x1 - x0
    if h < min_panel_dim or w < min_panel_dim or depth >= max_depth:
        return [bbox]

    region = binarized[y0:y1, x0:x1]

    # Compute row-white-fraction (within bbox)
    row_white = region.mean(axis=1)
    col_white = region.mean(axis=0)

    # Find INTERIOR runs only (not touching edges) — those would be margins
    h_runs = _find_white_runs(row_white, white_tolerance, min_gap_px)
    v_runs = _find_white_runs(col_white, white_tolerance, min_gap_px)

    interior_h = [(s, e) for s, e in h_runs if s > 0 and e < h]
    interior_v = [(s, e) for s, e in v_runs if s > 0 and e < w]

    # Compare longest interior gap on each axis
    longest_h = max((e - s for s, e in interior_h), default=0)
    longest_v = max((e - s for s, e in interior_v), default=0)

    if longest_h == 0 and longest_v == 0:
        # No interior split possible
        return [bbox]

    # Pick the axis with the longest gap; split at that gap's midpoint
    if longest_h >= longest_v:
        # Horizontal split (cut at a row range)
        s, e = max(interior_h, key=lambda r: r[1] - r[0])
        cut_top_local = s
        cut_bot_local = e
        top_bbox = (x0, y0, x1, y0 + cut_top_local)
        bot_bbox = (x0, y0 + cut_bot_local, x1, y1)
        return _xy_cut(
            binarized, top_bbox,
            min_gap_px=min_gap_px, white_tolerance=white_tolerance,
            min_panel_dim=min_panel_dim, depth=depth + 1, max_depth=max_depth,
        ) + _xy_cut(
            binarized, bot_bbox,
            min_gap_px=min_gap_px, white_tolerance=white_tolerance,
            min_panel_dim=min_panel_dim, depth=depth + 1, max_depth=max_depth,
        )
    else:
        # Vertical split (cut at a column range)
        s, e = max(interior_v, key=lambda r: r[1] - r[0])
        left_bbox = (x0, y0, x0 + s, y1)
        right_bbox = (x0 + e, y0, x1, y1)
        return _xy_cut(
            binarized, left_bbox,
            min_gap_px=min_gap_px, white_tolerance=white_tolerance,
            min_panel_dim=min_panel_dim, depth=depth + 1, max_depth=max_depth,
        ) + _xy_cut(
            binarized, right_bbox,
            min_gap_px=min_gap_px, white_tolerance=white_tolerance,
            min_panel_dim=min_panel_dim, depth=depth + 1, max_depth=max_depth,
        )


# ---------------------------------------------------------------------------
# Reading-order labeling
# ---------------------------------------------------------------------------


def _label_in_reading_order(
    bboxes: list[tuple[int, int, int, int]],
) -> list[Panel]:
    """Sort bboxes top-to-bottom in rows, left-to-right within each row.

    Uses TOP-edge bucketing: panels share a row when their top edges (y0)
    are within half the median panel height of each other. This handles
    Bobby's "E spans full height, F/G stacked on right" case correctly
    because E and F share top edge (y0≈0), so they're in the same row,
    and E sorts before F by x0. G falls in a later row.

    Labels: A, B, ..., Z, AA, AB, ...
    """
    if not bboxes:
        return []

    items = [
        {
            "bbox": bb,
            "x0": bb[0], "y0": bb[1], "x1": bb[2], "y1": bb[3],
            "h": bb[3] - bb[1],
            "w": bb[2] - bb[0],
        }
        for bb in bboxes
    ]

    # Row tolerance — half the median panel height. With tiny panels this
    # could be too small; clamp to >=20px.
    sorted_h = sorted(it["h"] for it in items)
    median_h = sorted_h[len(sorted_h) // 2] if sorted_h else 0
    row_threshold = max(20, median_h // 2)

    # Sort by top-edge first
    items.sort(key=lambda it: (it["y0"], it["x0"]))

    rows: list[list[dict]] = []
    for it in items:
        if not rows:
            rows.append([it])
            continue
        last_row = rows[-1]
        # Use the MIN y0 of last row as the reference (the row's top edge)
        last_row_y0 = min(r["y0"] for r in last_row)
        if it["y0"] - last_row_y0 > row_threshold:
            rows.append([it])
        else:
            last_row.append(it)

    # Sort each row by x
    for row in rows:
        row.sort(key=lambda it: it["x0"])

    # Flatten + label
    labeled: list[Panel] = []
    for row in rows:
        for it in row:
            label = _index_to_label(len(labeled))
            labeled.append(Panel(
                bbox_px=it["bbox"],
                label=label,
                area_px=it["w"] * it["h"],
            ))
    return labeled


def _index_to_label(i: int) -> str:
    """0 → 'A', 1 → 'B', ..., 25 → 'Z', 26 → 'AA', 27 → 'AB', ..."""
    if i < 0:
        return ""
    out = ""
    n = i
    while True:
        out = chr(ord("A") + n % 26) + out
        n = n // 26 - 1
        if n < 0:
            break
    return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_panels(
    image_path: Path | str,
    *,
    min_gap_px: int | None = None,
    min_panel_dim: int | None = None,
    white_threshold: int = 240,
    white_tolerance: float = 0.995,
) -> list[Panel]:
    """Detect panels in a multi-panel figure via recursive XY-cut.

    Args:
        image_path: Source figure (PNG/JPG/TIFF supported via Pillow).
        min_gap_px: Minimum spanning whitespace width to count as a
            panel separator. Defaults to ~1.5% of the image min dimension
            (clamped to [10, 80]).
        min_panel_dim: Minimum width/height of a leaf panel. Defaults to
            ~5% of the image min dimension.
        white_threshold: Pixel intensity (0-255) ≥ this is considered
            background.
        white_tolerance: A row/column counts as "all white" when ≥ this
            fraction of its pixels are white.

    Returns:
        List of :class:`Panel` objects in reading order with labels
        ``A``, ``B``, ``C``, ...
    """
    arr = _load_grayscale(image_path)
    binarized = _binarize(arr, threshold=white_threshold)
    h, w = binarized.shape
    if h == 0 or w == 0:
        return []

    min_dim = min(h, w)
    if min_gap_px is None:
        min_gap_px = max(10, min(80, int(min_dim * 0.015)))
    if min_panel_dim is None:
        min_panel_dim = max(40, int(min_dim * 0.05))

    # Step 1 — strip the global outer margin
    global_bbox = _global_content_bbox(binarized, white_tolerance=white_tolerance)

    # Step 2 — XY-cut within the content bbox
    leaves = _xy_cut(
        binarized, global_bbox,
        min_gap_px=min_gap_px, white_tolerance=white_tolerance,
        min_panel_dim=min_panel_dim,
    )

    # Step 3 — filter out thin "panel-letter" strips that XY-cut creates as
    # leaves. A real panel has both dimensions ≥ min_panel_dim AND a
    # reasonable aspect ratio (publication panels are rarely >15:1).
    def _is_real_panel(bb: tuple[int, int, int, int]) -> bool:
        bw = bb[2] - bb[0]
        bh = bb[3] - bb[1]
        if bw < min_panel_dim or bh < min_panel_dim:
            return False
        # Reject extreme aspect (panel-letter strips, separator bars)
        aspect = bw / bh if bh else 0
        if aspect > 15 or aspect < (1.0 / 15):
            return False
        return True

    real_leaves = [bb for bb in leaves if _is_real_panel(bb)]

    # Step 4 — order + label
    return _label_in_reading_order(real_leaves)


__all__ = ["Panel", "detect_panels"]
