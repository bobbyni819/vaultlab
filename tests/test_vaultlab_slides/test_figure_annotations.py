"""Tests for vaultlab.slides.figure_annotations."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from vaultlab.slides.figure_annotations import (
    ANNOTATION_COLORS,
    DEFAULT_MOTIFS,
    auto_annotate_figure,
)


def _mk_region(motif_name: str, bbox: tuple[int, int, int, int]):
    """Build a fake Region object matching the figures.understand model."""
    from vaultlab.figures.understand import Region
    return Region(motif_name=motif_name, bbox_px=bbox, area_px=1, centroid_px=(0, 0))


def test_returns_empty_when_image_missing(tmp_path):
    out = auto_annotate_figure(tmp_path / "nope.png")
    assert out == []


def test_translates_pixel_bbox_to_fractional(tmp_path):
    """Regions in pixel coords should come out as fractional bboxes."""
    from PIL import Image
    img = tmp_path / "x.png"
    Image.new("RGB", (1000, 500), (255, 255, 255)).save(img)

    fake_regions = [
        _mk_region("red-callout", (100, 50, 600, 250)),  # x: 0.1-0.6, y: 0.1-0.5
    ]
    with (
        patch("vaultlab.slides.figure_annotations.extract_regions",
              return_value=fake_regions),
        patch("vaultlab.slides.figure_annotations.merge_regions",
              return_value=fake_regions),
    ):
        anns = auto_annotate_figure(img)
    assert len(anns) == 1
    bbox = anns[0]["bbox"]
    assert bbox[0] == pytest.approx(0.1, rel=0.01)
    assert bbox[1] == pytest.approx(0.1, rel=0.01)
    assert bbox[2] == pytest.approx(0.6, rel=0.01)
    assert bbox[3] == pytest.approx(0.5, rel=0.01)


def test_default_color_per_motif(tmp_path):
    from PIL import Image
    img = tmp_path / "x.png"
    Image.new("RGB", (100, 100), (255, 255, 255)).save(img)

    fake_regions = [
        _mk_region("red-callout", (10, 10, 50, 50)),
        _mk_region("yellow-callout", (60, 10, 90, 50)),
    ]
    with (
        patch("vaultlab.slides.figure_annotations.extract_regions",
              return_value=fake_regions),
        patch("vaultlab.slides.figure_annotations.merge_regions",
              return_value=fake_regions),
    ):
        anns = auto_annotate_figure(img)
    colors = [a["color"] for a in anns]
    assert ANNOTATION_COLORS["red-callout"] in colors
    assert ANNOTATION_COLORS["yellow-callout"] in colors


def test_caps_at_max_regions(tmp_path):
    from PIL import Image
    img = tmp_path / "x.png"
    Image.new("RGB", (1000, 1000), (255, 255, 255)).save(img)

    fake_regions = [
        _mk_region("red-callout", (i*10, 0, i*10 + 50, 100))
        for i in range(20)
    ]
    with (
        patch("vaultlab.slides.figure_annotations.extract_regions",
              return_value=fake_regions),
        patch("vaultlab.slides.figure_annotations.merge_regions",
              return_value=fake_regions),
    ):
        anns = auto_annotate_figure(img, max_regions=3)
    assert len(anns) == 3


def test_sorts_by_area_largest_first(tmp_path):
    """Largest region should come first in the output."""
    from PIL import Image
    img = tmp_path / "x.png"
    Image.new("RGB", (1000, 1000), (255, 255, 255)).save(img)

    small = _mk_region("red-callout", (0, 0, 100, 100))     # area 10k
    large = _mk_region("red-callout", (200, 200, 600, 600)) # area 160k
    fake_regions = [small, large]  # in size-ascending order
    with (
        patch("vaultlab.slides.figure_annotations.extract_regions",
              return_value=fake_regions),
        patch("vaultlab.slides.figure_annotations.merge_regions",
              return_value=fake_regions),
    ):
        anns = auto_annotate_figure(img)
    # First annotation should be from the LARGE region
    bbox = anns[0]["bbox"]
    assert bbox[0] == pytest.approx(0.2, rel=0.01)


def test_attaches_click_indices(tmp_path):
    """Each annotation gets a click_index for build-up animation."""
    from PIL import Image
    img = tmp_path / "x.png"
    Image.new("RGB", (1000, 1000), (255, 255, 255)).save(img)

    fake_regions = [_mk_region("red-callout", (0, 0, 100, 100))]
    with (
        patch("vaultlab.slides.figure_annotations.extract_regions",
              return_value=fake_regions),
        patch("vaultlab.slides.figure_annotations.merge_regions",
              return_value=fake_regions),
    ):
        anns = auto_annotate_figure(img, bullet_click_indices=[5])
    assert anns[0]["click_index"] == 5


def test_returns_empty_on_extract_exception(tmp_path):
    from PIL import Image
    img = tmp_path / "x.png"
    Image.new("RGB", (100, 100), (255, 255, 255)).save(img)

    with patch(
        "vaultlab.slides.figure_annotations.extract_regions",
        side_effect=RuntimeError("boom"),
    ):
        anns = auto_annotate_figure(img)
    assert anns == []
