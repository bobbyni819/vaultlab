"""Slide and Deck data classes — declarative deck representation.

Backend-independent. The renderer (``vaultlab.slides.render``) is the only
module that talks to ``python-pptx``; everything else operates on these
dataclasses.

This module also hosts the **higher-level multi-slide composer** —
:class:`DeckSlide`, :class:`DeckPlan`, :func:`build_deck`, and
:func:`build_deck_from_lineage_result`. The composer wraps the low-level
``Slide``/``Deck``/``render_pptx`` pipeline plus the annotated-figure-slide
primitive into a single function that turns a structured "deck plan"
(title / section_intro / figure / bullets / references slides) into a
finished ``.pptx``. It is the prerequisite for the L4 e2e test that turns
a ``run_lit_arc`` corpus into a journal-club deck.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vaultlab.figures.understand.models import ElementAnnotation
    from vaultlab.research.lineage import LineageRunResult

logger = logging.getLogger(__name__)

# Layout names supported by the starter layouts module
SUPPORTED_LAYOUTS: frozenset[str] = frozenset(
    {"title", "content_with_bullets", "figure_with_caption"}
)


@dataclass
class Slide:
    """One slide in a deck.

    Fields are deliberately layout-agnostic — each layout reads only the fields
    it needs. Unused fields are ignored.

    Attributes
    ----------
    layout
        Layout name from ``SUPPORTED_LAYOUTS``.
    title
        Slide title (rendered as the H1 of the slide).
    subtitle
        Subtitle for ``title`` layout. Ignored elsewhere.
    bullets
        Bullet-list content for ``content_with_bullets``.
    figure_path
        Path to a ``.png`` / ``.jpg`` for ``figure_with_caption``. Resolved
        relative to ``Deck.working_dir`` if not absolute.
    caption
        Caption text for ``figure_with_caption``.
    speaker_notes
        Optional speaker notes (rendered into the .pptx notes panel).
    """

    layout: str
    title: str = ""
    subtitle: str = ""
    bullets: list[str] = field(default_factory=list)
    figure_path: str | None = None
    caption: str = ""
    speaker_notes: str = ""

    def __post_init__(self) -> None:
        if self.layout not in SUPPORTED_LAYOUTS:
            raise ValueError(
                f"Unsupported layout {self.layout!r}. Supported: {sorted(SUPPORTED_LAYOUTS)}"
            )


@dataclass
class Deck:
    """A complete slide deck.

    Attributes
    ----------
    title
        Deck title (used in the .pptx properties + as a default for the
        opening title slide).
    slides
        Ordered list of slides.
    theme
        Theme name. Defaults to ``"default"``.
    working_dir
        Used to resolve relative ``figure_path`` values.
    metadata
        Free-form provenance attached to the deck — kept in the file
        properties (``vaultlab_provenance`` key when supported by the backend).
    """

    title: str
    slides: list[Slide] = field(default_factory=list)
    theme: str = "default"
    working_dir: Path | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    def add(self, slide: Slide) -> None:
        """Append a slide. Useful for building decks programmatically."""
        self.slides.append(slide)

    def __len__(self) -> int:  # convenience
        return len(self.slides)


# ---------------------------------------------------------------------------
# Multi-slide composer (DeckSlide / DeckPlan / build_deck)
# ---------------------------------------------------------------------------

# Slide kinds the composer understands. These are higher-level than the
# layout names above — a single composer kind may pick one of several
# concrete renderers (e.g. ``figure`` uses the annotated-figure primitive).
SUPPORTED_DECK_SLIDE_KINDS: frozenset[str] = frozenset(
    {"title", "section_intro", "figure", "bullets", "references"}
)


@dataclass(frozen=True)
class DeckSlide:
    """One slide spec for the multi-slide composer.

    The ``content`` dict is interpreted per-kind:

    - ``title`` — ``{"subtitle": str, "speaker": str, "affiliation": str,
      "date": str}``
    - ``section_intro`` — ``{"section_name": str, "key_question": str,
      "bullets": list[str]}`` (1-3 bullets)
    - ``figure`` — ``{"figure_path": Path | str, "annotations":
      list[ElementAnnotation], "motif_colors": dict[str, tuple[int,int,int]],
      "caption": str, "citation_doi": str}``
    - ``bullets`` — ``{"bullets": list[str], "citations": list[str]}``
      (citations are DOI strings rendered as ``[N]`` markers)
    - ``references`` — ``{"refs": list[dict]}`` where each dict is
      ``{"n": int, "citation": str, "doi": str}``

    Unused keys per-kind are ignored — the dict shape is intentionally
    permissive so callers can pass extra context without breaking.
    """

    kind: str
    title: str
    content: dict[str, Any] = field(default_factory=dict)
    notes: str = ""

    def __post_init__(self) -> None:
        if self.kind not in SUPPORTED_DECK_SLIDE_KINDS:
            raise ValueError(
                f"Unsupported DeckSlide kind {self.kind!r}. "
                f"Supported: {sorted(SUPPORTED_DECK_SLIDE_KINDS)}"
            )


@dataclass(frozen=True)
class DeckPlan:
    """Full deck structure consumed by :func:`build_deck`."""

    title: str
    subtitle: str
    speaker: str
    affiliation: str
    sections: list[str] = field(default_factory=list)
    slides: list[DeckSlide] = field(default_factory=list)
    theme: str = "hickey_lab"


def build_deck(
    plan: DeckPlan,
    output_path: Path | str,
    *,
    citations: dict[str, dict[str, Any]] | None = None,
) -> Path:
    """Compose a multi-slide ``.pptx`` from a :class:`DeckPlan`.

    Slide-by-slide dispatch:

    - ``title`` / ``section_intro`` / ``bullets`` / ``references`` are
      rendered with python-pptx text primitives directly (these don't need
      annotation magic — bullets and headings are fine in plain text boxes).
    - ``figure`` slides delegate to
      :func:`vaultlab.slides.annotated_figure_slide.add_annotated_figure_slide`.

    Theming:

    - ``plan.theme == "hickey_lab"`` initialises the presentation from the
      bundled Hickey Lab template (preserves logos, color theme, masters)
      and uses the ``HICKEY_LAB_LAYOUT`` for figure slides.
    - Any other theme falls back to a vanilla 16:9 presentation with the
      ``DEFAULT`` layout.

    Returns the written ``.pptx`` path.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    citations = citations or {}

    # Lazy imports — keep the dataclass module light when callers only need
    # the data shapes (e.g. unit tests that inspect a DeckPlan).
    from pptx import Presentation
    from pptx.util import Inches

    from vaultlab.slides.annotated_figure_slide import (
        DEFAULT,
        HICKEY_LAB_LAYOUT,
        SlideLayout,
        add_annotated_figure_slide,
    )

    if plan.theme == "hickey_lab":
        try:
            from vaultlab.slides.themes.hickey_lab import (
                load_hickey_lab_presentation,
            )

            pres = load_hickey_lab_presentation(theme="dark")
            layout: SlideLayout = HICKEY_LAB_LAYOUT
        except FileNotFoundError:
            logger.warning(
                "Hickey Lab template not bundled; falling back to default theme."
            )
            pres = Presentation()
            pres.slide_width = Inches(13.333)
            pres.slide_height = Inches(7.5)
            layout = DEFAULT
    else:
        pres = Presentation()
        pres.slide_width = Inches(13.333)
        pres.slide_height = Inches(7.5)
        layout = DEFAULT

    for idx, ds in enumerate(plan.slides):
        page_number = idx + 1
        section_idx = _current_section_idx(ds, plan.sections)
        if ds.kind == "title":
            _add_title_slide(pres, ds, plan, layout)
        elif ds.kind == "section_intro":
            _add_section_intro_slide(pres, ds, layout)
        elif ds.kind == "bullets":
            _add_bullets_slide(
                pres,
                ds,
                layout,
                page_number=page_number,
                sections=plan.sections,
                section_idx=section_idx,
                citations=citations,
            )
        elif ds.kind == "figure":
            _add_figure_slide(
                pres,
                ds,
                layout,
                page_number=page_number,
                sections=plan.sections,
                section_idx=section_idx,
                add_fn=add_annotated_figure_slide,
            )
        elif ds.kind == "references":
            _add_references_slide(pres, ds, layout)
        else:  # pragma: no cover — guarded by DeckSlide.__post_init__
            raise ValueError(f"Unknown DeckSlide kind: {ds.kind}")

    pres.save(str(output_path))
    return output_path


