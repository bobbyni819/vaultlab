"""Tests for vaultlab.figures.understand - color motifs, region merging, render."""

from __future__ import annotations

from pathlib import Path

import pytest

# Skip the whole module when figure deps aren't installed (CI installs only [dev]).
np = pytest.importorskip("numpy")
pytest.importorskip("PIL")
pytest.importorskip("skimage")

from PIL import Image

# ---------------------------------------------------------------------------
# Synthetic image helpers — predictable color regions for deterministic tests
# ---------------------------------------------------------------------------


def _make_synthetic_figure(tmp_path: Path) -> Path:
    """Create a 400x400 figure with 3 known colored squares + a background.

    Layout:
        - white background
        - 50x50 neon-green square at (100, 100)
        - 50x50 neon-green square at (250, 100)  (so we can test merging)
        - 50x50 electric-blue square at (100, 250)
        - 50x50 orange square at (250, 250)
    """
    img = np.full((400, 400, 3), 255, dtype=np.uint8)  # white
    img[100:150, 100:150] = (50, 230, 50)  # neon green
    img[100:150, 250:300] = (50, 230, 50)  # neon green
    img[250:300, 100:150] = (40, 100, 230)  # electric blue
    img[250:300, 250:300] = (230, 130, 30)  # orange

    path = tmp_path / "synthetic.png"
    Image.fromarray(img).save(path)
    return path


# ---------------------------------------------------------------------------
# ColorMotif + extract_regions
# ---------------------------------------------------------------------------


class TestExtractRegions:
    def test_finds_two_green_squares(self, tmp_path: Path) -> None:
        from vaultlab.figures.understand import ColorMotif, extract_regions

        path = _make_synthetic_figure(tmp_path)
        motif = ColorMotif("green", (90, 145), 0.40, 0.40, 0.0001)
        regions = extract_regions(path, [motif])
        assert len(regions) == 2
        for r in regions:
            assert r.motif_name == "green"
            x0, y0, x1, y1 = r.bbox_px
            # Each square is ~50x50
            assert 40 <= (x1 - x0) <= 60
            assert 40 <= (y1 - y0) <= 60

    def test_finds_blue_square(self, tmp_path: Path) -> None:
        from vaultlab.figures.understand import ColorMotif, extract_regions

        path = _make_synthetic_figure(tmp_path)
        motif = ColorMotif("blue", (200, 240), 0.30, 0.30, 0.0001)
        regions = extract_regions(path, [motif])
        assert len(regions) == 1
        assert regions[0].motif_name == "blue"

    def test_finds_orange_square(self, tmp_path: Path) -> None:
        from vaultlab.figures.understand import ColorMotif, extract_regions

        path = _make_synthetic_figure(tmp_path)
        motif = ColorMotif("orange", (15, 40), 0.45, 0.45, 0.0001)
        regions = extract_regions(path, [motif])
        assert len(regions) == 1

    def test_multiple_motifs_combined(self, tmp_path: Path) -> None:
        from vaultlab.figures.understand import ColorMotif, extract_regions

        path = _make_synthetic_figure(tmp_path)
        motifs = [
            ColorMotif("green", (90, 145), 0.40, 0.40, 0.0001),
            ColorMotif("blue", (200, 240), 0.30, 0.30, 0.0001),
            ColorMotif("orange", (15, 40), 0.45, 0.45, 0.0001),
        ]
        regions = extract_regions(path, motifs)
        # 2 green + 1 blue + 1 orange
        assert len(regions) == 4
        names = [r.motif_name for r in regions]
        assert names.count("green") == 2
        assert names.count("blue") == 1
        assert names.count("orange") == 1

    def test_no_match_returns_empty(self, tmp_path: Path) -> None:
        from vaultlab.figures.understand import ColorMotif, extract_regions

        path = _make_synthetic_figure(tmp_path)
        # Pure red — not in the synthetic image
        motif = ColorMotif("red-only", (350, 360), 0.80, 0.80, 0.0001)
        assert extract_regions(path, [motif]) == []

    def test_min_area_filters_small_components(self, tmp_path: Path) -> None:
        from vaultlab.figures.understand import ColorMotif, extract_regions

        path = _make_synthetic_figure(tmp_path)
        # min_area_frac too high → excludes 50x50 (2500 px) since image has 160000 px;
        # 0.05 * 160000 = 8000 px > 2500
        motif = ColorMotif("green", (90, 145), 0.40, 0.40, 0.05)
        assert extract_regions(path, [motif]) == []


# ---------------------------------------------------------------------------
# merge_regions
# ---------------------------------------------------------------------------


