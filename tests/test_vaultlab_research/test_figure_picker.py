"""Tests for vaultlab.research.figure_picker."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from vaultlab.research.figure_picker import pick_best_figure


def _mk_record(path: Path, w: int, h: int, min_dim: int | None = None) -> dict:
    """Build a fake figure-record dict matching extract_figures output."""
    return {
        "path": str(path),
        "page": 1,
        "figure_num": "1",
        "caption": "",
        "width_px": w,
        "height_px": h,
        "min_dimension": min_dim if min_dim is not None else min(w, h),
        "bbox": [0, 0, w, h],
    }


def test_picks_aspect_in_target_range_over_extreme(tmp_path):
    """Square figure beats sliver figure even when sliver is larger."""
    a = tmp_path / "a.png"; a.write_bytes(b"a" * 50_000)
    b = tmp_path / "b.png"; b.write_bytes(b"b" * 50_000)
    records = [
        _mk_record(a, 1000, 1000),  # aspect 1.0 — in range
        _mk_record(b, 200, 1500),   # aspect 0.13 — out of range, sliver
    ]
    with patch("vaultlab.research.figure_picker.extract_figures",
               return_value=records):
        pdf = tmp_path / "x.pdf"; pdf.write_bytes(b"fake")
        out = pick_best_figure(pdf, tmp_path)
    assert out == a


def test_picks_larger_when_both_in_aspect_range(tmp_path):
    """Among two slide-friendly figures, larger one wins."""
    a = tmp_path / "a.png"; a.write_bytes(b"a" * 50_000)
    b = tmp_path / "b.png"; b.write_bytes(b"b" * 50_000)
    records = [
        _mk_record(a, 800, 600, min_dim=600),
        _mk_record(b, 1500, 1200, min_dim=1200),
    ]
    with patch("vaultlab.research.figure_picker.extract_figures",
               return_value=records):
        pdf = tmp_path / "x.pdf"; pdf.write_bytes(b"fake")
        out = pick_best_figure(pdf, tmp_path)
    assert out == b


def test_panel_score_breaks_ties(tmp_path):
    """File-size bonus picks multi-panel figure over single-panel."""
    a = tmp_path / "a.png"; a.write_bytes(b"a" * 250_000)  # large = multi-panel
    b = tmp_path / "b.png"; b.write_bytes(b"b" * 50_000)   # small = single-panel
    records = [
        _mk_record(a, 1200, 900, min_dim=900),
        _mk_record(b, 1200, 900, min_dim=900),
    ]
    with patch("vaultlab.research.figure_picker.extract_figures",
               return_value=records):
        pdf = tmp_path / "x.pdf"; pdf.write_bytes(b"fake")
        out = pick_best_figure(pdf, tmp_path)
    assert out == a


def test_first_n_preference_breaks_ties(tmp_path):
    """Among equally-scored figures, prefer those among first N (main figures)."""
    a = tmp_path / "a.png"; a.write_bytes(b"a" * 50_000)
    b = tmp_path / "b.png"; b.write_bytes(b"b" * 50_000)
    records = [
        _mk_record(a, 1200, 900, min_dim=900),  # index 0
        _mk_record(b, 1200, 900, min_dim=900),  # index 1
    ]
    # Reverse the order — b first, a second — so we know first-N preference
    # depends on index
    records_reversed = records[::-1]
    with patch("vaultlab.research.figure_picker.extract_figures",
               return_value=records_reversed):
        pdf = tmp_path / "x.pdf"; pdf.write_bytes(b"fake")
        out = pick_best_figure(pdf, tmp_path, prefer_first_n=1)
    # b is at index 0 in records_reversed; should win on order
    assert out == b


def test_returns_none_when_no_figures(tmp_path):
    with patch("vaultlab.research.figure_picker.extract_figures",
               return_value=[]):
        pdf = tmp_path / "x.pdf"; pdf.write_bytes(b"fake")
        out = pick_best_figure(pdf, tmp_path)
    assert out is None


def test_returns_none_when_pdf_missing(tmp_path):
    out = pick_best_figure(tmp_path / "missing.pdf", tmp_path)
    assert out is None


def test_handles_extract_figures_exception(tmp_path):
    pdf = tmp_path / "x.pdf"; pdf.write_bytes(b"fake")
    with patch("vaultlab.research.figure_picker.extract_figures",
               side_effect=RuntimeError("boom")):
        out = pick_best_figure(pdf, tmp_path)
    assert out is None


def test_extreme_aspect_with_no_alternatives_still_returns(tmp_path):
    """If only sliver figures exist, return the best of those rather than None."""
    a = tmp_path / "a.png"; a.write_bytes(b"a" * 50_000)
    records = [_mk_record(a, 200, 1500)]
    with patch("vaultlab.research.figure_picker.extract_figures",
               return_value=records):
        pdf = tmp_path / "x.pdf"; pdf.write_bytes(b"fake")
        out = pick_best_figure(pdf, tmp_path)
    assert out == a  # better than nothing