def build_deck_from_lineage_result(
    lineage_result: LineageRunResult,
    *,
    speaker: str,
    affiliation: str = "Hickey Lab @ Duke BME",
    project_slug: str | None = None,
    figure_assignments: dict[str, Path] | None = None,
    kb_root: Path,
) -> Path:
    """Take a ``/lit-arc`` result and synthesize a ~7-slide deck.

    Reads each per-paper summary's frontmatter to recover ``year_bucket``,
    then composes:

    1. Title (lineage topic)
    2. Section intro: Background
    3. Figure (history bucket) — IF a figure assignment exists for a
       history-bucket DOI; otherwise dropped and replaced with bullets.
    4. Section intro: Development
    5. Bullets: SOTA findings — TL;DR snippets from sota-bucket papers
    6. Section intro: Synthesis — pulled from the arc narrative when
       available; otherwise a stub instructing the user to fill it in.
    7. References — Vancouver-style 2-column

    Output is routed through :func:`vaultlab.kb.paths.deck_path` so the
    .pptx lands at ``<kb_root>/Output/<project>/<topic>-deck.pptx``.
    """
    from vaultlab.kb.paths import deck_path, slugify_topic

    plan = _plan_from_lineage(
        lineage_result,
        speaker=speaker,
        affiliation=affiliation,
        figure_assignments=figure_assignments or {},
    )
    project = project_slug or "lit-arc"
    deck_name = f"{slugify_topic(lineage_result.topic)}-deck.pptx"
    out = deck_path(Path(kb_root), project, deck_name)
    out.parent.mkdir(parents=True, exist_ok=True)
    return build_deck(plan, out, citations=_collect_citations_from_summaries(lineage_result))