class TestMergeRegions:
    def test_merges_close_same_motif_regions(self, tmp_path: Path) -> None:
        from vaultlab.figures.understand import (
            ColorMotif,
            extract_regions,
            merge_regions,
        )

        path = _make_synthetic_figure(tmp_path)
        # Two green squares 100px apart — high dilation should merge them
        motif = ColorMotif("green", (90, 145), 0.40, 0.40, 0.0001)
        regions = extract_regions(path, [motif])
        assert len(regions) == 2
        merged = merge_regions(regions, dilation_px=200)
        assert len(merged) == 1

    def test_does_not_merge_different_motifs(self, tmp_path: Path) -> None:
        from vaultlab.figures.understand import (
            ColorMotif,
            extract_regions,
            merge_regions,
        )

        path = _make_synthetic_figure(tmp_path)
        motifs = [
            ColorMotif("green", (90, 145), 0.40, 0.40, 0.0001),
            ColorMotif("blue", (200, 240), 0.30, 0.30, 0.0001),
        ]
        regions = extract_regions(path, motifs)
        # Even with massive dilation, blue + green stay separate
        merged = merge_regions(regions, dilation_px=500)
        names = sorted(r.motif_name for r in merged)
        assert names == ["blue", "green"]

    def test_preserves_separation_when_dilation_small(self, tmp_path: Path) -> None:
        from vaultlab.figures.understand import (
            ColorMotif,
            extract_regions,
            merge_regions,
        )

        path = _make_synthetic_figure(tmp_path)
        motif = ColorMotif("green", (90, 145), 0.40, 0.40, 0.0001)
        regions = extract_regions(path, [motif])
        # Squares are ~100px apart edge-to-edge; dilation 5 should NOT merge
        merged = merge_regions(regions, dilation_px=5)
        assert len(merged) == 2

    def test_merged_bbox_unions_inputs(self, tmp_path: Path) -> None:
        from vaultlab.figures.understand import (
            ColorMotif,
            extract_regions,
            merge_regions,
        )

        path = _make_synthetic_figure(tmp_path)
        motif = ColorMotif("green", (90, 145), 0.40, 0.40, 0.0001)
        regions = extract_regions(path, [motif])
        merged = merge_regions(regions, dilation_px=200)
        assert len(merged) == 1
        x0, y0, x1, y1 = merged[0].bbox_px
        # Should span both green squares
        assert x0 <= 100 and x1 >= 300
        assert y0 <= 100 and y1 >= 150


# ---------------------------------------------------------------------------
# render_debug_overlay + render_annotated_figure
# ---------------------------------------------------------------------------


class TestRenderDebugOverlay:
    def test_writes_output_png(self, tmp_path: Path) -> None:
        from vaultlab.figures.understand import (
            ColorMotif,
            extract_regions,
            render_debug_overlay,
        )

        path = _make_synthetic_figure(tmp_path)
        motif = ColorMotif("green", (90, 145), 0.40, 0.40, 0.0001)
        regions = extract_regions(path, [motif])
        out = render_debug_overlay(path, regions, tmp_path / "debug.png")
        assert out.exists()
        assert out.stat().st_size > 0

    def test_handles_empty_regions(self, tmp_path: Path) -> None:
        from vaultlab.figures.understand import render_debug_overlay

        path = _make_synthetic_figure(tmp_path)
        out = render_debug_overlay(path, [], tmp_path / "empty.png")
        assert out.exists()


class TestRenderAnnotatedFigure:
    def test_writes_annotated_png(self, tmp_path: Path) -> None:
        from vaultlab.figures.understand import ElementAnnotation
        from vaultlab.figures.understand.render import render_annotated_figure

        path = _make_synthetic_figure(tmp_path)
        annotations = [
            ElementAnnotation(
                label="Green square (left)",
                bbox_px=(100, 100, 150, 150),
                explanation="x",
                motif_name="green",
            ),
            ElementAnnotation(
                label="Blue square",
                bbox_px=(100, 250, 150, 300),
                explanation="x",
                motif_name="blue",
            ),
        ]
        out = render_annotated_figure(path, annotations, tmp_path / "ann.png")
        assert out.exists()
        # Output is wider than original (gutter added)
        out_img = Image.open(out)
        in_img = Image.open(path)
        assert out_img.width > in_img.width
        assert out_img.height == in_img.height

    def test_handles_zero_annotations(self, tmp_path: Path) -> None:
        from vaultlab.figures.understand.render import render_annotated_figure

        path = _make_synthetic_figure(tmp_path)
        out = render_annotated_figure(path, [], tmp_path / "zero.png")
        assert out.exists()


# ---------------------------------------------------------------------------
# ElementAnnotation
# ---------------------------------------------------------------------------


class TestElementAnnotation:
    def test_construction(self) -> None:
        from vaultlab.figures.understand import ElementAnnotation

        ann = ElementAnnotation(
            label="Test",
            bbox_px=(10, 20, 30, 40),
            explanation="why",
            motif_name="green",
            confidence=0.8,
        )
        assert ann.label == "Test"
        assert ann.bbox_px == (10, 20, 30, 40)
        assert ann.confidence == 0.8

    def test_defaults(self) -> None:
        from vaultlab.figures.understand import ElementAnnotation

        ann = ElementAnnotation(label="x", bbox_px=(0, 0, 1, 1))
        assert ann.explanation == ""
        assert ann.motif_name == ""
        assert ann.confidence == 0.0
