"""Tests for vaultlab.figures.crop_panel + trim_margins."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from vaultlab.figures.crop_panel import crop_to_panel, crop_to_panels
from vaultlab.figures.trim_margins import trim_white_margin


def _build_grid_figure(tmp_path: Path) -> Path:
    """4-panel grid: A top-left, B top-right, C bot-left, D bot-right."""
    canvas = np.full((400, 400), 255, dtype=np.uint8)
    canvas[30:180, 30:180] = 50    # A
    canvas[30:180, 220:370] = 50   # B
    canvas[220:370, 30:180] = 50   # C
    canvas[220:370, 220:370] = 50  # D
    p = tmp_path / "grid.png"
    Image.fromarray(canvas, mode="L").save(p)
    return p


def test_crop_to_panel_returns_path(tmp_path):
    src = _build_grid_figure(tmp_path)
    out = crop_to_panel(src, "B")
    assert out is not None
    assert out.exists()
    assert "panel-B" in out.name


def test_crop_to_panel_case_insensitive(tmp_path):
    src = _build_grid_figure(tmp_path)
    out = crop_to_panel(src, "b")
    assert out is not None
    # Output filename normalises to uppercase
    assert "panel-B" in out.name


def test_crop_to_panel_unknown_label_returns_none(tmp_path):
    src = _build_grid_figure(tmp_path)
    out = crop_to_panel(src, "Z")
    assert out is None


def test_crop_to_panel_idempotent(tmp_path):
    src = _build_grid_figure(tmp_path)
    out1 = crop_to_panel(src, "A")
    out2 = crop_to_panel(src, "A")
    assert out1 == out2
    assert out1.exists()


def test_crop_to_panel_crops_correct_region(tmp_path):
    src = _build_grid_figure(tmp_path)
    out = crop_to_panel(src, "A", margin_px=0)
    assert out is not None
    # Panel A is at (30,30)-(180,180) — width 150, height 150
    cropped = Image.open(out)
    assert 140 <= cropped.size[0] <= 160
    assert 140 <= cropped.size[1] <= 160


def test_crop_to_panel_missing_source_returns_none(tmp_path):
    out = crop_to_panel(tmp_path / "missing.png", "A")
    assert out is None


def test_crop_to_panels_batch(tmp_path):
    src = _build_grid_figure(tmp_path)
    out = crop_to_panels(src, ["A", "B", "Z"])
    assert "A" in out and "B" in out
    assert "Z" not in out  # unknown panel skipped silently


# --- trim_white_margin ---


def test_trim_white_margin_strips_padding(tmp_path):
    """Image with white padding around content gets cropped to content."""
    canvas = np.full((400, 600), 255, dtype=np.uint8)
    # Content only in the middle: x 100-500, y 50-350
    canvas[50:350, 100:500] = 50
    src = tmp_path / "padded.png"
    Image.fromarray(canvas, mode="L").save(src)
    out = trim_white_margin(src, margin_keep_px=0)
    assert out is not None
    cropped = Image.open(out)
    # Should be ~400x300
    assert 380 <= cropped.size[0] <= 410
    assert 280 <= cropped.size[1] <= 310


def test_trim_white_margin_preserves_when_no_margin(tmp_path):
    """When figure already fills its bounds, return original path."""
    canvas = np.full((100, 100), 50, dtype=np.uint8)
    src = tmp_path / "tight.png"
    Image.fromarray(canvas, mode="L").save(src)
    out = trim_white_margin(src)
    # Should return the original (no trim needed)
    assert out == src


def test_trim_white_margin_idempotent(tmp_path):
    canvas = np.full((400, 600), 255, dtype=np.uint8)
    canvas[50:350, 100:500] = 50
    src = tmp_path / "padded.png"
    Image.fromarray(canvas, mode="L").save(src)
    out1 = trim_white_margin(src)
    out2 = trim_white_margin(src)
    assert out1 == out2


def test_trim_white_margin_missing_source_returns_none(tmp_path):
    assert trim_white_margin(tmp_path / "missing.png") is None
