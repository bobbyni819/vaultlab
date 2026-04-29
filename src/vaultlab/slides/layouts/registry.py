"""Layout specs — declarative templates the renderer interprets.

Each ``LayoutSpec`` is a recipe: which fields of :class:`Slide` to read, where
to place them on the slide, what theme constants to apply.

Phase-1: three layouts (title / content_with_bullets / figure_with_caption).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TextBox:
    """Position + size of a text region on a slide.

    Coordinates are fractions of slide width / height (0.0 = top/left,
    1.0 = bottom/right). The renderer converts to EMU.
    """

    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class LayoutSpec:
    """Declarative layout — what to render where.

    Attributes
    ----------
    name
        Layout identifier; matches ``Slide.layout``.
    title_box
        Position of the title text.
    body_box
        Position of the main body (bullets, caption, or subtitle).
    figure_box
        Position of the figure region (only meaningful for figure layouts).
    """

    name: str
    title_box: TextBox
    body_box: TextBox | None = None
    figure_box: TextBox | None = None


# ---------------------------------------------------------------------------
# Layout registry
# ---------------------------------------------------------------------------


_TITLE = LayoutSpec(
    name="title",
    title_box=TextBox(x=0.10, y=0.30, width=0.80, height=0.20),
    body_box=TextBox(x=0.10, y=0.55, width=0.80, height=0.10),
)


_CONTENT_BULLETS = LayoutSpec(
    name="content_with_bullets",
    title_box=TextBox(x=0.06, y=0.06, width=0.88, height=0.12),
    body_box=TextBox(x=0.06, y=0.22, width=0.88, height=0.72),
)


_FIGURE_CAPTION = LayoutSpec(
    name="figure_with_caption",
    title_box=TextBox(x=0.06, y=0.04, width=0.88, height=0.10),
    figure_box=TextBox(x=0.10, y=0.16, width=0.80, height=0.62),
    body_box=TextBox(x=0.10, y=0.80, width=0.80, height=0.16),
)


LAYOUTS: dict[str, LayoutSpec] = {
    "title": _TITLE,
    "content_with_bullets": _CONTENT_BULLETS,
    "figure_with_caption": _FIGURE_CAPTION,
}


def get_layout(name: str) -> LayoutSpec:
    """Look up a layout by name. Raises ``KeyError`` for unknown layouts."""
    if name not in LAYOUTS:
        raise KeyError(f"Unknown layout {name!r}. Available: {sorted(LAYOUTS)}")
    return LAYOUTS[name]


__all__ = ["LAYOUTS", "LayoutSpec", "TextBox", "get_layout"]
