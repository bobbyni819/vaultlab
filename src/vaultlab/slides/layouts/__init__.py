"""vaultlab.slides.layouts — declarative layout templates + lifted primitives.

Two layers live here:

1. **Declarative LayoutSpec registry** (``registry.py``) — the original
   markdown-as-interface layout primitives (``title``,
   ``content_with_bullets``, ``figure_with_caption``). Used by the
   simple :func:`vaultlab.slides.render_pptx` renderer.

2. **Lab-template imperative primitives** (``title.py``, ``figure.py``,
   ``multi_figure.py``, ``text.py``, ``section_divider.py``,
   ``references.py``) — lifted from ``bobby_slides._layout`` (2026-04).
   Used by :func:`vaultlab.slides.deck.build_from_plan` for richly-styled
   decks that load the Hickey Lab template.

Both layers coexist: the declarative ``LayoutSpec`` model is great for
data-driven decks, the imperative primitives are great for content-aware
plan-driven decks where layout choice depends on slide intent.
"""

from __future__ import annotations

from vaultlab.slides.layouts.acknowledgments_grid import (
    add_acknowledgments_grid_slide,
)
from vaultlab.slides.layouts.comparison_table import add_comparison_table_slide
from vaultlab.slides.layouts.equation import add_equation_slide
from vaultlab.slides.layouts.figure import (
    add_figure_above_bullets_slide,
    add_figure_only_slide,
    add_figure_slide,
    add_quote_slide,
    add_two_figure_compare_slide,
)
from vaultlab.slides.layouts.multi_figure import add_multi_figure_slide
from vaultlab.slides.layouts.references import add_references_slide
from vaultlab.slides.layouts.registry import LAYOUTS, LayoutSpec, get_layout
from vaultlab.slides.layouts.section_divider import add_section_divider
from vaultlab.slides.layouts.table import add_table_slide
from vaultlab.slides.layouts.text import add_text_slide
from vaultlab.slides.layouts.title import add_title_slide

__all__ = [
    "LAYOUTS",
    "LayoutSpec",
    "add_acknowledgments_grid_slide",
    "add_comparison_table_slide",
    "add_equation_slide",
    "add_figure_above_bullets_slide",
    "add_figure_only_slide",
    "add_figure_slide",
    "add_multi_figure_slide",
    "add_quote_slide",
    "add_references_slide",
    "add_section_divider",
    "add_table_slide",
    "add_text_slide",
    "add_title_slide",
    "add_two_figure_compare_slide",
    "get_layout",
]
