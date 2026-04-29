"""Tests for the slide deck data model + layout / theme registries.

Renderer tests that touch python-pptx are kept separate (test_render.py)
and marked slow.
"""

from __future__ import annotations

import pytest


class TestSlideValidation:
    def test_supported_layouts(self) -> None:
        from vaultlab.slides import Slide
        from vaultlab.slides.deck import SUPPORTED_LAYOUTS

        # Every supported layout instantiates cleanly
        for name in SUPPORTED_LAYOUTS:
            Slide(layout=name, title="x")

    def test_unsupported_layout_raises(self) -> None:
        from vaultlab.slides import Slide

        with pytest.raises(ValueError, match="Unsupported layout"):
            Slide(layout="not-a-layout")


class TestDeck:
    def test_add_appends_slide(self) -> None:
        from vaultlab.slides import Deck, Slide

        deck = Deck(title="my talk")
        deck.add(Slide(layout="title", title="hi"))
        deck.add(Slide(layout="content_with_bullets", title="part 2"))
        assert len(deck) == 2

    def test_default_theme(self) -> None:
        from vaultlab.slides import Deck

        assert Deck(title="x").theme == "default"


class TestLayouts:
    def test_get_layout_returns_spec_for_each_supported(self) -> None:
        from vaultlab.slides.deck import SUPPORTED_LAYOUTS
        from vaultlab.slides.layouts import get_layout

        for name in SUPPORTED_LAYOUTS:
            spec = get_layout(name)
            assert spec.name == name
            assert spec.title_box is not None
            # Each box has fractional coords in [0, 1]
            tb = spec.title_box
            assert 0.0 <= tb.x <= 1.0
            assert 0.0 <= tb.y <= 1.0

    def test_unknown_layout_raises(self) -> None:
        from vaultlab.slides.layouts import get_layout

        with pytest.raises(KeyError, match="Unknown layout"):
            get_layout("does-not-exist")

    def test_figure_layout_has_figure_box(self) -> None:
        from vaultlab.slides.layouts import get_layout

        spec = get_layout("figure_with_caption")
        assert spec.figure_box is not None


class TestThemes:
    def test_default_theme_has_required_fields(self) -> None:
        from vaultlab.slides.themes import get_theme

        theme = get_theme("default")
        assert theme.name == "default"
        assert theme.title_font
        assert theme.title_size_pt > 0
        assert len(theme.title_color_rgb) == 3
        for c in theme.title_color_rgb:
            assert 0 <= c <= 255

    def test_unknown_theme_raises(self) -> None:
        from vaultlab.slides.themes import get_theme

        with pytest.raises(KeyError):
            get_theme("missing")
