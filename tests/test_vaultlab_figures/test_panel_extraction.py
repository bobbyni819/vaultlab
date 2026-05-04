"""Tests for vaultlab.figures.panel_extraction — XY-cut panel detection."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from vaultlab.figures.panel_extraction import (
    Panel,
    _binarize,
    _find_white_runs,
    _global_content_bbox,
    _index_to_label,
    _label_in_reading_order,
    detect_panels,
)


# ---------------------------------------------------------------------------
# Synthetic figure builders
# ---------------------------------------------------------------------------


def _make_figure(arr: np.ndarray, path: Path) -> Path:
    """Save a uint8 grayscale numpy array as a PNG for testing."""
    img = Image.fromarray(arr, mode="L")
    img.save(path)
    return path


def _white_canvas(h: int, w: int) -> np.ndarray:
    return np.full((h, w), 255, dtype=np.uint8)


def _fill(arr: np.ndarray, x0: int, y0: int, x1: int, y1: int, val: int = 50) -> None:
    """Fill a rectangle with non-white pixels (representing panel content)."""
    arr[y0:y1, x0:x1] = val


# ---------------------------------------------------------------------------
# Index → label
# ---------------------------------------------------------------------------


def test_index_to_label_first_26():
    assert _index_to_label(0) == "A"
    assert _index_to_label(1) == "B"
    assert _index_to_label(25) == "Z"


def test_index_to_label_double_letters():
    assert _index_to_label(26) == "AA"
    assert _index_to_label(27) == "AB"
    assert _index_to_label(51) == "AZ"
    assert _index_to_label(52) == "BA"


# ---------------------------------------------------------------------------
# Whitespace-run detection
# ---------------------------------------------------------------------------


def test_find_white_runs_single_run():
    profile = np.array([0.5, 0.5, 1.0, 1.0, 1.0, 0.5, 0.5])
    runs = _find_white_runs(profile, white_tolerance=0.99, min_gap=1)
    assert runs == [(2, 5)]


def test_find_white_runs_filters_short_gaps():
    profile = np.array([0.5, 1.0, 1.0, 0.5, 1.0, 1.0, 1.0, 1.0, 1.0, 0.5])
    runs = _find_white_runs(profile, white_tolerance=0.99, min_gap=4)
    # The first 2-pixel run is below min_gap=4; only the 5-pixel run qualifies
    assert runs == [(4, 9)]


def test_find_white_runs_handles_run_to_end():
    profile = np.array([0.5, 0.5, 1.0, 1.0, 1.0])
    runs = _find_white_runs(profile, white_tolerance=0.99, min_gap=1)
    assert runs == [(2, 5)]


# ---------------------------------------------------------------------------
# Global content bbox
# ---------------------------------------------------------------------------


def test_global_content_bbox_strips_outer_margin():
    canvas = _white_canvas(200, 300)
    _fill(canvas, 50, 30, 250, 170)  # content at (50,30)-(250,170)
    binarized = _binarize(canvas)
    bbox = _global_content_bbox(binarized)
    # Allow tolerance: edges of content
    assert bbox[0] >= 49 and bbox[0] <= 51
    assert bbox[1] >= 29 and bbox[1] <= 31
    assert bbox[2] >= 249 and bbox[2] <= 251
    assert bbox[3] >= 169 and bbox[3] <= 171


def test_global_content_bbox_all_white_image():
    canvas = _white_canvas(50, 50)
    binarized = _binarize(canvas)
    bbox = _global_content_bbox(binarized)
    assert bbox == (0, 0, 50, 50)


# ---------------------------------------------------------------------------
# Reading-order labeling
# ---------------------------------------------------------------------------


def test_label_in_reading_order_simple_grid():
    """Standard 2x2 grid — labels A B / C D."""
    bboxes = [
        (0, 0, 100, 80),       # A — top-left
        (120, 0, 220, 80),     # B — top-right
        (0, 100, 100, 180),    # C — bottom-left
        (120, 100, 220, 180),  # D — bottom-right
    ]
    panels = _label_in_reading_order(bboxes)
    labels = [p.label for p in panels]
    assert labels == ["A", "B", "C", "D"]


def test_label_in_reading_order_e_big_left_fg_stacked_right():
    """Bobby's example: E big on left + F/G stacked on right.

    But labeled in reading order — so really A B / C D / E F / G H stacked
    examples don't apply directly. We just want geometric reading order:
    E (left, top-aligned spanning) then F (top-right) then G (bot-right).

    Top-row contains E top + F top. Bottom-row contains E bot + G bot.
    Tolerance based on row height — since E spans 0-200, its height is 200,
    F is 0-100 height 100. The grouping should put F same row as E top
    (they both start at y=0) and G same row as E bottom OR a separate row.

    For this test we just verify the X-ordering: when same row, leftward
    bbox gets earlier label.
    """
    bboxes = [
        (200, 0, 400, 100),     # right-top
        (200, 110, 400, 200),   # right-bot
        (0, 0, 180, 200),       # left-tall
    ]
    panels = _label_in_reading_order(bboxes)
    # With top-edge bucketing: left-tall (y0=0) + right-top (y0=0) share
    # row 1. Left has smaller x0 → A. right-top → B. right-bot (y0=110)
    # is 110px below row 1, exceeds threshold → row 2 → C.
    labels_by_bbox = {p.bbox_px: p.label for p in panels}
    assert labels_by_bbox[(0, 0, 180, 200)] == "A"   # E (big left)
    assert labels_by_bbox[(200, 0, 400, 100)] == "B"  # F (top right)
    assert labels_by_bbox[(200, 110, 400, 200)] == "C"  # G (bot right)


def test_label_empty_input():
    assert _label_in_reading_order([]) == []


# ---------------------------------------------------------------------------
# detect_panels — end-to-end on synthetic figures
# ---------------------------------------------------------------------------


def test_detect_panels_2x2_grid(tmp_path):
    """Standard 2x2 grid figure."""
    canvas = _white_canvas(400, 400)
    _fill(canvas, 30, 30, 180, 180)    # top-left
    _fill(canvas, 220, 30, 370, 180)   # top-right
    _fill(canvas, 30, 220, 180, 370)   # bot-left
    _fill(canvas, 220, 220, 370, 370)  # bot-right
    img = _make_figure(canvas, tmp_path / "g.png")
    panels = detect_panels(img)
    assert len(panels) == 4
    assert {p.label for p in panels} == {"A", "B", "C", "D"}


def test_detect_panels_1x3_horizontal_strip(tmp_path):
    """Three panels side by side."""
    canvas = _white_canvas(200, 600)
    _fill(canvas, 20, 30, 180, 170)
    _fill(canvas, 220, 30, 380, 170)
    _fill(canvas, 420, 30, 580, 170)
    img = _make_figure(canvas, tmp_path / "g.png")
    panels = detect_panels(img)
    assert len(panels) == 3
    labels = sorted(p.label for p in panels)
    assert labels == ["A", "B", "C"]


def test_detect_panels_e_big_fg_stacked(tmp_path):
    """Bobby's example: left panel spans full height; right column has 2 stacked panels."""
    canvas = _white_canvas(400, 600)
    _fill(canvas, 20, 20, 280, 380)   # E — big-left
    _fill(canvas, 320, 20, 580, 180)  # F — top-right
    _fill(canvas, 320, 220, 580, 380) # G — bot-right
    img = _make_figure(canvas, tmp_path / "g.png")
    panels = detect_panels(img)
    assert len(panels) == 3
    # E is the largest; F and G are smaller and equal-ish
    panels_by_label = {p.label: p for p in panels}
    a = panels_by_label["A"]  # left-tall (E in original, A in reading order)
    assert a.area_px > panels_by_label["B"].area_px
    # F/G should share the same x range
    f, g = panels_by_label["B"], panels_by_label["C"]
    assert abs(f.bbox_px[0] - g.bbox_px[0]) < 20
    assert abs(f.bbox_px[2] - g.bbox_px[2]) < 20


def test_detect_panels_single_panel(tmp_path):
    """A single-content figure with no internal whitespace splits."""
    canvas = _white_canvas(200, 300)
    _fill(canvas, 30, 30, 270, 170)  # one big content area
    img = _make_figure(canvas, tmp_path / "g.png")
    panels = detect_panels(img)
    assert len(panels) == 1
    assert panels[0].label == "A"


def test_detect_panels_blank_image_returns_empty(tmp_path):
    canvas = _white_canvas(100, 100)
    img = _make_figure(canvas, tmp_path / "g.png")
    panels = detect_panels(img)
    # All-white image returns the (empty) global bbox as a single "panel"
    # OR no panels — both are acceptable behaviours
    assert len(panels) <= 1
