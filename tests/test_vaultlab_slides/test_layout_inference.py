"""Tests for vaultlab.slides.layout_inference."""

from __future__ import annotations

from unittest.mock import MagicMock

from vaultlab.slides.layout_inference import infer_slide_layout


_PIC = 13
_TXT = 17


def _shape(*, kind: int, l: float, t: float, w: float, h: float, text: str = ""):
    sh = MagicMock()
    sh.shape_type = kind
    sh.left = int(l * 914400)
    sh.top = int(t * 914400)
    sh.width = int(w * 914400)
    sh.height = int(h * 914400)
    sh.has_text_frame = (kind == _TXT)
    if kind == _TXT:
        sh.text_frame.text = text
    return sh


def _slide(shapes):
    s = MagicMock()
    s.shapes = shapes
    return s


SW, SH = int(13.33 * 914400), int(7.5 * 914400)


def test_no_picture_returns_none():
    s = _slide([_shape(kind=_TXT, l=0.5, t=0.3, w=12, h=1, text="title")])
    assert infer_slide_layout(s, SW, SH) is None


def test_figure_top_caption_br():
    """Figure on top spanning width; caption text in bottom-right corner."""
    s = _slide([
        _shape(kind=_TXT, l=0.5, t=0.3, w=12, h=1.2, text="title"),
        _shape(kind=_PIC, l=0.3, t=1.6, w=12.7, h=4.0),  # figure top, full width
        _shape(kind=_TXT, l=7.0, t=6.0, w=5.5, h=0.5, text="caption"),  # bottom-right
        _shape(kind=_TXT, l=7.0, t=7.0, w=5.5, h=0.4, text="cite"),
    ])
    assert infer_slide_layout(s, SW, SH) == "figure_top_caption_br"


def test_figure_with_side_caption():
    """Figure left ~60% width, full height; caption + bullets in right gutter."""
    s = _slide([
        _shape(kind=_TXT, l=0.5, t=0.3, w=12, h=1.2, text="title"),
        _shape(kind=_PIC, l=0.4, t=1.6, w=8.0, h=5.5),  # figure left, tall
        _shape(kind=_TXT, l=9.0, t=1.6, w=4.0, h=1.2, text="caption"),  # right gutter
        _shape(kind=_TXT, l=9.0, t=3.0, w=4.0, h=3.5, text="bullets"),
    ])
    assert infer_slide_layout(s, SW, SH) == "figure_with_side_caption"


def test_figure_above_bullets():
    """Figure top half full-width, bullets full-width below."""
    s = _slide([
        _shape(kind=_TXT, l=0.5, t=0.3, w=12, h=1.2, text="title"),
        _shape(kind=_PIC, l=0.5, t=1.6, w=12, h=3.5),  # top half
        _shape(kind=_TXT, l=0.5, t=5.5, w=12, h=2.0, text="bullets"),  # below
    ])
    assert infer_slide_layout(s, SW, SH) == "figure_above_bullets"


def test_figure_only():
    """Figure centered, no side or below text (other than tiny caption directly under)."""
    s = _slide([
        _shape(kind=_TXT, l=0.5, t=0.3, w=12, h=1.2, text="title"),
        _shape(kind=_PIC, l=2.5, t=1.6, w=8.0, h=5.5),  # centered horizontally
    ])
    assert infer_slide_layout(s, SW, SH) == "figure_only"


def test_default_figure_slide():
    """Figure left, bullets right, NOT full slide height (default figure_slide)."""
    s = _slide([
        _shape(kind=_TXT, l=0.5, t=0.3, w=12, h=1.2, text="title"),
        _shape(kind=_PIC, l=0.4, t=1.6, w=8.0, h=4.0),  # figure left, NOT full height
        _shape(kind=_TXT, l=9.0, t=1.9, w=4.0, h=4.5, text="bullets"),
    ])
    assert infer_slide_layout(s, SW, SH) == "default"