# ---------------------------------------------------------------------------
# Internal: per-kind slide builders
# ---------------------------------------------------------------------------


def _current_section_idx(ds: DeckSlide, sections: list[str]) -> int | None:
    """Find which section a section_intro slide belongs to (for banner highlight)."""
    if ds.kind != "section_intro":
        return None
    name = ds.content.get("section_name", "")
    if name in sections:
        return sections.index(name)
    return None


def _add_title_slide(pres, ds: DeckSlide, plan: DeckPlan, layout) -> None:
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN
    from pptx.util import Inches, Pt

    from vaultlab.slides.annotated_figure_slide import (
        text_color_for_theme,
        muted_text_color_for_theme,
    )

    blank = pres.slide_layouts[6]
    s = pres.slides.add_slide(blank)

    # Big centered title
    box = s.shapes.add_textbox(
        Inches(0.5),
        Inches(2.5),
        Inches(layout.slide_w_in - 1.0),
        Inches(1.5),
    )
    box.name = "title_main"
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = ds.title or plan.title
    r.font.name = "Arial"
    r.font.size = Pt(40)
    r.font.bold = True
    r.font.color.rgb = RGBColor(*text_color_for_theme(layout.theme_variant))

    subtitle = ds.content.get("subtitle") or plan.subtitle
    speaker = ds.content.get("speaker") or plan.speaker
    affiliation = ds.content.get("affiliation") or plan.affiliation
    date_str = ds.content.get("date", "")

    sub_lines = [x for x in (subtitle, speaker, affiliation, date_str) if x]
    if sub_lines:
        sub = s.shapes.add_textbox(
            Inches(0.5),
            Inches(4.2),
            Inches(layout.slide_w_in - 1.0),
            Inches(2.5),
        )
        sub.name = "title_subtitle"
        tf2 = sub.text_frame
        tf2.word_wrap = True
        for i, line in enumerate(sub_lines):
            para = tf2.paragraphs[0] if i == 0 else tf2.add_paragraph()
            para.alignment = PP_ALIGN.CENTER
            run = para.add_run()
            run.text = line
            run.font.name = "Arial"
            run.font.size = Pt(20 if i == 0 else 16)
            run.font.color.rgb = RGBColor(*muted_text_color_for_theme(layout.theme_variant))

    if ds.notes:
        s.notes_slide.notes_text_frame.text = ds.notes


