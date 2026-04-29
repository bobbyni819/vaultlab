"""vaultlab.slides.layouts — declarative layout templates.

Phase-1 layouts:

- ``title`` — title + subtitle, centered
- ``content_with_bullets`` — H1 + bullet list (the workhorse for talks)
- ``figure_with_caption`` — figure on top, caption below

Per the markdown-as-interface principle (Invariant 7), each layout has both
``<name>.py`` (the renderer instructions) and a sibling ``<name>.md`` (visual
reference + contributor notes). Future phases add ``two_column``, ``quote``,
``section_divider``, and ~7 more layouts.
"""

from __future__ import annotations

from vaultlab.slides.layouts.registry import LAYOUTS, LayoutSpec, get_layout

__all__ = ["LAYOUTS", "LayoutSpec", "get_layout"]
