"""Default theme — neutral, conference-friendly, large readable text.

Markdown sibling: ``default.md`` (visual rationale + screenshot reference).

Per the markdown-as-interface principle (Invariant 7), the theme's *style*
choices live in the .md doc; this Python file is the engine that exposes the
exact constants the renderer needs.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    """All settings the renderer needs to style a deck.

    Sizes are in EMU multiples or python-pptx Pt; the renderer handles the
    conversion.
    """

    name: str
    title_font: str
    body_font: str
    title_size_pt: int
    body_size_pt: int
    bullet_size_pt: int
    caption_size_pt: int
    title_color_rgb: tuple[int, int, int]
    body_color_rgb: tuple[int, int, int]
    bg_color_rgb: tuple[int, int, int]
    accent_color_rgb: tuple[int, int, int]


DEFAULT = Theme(
    name="default",
    title_font="Arial",
    body_font="Arial",
    title_size_pt=36,
    body_size_pt=20,
    bullet_size_pt=22,
    caption_size_pt=16,
    title_color_rgb=(20, 20, 20),
    body_color_rgb=(50, 50, 50),
    bg_color_rgb=(255, 255, 255),
    accent_color_rgb=(0, 102, 204),  # readable cobalt; contrast >= 7:1 on white
)


THEMES: dict[str, Theme] = {"default": DEFAULT}


def get_theme(name: str) -> Theme:
    """Look up a theme by name. Raises ``KeyError`` for unknown themes."""
    if name not in THEMES:
        raise KeyError(f"Unknown theme {name!r}. Available: {sorted(THEMES)}")
    return THEMES[name]


__all__ = ["DEFAULT", "THEMES", "Theme", "get_theme"]