def _add_section_intro_slide(pres, ds: DeckSlide, layout) -> None:
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN
    from pptx.util import Inches, Pt

    from vaultlab.slides.annotated_figure_slide import (
        text_color_for_theme,
        muted_text_color_for_theme,
    )

    blank = pres.shapes if False else pres.slide_layouts[6]  # noqa: invariant
    s = pres.slides.add_slide(pres.slide_layouts[6])

    section_name = ds.content.get("section_name", "")
    key_question = ds.content.get("key_question", "")
    bullets = list(ds.content.get("bullets", []))[:3]

    # Section name (small, top)
    if section_name:
        sn = s.shapes.add_textbox(
            Inches(0.6),
            Inches(0.5),
            Inches(layout.slide_w_in - 1.2),
            Inches(0.6),
        )
        sn.name = "section_name"
        tf = sn.text_frame
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        r = p.add_run()
        r.text = section_name.upper()
        r.font.name = "Arial"
        r.font.size = Pt(14)
        r.font.bold = True
        r.font.color.rgb = RGBColor(0, 102, 204)

    # Title
    title_box = s.shapes.add_textbox(
        Inches(0.6),
        Inches(1.2),
        Inches(layout.slide_w_in - 1.2),
        Inches(1.5),
    )
    title_box.name = "section_title"
    ttf = title_box.text_frame
    ttf.word_wrap = True
    p = ttf.paragraphs[0]
    r = p.add_run()
    r.text = ds.title
    r.font.name = "Arial"
    r.font.size = Pt(34)
    r.font.bold = True
    r.font.color.rgb = RGBColor(*text_color_for_theme(layout.theme_variant))

    # Key question
    if key_question:
        kq = s.shapes.add_textbox(
            Inches(0.6),
            Inches(2.9),
            Inches(layout.slide_w_in - 1.2),
            Inches(0.9),
        )
        kq.name = "section_key_question"
        ktf = kq.text_frame
        ktf.word_wrap = True
        p = ktf.paragraphs[0]
        r = p.add_run()
        r.text = key_question
        r.font.name = "Arial"
        r.font.size = Pt(20)
        r.font.italic = True
        r.font.color.rgb = RGBColor(*muted_text_color_for_theme(layout.theme_variant))

    # Bullets
    if bullets:
        bb = s.shapes.add_textbox(
            Inches(0.8),
            Inches(4.0),
            Inches(layout.slide_w_in - 1.6),
            Inches(2.8),
        )
        bb.name = "section_bullets"
        btf = bb.text_frame
        btf.word_wrap = True
        for i, b in enumerate(bullets):
            para = btf.paragraphs[0] if i == 0 else btf.add_paragraph()
            run = para.add_run()
            run.text = f"•  {b}"
            run.font.name = "Arial"
            run.font.size = Pt(20)
            run.font.color.rgb = RGBColor(*text_color_for_theme(layout.theme_variant))

    if ds.notes:
        s.notes_slide.notes_text_frame.text = ds.notes


