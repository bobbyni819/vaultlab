"""vaultlab.slides — slide deck generation.

Two coexisting deck-builder paths:

1. **Typed-DeckPlan path** (Phase 8 of the master plan): :class:`Slide` /
   :class:`Deck` / :class:`DeckSlide` / :class:`DeckPlan` data classes, the
   :func:`build_deck` composer that turns a typed plan into a ``.pptx``,
   plus :func:`build_deck_from_lineage_result` for ``/lit-arc`` decks.
   Backed by the declarative ``LayoutSpec`` registry and
   :func:`render_pptx`.

2. **Dict-plan path** (lifted from ``bobby_slides`` 2026-04):
   :func:`build_from_plan` accepts a flexible dict plan with eight slide
   types (``title`` / ``section_divider`` / ``figure`` / ``two_figure`` /
   ``multi_figure`` / ``quote`` / ``text`` / ``references``) and renders
   with the imperative lab-template primitives in
   :mod:`vaultlab.slides.layouts`. Use this when you have an LLM-driven
   or hand-authored plan and want richly-styled slides on the Hickey lab
   template.

Both paths share :class:`KBReader` (KB I/O), the speaker-notes formatter
in :mod:`vaultlab.slides.notes`, the OOXML animation engine in
:mod:`vaultlab.slides.animations`, and the figure-annotation overlay
primitives in :mod:`vaultlab.slides.annotate`.
"""

from __future__ import annotations

from vaultlab.slides.animations import (
    appear_on_click,
    appear_together_on_click,
    bullet_reveal,
    fade_on_click,
    panel_buildup,
)
from vaultlab.slides.annotate import add_annotations
from vaultlab.slides.deck import (
    Deck,
    DeckPlan,
    DeckSlide,
    Slide,
    build_deck,
    build_deck_from_lineage_result,
    build_from_plan,
)
from vaultlab.slides.kb_reader import KBNotFoundError, KBReader
from vaultlab.slides.layouts import (
    add_figure_above_bullets_slide,
    add_figure_only_slide,
    add_figure_slide,
    add_multi_figure_slide,
    add_quote_slide,
    add_references_slide,
    add_section_divider,
    add_text_slide,
    add_title_slide,
    add_two_figure_compare_slide,
)
from vaultlab.slides.marp import deck_plan_to_marp, write_marp
from vaultlab.slides.notes import (
    attach_to_slide,
    dual_format,
    format_speaker_notes,
    parse_speaker_notes,
)
from vaultlab.slides.render import RenderError, render_pptx
from vaultlab.slides.self_review import (
    ReviewReport,
    SlideReview,
    review_deck,
    write_review_report,
)
from vaultlab.slides.template import (
    default_font,
    lab_template_path,
    load_plain_presentation,
    load_template,
    min_sizes,
    theme_colors,
    theme_colors_hex,
)

__all__ = [
    # Typed deck data classes + composer
    "Deck",
    "DeckPlan",
    "DeckSlide",
    "RenderError",
    "ReviewReport",
    "Slide",
    "SlideReview",
    "build_deck",
    "build_deck_from_lineage_result",
    "render_pptx",
    "review_deck",
    "write_review_report",
    # Dict-plan-driven deck builder
    "build_from_plan",
    # KB reader
    "KBReader",
    "KBNotFoundError",
    # Imperative layout primitives
    "add_title_slide",
    "add_figure_slide",
    "add_figure_only_slide",
    "add_figure_above_bullets_slide",
    "add_two_figure_compare_slide",
    "add_quote_slide",
    "add_multi_figure_slide",
    "add_text_slide",
    "add_section_divider",
    "add_references_slide",
    # Speaker notes
    "format_speaker_notes",
    "parse_speaker_notes",
    "attach_to_slide",
    "dual_format",
    # Animations
    "appear_on_click",
    "appear_together_on_click",
    "fade_on_click",
    "bullet_reveal",
    "panel_buildup",
    # Annotations
    "add_annotations",
    # Marp mirror
    "deck_plan_to_marp",
    "write_marp",
    # Template + theme
    "load_template",
    "load_plain_presentation",
    "lab_template_path",
    "theme_colors",
    "theme_colors_hex",
    "default_font",
    "min_sizes",
]
