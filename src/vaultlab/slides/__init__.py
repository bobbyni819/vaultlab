"""vaultlab.slides - slide deck generation (file 08 of master plan).

Phase 8 of the file-05/file-08 build delivers the **core deck pipeline**:

- :class:`Slide`, :class:`Deck` - declarative data model independent of the
  rendering backend
- Three starter layouts (``title``, ``content_with_bullets``,
  ``figure_with_caption``) - declarative, markdown-readable; one ``.py`` +
  ``.md`` per layout per the markdown-as-interface principle
- One theme (``default``) - fonts, colors, sizes
- :func:`render_pptx` - write a ``.pptx`` via python-pptx

The four ``from_*`` entry points (``from_manuscript``, ``from_kb_page``,
``from_finding``, ``from_paper``), the figure-understanding pipeline, the
annotate primitives, and the additional themes / layouts are scaffolded as
future phases (8b-8d). They live as documented stubs so the structure is
visible to contributors today.

Examples
--------
>>> from vaultlab.slides import Deck, Slide, render_pptx
>>> deck = Deck(title="My talk", slides=[
...     Slide(layout="title", title="My talk", subtitle="Subtitle"),
...     Slide(layout="content_with_bullets", title="Outline",
...           bullets=["Background", "Methods", "Results"]),
... ])
>>> render_pptx(deck, "/tmp/out.pptx")  # doctest: +SKIP
"""

from __future__ import annotations

from vaultlab.slides.deck import (
    Deck,
    DeckPlan,
    DeckSlide,
    Slide,
    build_deck,
    build_deck_from_lineage_result,
)
from vaultlab.slides.render import RenderError, render_pptx

__all__ = [
    "Deck",
    "DeckPlan",
    "DeckSlide",
    "RenderError",
    "Slide",
    "build_deck",
    "build_deck_from_lineage_result",
    "render_pptx",
]