def _add_bullets_slide(
    pres,
    ds: DeckSlide,
    layout,
    *,
    page_number: int,
    sections: list[str],
    section_idx: int | None,
    citations: dict[str, dict[str, Any]],
) -> None:
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN
    from pptx.util import Inches, Pt

    from vaultlab.slides.annotated_figure_slide import (
        text_color_for_theme,
        muted_text_color_for_theme,
        _add_page_number,
        _add_section_banner,
    )

    s = pres.slides.add_slide(pres.slide_layouts[6])

    # Title
    tbox = s.shapes.add_textbox(
        Inches(0.4),
        Inches(0.15),
        Inches(layout.slide_w_in - 0.8),
        Inches(layout.title_h_in - 0.1),
    )
    tbox.name = "slide_title"
    tf = tbox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = ds.title
    r.font.name = "Arial"
    r.font.size = Pt(layout.title_font_pt)
    r.font.bold = True
    r.font.color.rgb = RGBColor(*text_color_for_theme(layout.theme_variant))

    bullets = list(ds.content.get("bullets", []))
    cite_dois = list(ds.content.get("citations", []))

    bb = s.shapes.add_textbox(
        Inches(0.8),
        Inches(layout.title_h_in + 0.3),
        Inches(layout.slide_w_in - 1.6),
        Inches(layout.slide_h_in - layout.title_h_in - layout.footer_h_in - 0.5),
    )
    bb.name = "slide_bullets"
    btf = bb.text_frame
    btf.word_wrap = True
    for i, b in enumerate(bullets):
        para = btf.paragraphs[0] if i == 0 else btf.add_paragraph()
        run = para.add_run()
        run.text = f"•  {b}"
        run.font.name = "Arial"
        run.font.size = Pt(22)
        run.font.color.rgb = RGBColor(*text_color_for_theme(layout.theme_variant))

    # Citations footnote line
    if cite_dois:
        labels = []
        for n, doi in enumerate(cite_dois, 1):
            cite = citations.get(doi)
            if cite and cite.get("authors"):
                first = cite["authors"][0].split()[0] if cite["authors"] else "Anon"
                year = cite.get("year", "")
                labels.append(f"[{n}] {first} {year}".strip())
            else:
                labels.append(f"[{n}] {doi}")
        cb = s.shapes.add_textbox(
            Inches(0.8),
            Inches(layout.slide_h_in - layout.footer_h_in - 0.5),
            Inches(layout.slide_w_in - 1.6),
            Inches(0.4),
        )
        cb.name = "slide_citations_footer"
        ctf = cb.text_frame
        ctf.word_wrap = True
        p = ctf.paragraphs[0]
        run = p.add_run()
        run.text = "  ".join(labels)
        run.font.name = "Arial"
        run.font.size = Pt(10)
        run.font.italic = True
        run.font.color.rgb = RGBColor(*muted_text_color_for_theme(layout.theme_variant))

    _add_page_number(s, page_number, layout)
    if sections:
        _add_section_banner(s, sections=sections, current_idx=section_idx, layout=layout)

    if ds.notes:
        s.notes_slide.notes_text_frame.text = ds.notes


def _add_figure_slide(
    pres,
    ds: DeckSlide,
    layout,
    *,
    page_number: int,
    sections: list[str],
    section_idx: int | None,
    add_fn,
) -> None:
    figure_path = ds.content.get("figure_path")
    if figure_path is None:
        raise ValueError(
            f"figure-kind DeckSlide '{ds.title}' missing figure_path; "
            "use build_deck_from_lineage_result for graceful fallback."
        )
    annotations = list(ds.content.get("annotations", []))
    motif_colors = ds.content.get("motif_colors") or {}
    caption = ds.content.get("caption", "")

    add_fn(
        pres,
        image_path=figure_path,
        annotations=annotations,
        title=ds.title,
        caption=caption,
        motif_colors=motif_colors,
        layout=layout,
        notes=ds.notes,
        page_number=page_number,
        sections=sections or None,
        current_section_idx=section_idx,
    )


def _add_references_slide(pres, ds: DeckSlide, layout) -> None:
    """Vancouver-style references in two columns."""
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN
    from pptx.util import Inches, Pt

    from vaultlab.slides.annotated_figure_slide import (
        text_color_for_theme,
        muted_text_color_for_theme,
    )

    s = pres.slides.add_slide(pres.slide_layouts[6])

    # Title
    tbox = s.shapes.add_textbox(
        Inches(0.4),
        Inches(0.15),
        Inches(layout.slide_w_in - 0.8),
        Inches(layout.title_h_in - 0.1),
    )
    tbox.name = "slide_title"
    tf = tbox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = ds.title or "References"
    r.font.name = "Arial"
    r.font.size = Pt(layout.title_font_pt)
    r.font.bold = True
    r.font.color.rgb = RGBColor(*text_color_for_theme(layout.theme_variant))

    refs = list(ds.content.get("refs", []))
    if not refs:
        return

    # Two columns
    col_w = (layout.slide_w_in - 1.2) / 2.0
    col_h = layout.slide_h_in - layout.title_h_in - 0.5
    col_y = layout.title_h_in + 0.2

    half = (len(refs) + 1) // 2
    cols = [refs[:half], refs[half:]]

    for ci, col in enumerate(cols):
        cb = s.shapes.add_textbox(
            Inches(0.6 + ci * (col_w + 0.2)),
            Inches(col_y),
            Inches(col_w),
            Inches(col_h),
        )
        cb.name = f"refs_col_{ci}"
        ctf = cb.text_frame
        ctf.word_wrap = True
        for i, ref in enumerate(col):
            para = ctf.paragraphs[0] if i == 0 else ctf.add_paragraph()
            n = ref.get("n", "?")
            citation = ref.get("citation", "")
            doi = ref.get("doi", "")
            text = f"[{n}] {citation}"
            if doi:
                text += f"  doi:{doi}"
            run = para.add_run()
            run.text = text
            run.font.name = "Arial"
            run.font.size = Pt(11)
            run.font.color.rgb = RGBColor(*text_color_for_theme(layout.theme_variant))

    if ds.notes:
        s.notes_slide.notes_text_frame.text = ds.notes


# ---------------------------------------------------------------------------
# Internal: lineage-result -> DeckPlan
# ---------------------------------------------------------------------------


def _plan_from_lineage(
    lineage_result: LineageRunResult,
    *,
    speaker: str,
    affiliation: str,
    figure_assignments: dict[str, Path],
) -> DeckPlan:
    """Pure-Python composer (no LLM call) that turns a lineage result into a DeckPlan."""
    from datetime import date as _date

    from vaultlab.slides.notes import dual_format

    # Read summaries from disk if they exist; fall back gracefully when not.
    summaries = _read_summary_frontmatters(lineage_result.summary_paths)
    bucketed = _bucket_by_year(summaries)
    arc_text = _read_arc_narrative(lineage_result.arc_path)

    sections = ["Background", "Development", "Synthesis", "References"]
    slides: list[DeckSlide] = []

    # 1. Title
    slides.append(
        DeckSlide(
            kind="title",
            title=f"Lineage: {lineage_result.topic}",
            content={
                "subtitle": "Journal-club deck",
                "speaker": speaker,
                "affiliation": affiliation,
                "date": _date.today().isoformat(),
            },
            notes=dual_format(
                mental_map={
                    "hook": f"Today we trace the lineage of {lineage_result.topic}.",
                    "key_claim": (
                        f"This corpus has {lineage_result.corpus_size} papers; "
                        f"we'll walk through history, development, and the SOTA."
                    ),
                    "transition": "Let's start with the foundational work.",
                },
                detailed_script=(
                    f"Hello, I'm {speaker}, and today I'm presenting a "
                    f"lineage view of {lineage_result.topic}. The corpus assembled "
                    f"by /lit-arc covers {lineage_result.corpus_size} papers, "
                    f"of which {lineage_result.pdfs_acquired} have full-text "
                    f"PDFs available. We'll move from history through "
                    f"development to the state of the art."
                ),
            ),
        )
    )

    # 2. Section intro: Background
    history_papers = bucketed.get("history", [])
    history_bullets = [_one_line_label(s) for s in history_papers[:3]]
    slides.append(
        DeckSlide(
            kind="section_intro",
            title="Background",
            content={
                "section_name": "Background",
                "key_question": (
                    f"What foundational work established {lineage_result.topic}?"
                ),
                "bullets": history_bullets or ["(no history-bucket papers in corpus)"],
            },
            notes=dual_format(
                mental_map={
                    "key_claim": "These are the OG papers everyone cites.",
                    "transition": "Now let's see how the field evolved.",
                }
            ),
        )
    )

    # 3. Figure or bullets — history bucket
    history_figure = _pick_figure_for_bucket(history_papers, figure_assignments)
    if history_figure is not None:
        fig_doi, fig_path = history_figure
        slides.append(
            DeckSlide(
                kind="figure",
                title=f"Foundational result — {_label_for_doi(summaries, fig_doi)}",
                content={
                    "figure_path": fig_path,
                    "annotations": [],
                    "motif_colors": {},
                    "caption": _summary_caption(summaries.get(fig_doi)),
                    "citation_doi": fig_doi,
                },
                notes=dual_format(
                    mental_map={
                        "hook": "Look at this canonical figure.",
                        "evidence": f"Figure from {_label_for_doi(summaries, fig_doi)}",
                    }
                ),
            )
        )
    else:
        # Drop the figure slide; replace with bullets from history TL;DRs
        slides.append(
            DeckSlide(
                kind="bullets",
                title="Foundational findings",
                content={
                    "bullets": [
                        _bullet_from_summary(s)
                        for s in history_papers[:5]
                    ] or ["(no history-bucket summaries available)"],
                    "citations": [
                        s.get("doi", "") for s in history_papers[:5] if s.get("doi")
                    ],
                },
                notes=dual_format(
                    mental_map={
                        "key_claim": "These are the foundational findings.",
                    }
                ),
            )
        )

    # 4. Section intro: Development
    slides.append(
        DeckSlide(
            kind="section_intro",
            title="Development",
            content={
                "section_name": "Development",
                "key_question": "How did the field evolve?",
                "bullets": [
                    _one_line_label(s) for s in bucketed.get("development", [])[:3]
                ] or ["(no development-bucket papers in corpus)"],
            },
        )
    )

    # 5. Bullets: SOTA findings
    sota_papers = bucketed.get("sota", [])
    sota_bullets = [_bullet_from_summary(s) for s in sota_papers[:5]]
    sota_dois = [s.get("doi", "") for s in sota_papers[:5] if s.get("doi")]
    slides.append(
        DeckSlide(
            kind="bullets",
            title="State of the art",
            content={
                "bullets": sota_bullets or ["(no SOTA-bucket findings available)"],
                "citations": sota_dois,
            },
            notes=dual_format(
                mental_map={
                    "key_claim": "Here's where the field stands today.",
                    "transition": "Let's pull it together.",
                }
            ),
        )
    )

    # 6. Section intro: Synthesis (use arc narrative when present)
    synthesis_bullets = _arc_bullets(arc_text) if arc_text else [
        "(synthesis pending — re-run /lit-arc with ANTHROPIC_API_KEY for narrative)"
    ]
    slides.append(
        DeckSlide(
            kind="section_intro",
            title="Synthesis",
            content={
                "section_name": "Synthesis",
                "key_question": "What's the through-line?",
                "bullets": synthesis_bullets,
            },
        )
    )

    # 7. References
    refs = _build_references(summaries)
    slides.append(
        DeckSlide(
            kind="references",
            title="References",
            content={"refs": refs},
        )
    )

    return DeckPlan(
        title=f"Lineage: {lineage_result.topic}",
        subtitle="Journal-club deck",
        speaker=speaker,
        affiliation=affiliation,
        sections=sections,
        slides=slides,
        theme="hickey_lab",
    )


# ---------------------------------------------------------------------------
# Internal: read summary frontmatter / arc text
# ---------------------------------------------------------------------------


def _read_summary_frontmatters(
    summary_paths: dict[str, Path],
) -> dict[str, dict[str, Any]]:
    """Parse YAML frontmatter from each Wiki/Summaries/<doi>.md file.

    Returns ``{doi: {fm_dict, plus 'tldr', 'key_findings' parsed from body}}``.
    Missing files are skipped silently — the caller falls back to bullets.
    """
    import yaml

    out: dict[str, dict[str, Any]] = {}
    for doi, path in summary_paths.items():
        if not path or not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        # Frontmatter block between '---' delimiters
        if not text.startswith("---"):
            out[doi] = {"doi": doi}
            continue
        end = text.find("\n---", 3)
        if end == -1:
            out[doi] = {"doi": doi}
            continue
        try:
            fm = yaml.safe_load(text[3:end]) or {}
        except yaml.YAMLError:
            fm = {}
        body = text[end + 4:]
        # Extract TL;DR (first non-empty line under "## TL;DR")
        tldr = _extract_section(body, "## TL;DR")
        findings = _extract_bullet_section(body, "## Key findings")
        rec = {"doi": doi, **fm, "tldr": tldr, "key_findings": findings}
        out[doi] = rec
    return out


def _extract_section(body: str, heading: str) -> str:
    """Return text under ``heading`` until the next ``## `` heading, stripped."""
    import re

    pat = re.compile(
        rf"^{re.escape(heading)}\s*\n(.*?)(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pat.search(body)
    if not m:
        return ""
    return m.group(1).strip()


def _extract_bullet_section(body: str, heading: str) -> list[str]:
    text = _extract_section(body, heading)
    if not text:
        return []
    return [
        line[2:].strip()
        for line in text.splitlines()
        if line.startswith("- ") and "_(none)_" not in line
    ][:5]


def _bucket_by_year(
    summaries: dict[str, dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {
        "history": [],
        "development": [],
        "sota": [],
        "unknown": [],
    }
    for s in summaries.values():
        bucket = s.get("year_bucket", "unknown")
        out.setdefault(bucket, []).append(s)
    # Sort each bucket by year ascending
    for k in out:
        out[k].sort(key=lambda d: d.get("year", 0) or 0)
    return out


def _read_arc_narrative(arc_path: Path) -> str:
    if not arc_path or not arc_path.exists():
        return ""
    try:
        return arc_path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _arc_bullets(arc_text: str) -> list[str]:
    """Pull a few non-empty paragraph snippets from the arc to seed Synthesis."""
    bullets: list[str] = []
    for line in arc_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith(">"):
            continue
        if stripped.startswith("|") or stripped.startswith("---"):
            continue
        if stripped.startswith("- "):
            continue
        # Take first sentence
        first_period = stripped.find(". ")
        if first_period > 30:
            bullets.append(stripped[:first_period + 1])
        else:
            bullets.append(stripped[:200])
        if len(bullets) >= 3:
            break
    return bullets


def _one_line_label(summary: dict[str, Any]) -> str:
    authors = summary.get("authors") or []
    first = authors[0].split()[0] if authors and authors[0] else "Anon"
    year = summary.get("year") or "n.d."
    title = summary.get("title", "") or summary.get("doi", "")
    short = title if len(title) <= 70 else title[:67] + "..."
    return f"{first} {year} — {short}"


def _label_for_doi(summaries: dict[str, dict[str, Any]], doi: str) -> str:
    s = summaries.get(doi)
    if not s:
        return doi
    return _one_line_label(s)


def _summary_caption(summary: dict[str, Any] | None) -> str:
    if not summary:
        return ""
    tldr = (summary.get("tldr") or "").strip()
    if tldr:
        return tldr.split("\n")[0][:200]
    return ""


def _bullet_from_summary(summary: dict[str, Any]) -> str:
    findings = summary.get("key_findings") or []
    if findings:
        return findings[0][:200]
    tldr = (summary.get("tldr") or "").strip()
    if tldr:
        return tldr.split("\n")[0][:200]
    return _one_line_label(summary)


def _pick_figure_for_bucket(
    bucket_papers: list[dict[str, Any]],
    figure_assignments: dict[str, Path],
) -> tuple[str, Path] | None:
    """Return (doi, path) for the first paper in the bucket with a figure."""
    for s in bucket_papers:
        doi = (s.get("doi") or "").strip()
        if not doi:
            continue
        path = figure_assignments.get(doi)
        if path is not None and Path(path).exists():
            return doi, Path(path)
    return None


def _build_references(summaries: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for n, (doi, s) in enumerate(
        sorted(
            summaries.items(),
            key=lambda kv: (kv[1].get("year", 0) or 0, kv[0]),
        ),
        start=1,
    ):
        authors = s.get("authors") or []
        if authors:
            if len(authors) > 3:
                authors_part = ", ".join(authors[:3]) + ", et al."
            else:
                authors_part = ", ".join(authors)
        else:
            authors_part = "Anon."
        title = s.get("title", "") or "(no title)"
        year = s.get("year", "") or ""
        journal = s.get("journal", "") or ""
        citation = f"{authors_part} {title}. {journal} {year}.".strip()
        refs.append({"n": n, "citation": citation, "doi": doi})
    return refs


def _collect_citations_from_summaries(
    lineage_result: LineageRunResult,
) -> dict[str, dict[str, Any]]:
    summaries = _read_summary_frontmatters(lineage_result.summary_paths)
    return {
        doi: {
            "title": s.get("title", ""),
            "authors": s.get("authors", []) or [],
            "year": s.get("year", ""),
            "journal": s.get("journal", ""),
        }
        for doi, s in summaries.items()
    }
