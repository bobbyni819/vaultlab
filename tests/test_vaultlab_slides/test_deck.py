"""Tests for the slide deck data model + layout / theme registries.

Renderer tests that touch python-pptx are kept separate (test_render.py)
and marked slow.
"""

from __future__ import annotations

from pathlib import Path

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


# ---------------------------------------------------------------------------
# Multi-slide composer (build_deck / build_deck_from_lineage_result)
# ---------------------------------------------------------------------------


@pytest.fixture
def pptx() -> object:
    """Skip composer tests when python-pptx isn't installed."""
    try:
        import pptx  # type: ignore[import-not-found]

        return pptx
    except ImportError:
        pytest.skip("python-pptx not installed")


@pytest.fixture
def synthetic_png(tmp_path):
    """Create a small RGB PNG so figure-slide tests have a real image."""
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("Pillow not installed")
    img = Image.new("RGB", (640, 480), color=(80, 120, 200))
    p = tmp_path / "synthetic.png"
    img.save(p)
    return p


class TestDeckSlideValidation:
    def test_supported_kinds_instantiate(self) -> None:
        from vaultlab.slides import DeckSlide
        from vaultlab.slides.deck import SUPPORTED_DECK_SLIDE_KINDS

        for kind in SUPPORTED_DECK_SLIDE_KINDS:
            DeckSlide(kind=kind, title="x")

    def test_unsupported_kind_raises(self) -> None:
        from vaultlab.slides import DeckSlide

        with pytest.raises(ValueError, match="Unsupported DeckSlide kind"):
            DeckSlide(kind="not-a-kind", title="x")


class TestBuildDeckMinimal:
    def test_build_deck_minimal_default_theme(self, tmp_path, pptx) -> None:
        """Title + bullets + references, default theme — verify slide count."""
        from pptx import Presentation

        from vaultlab.slides import DeckPlan, DeckSlide, build_deck

        plan = DeckPlan(
            title="My talk",
            subtitle="A talk",
            speaker="Bobby Ni",
            affiliation="Hickey Lab",
            sections=[],
            slides=[
                DeckSlide(
                    kind="title",
                    title="My talk",
                    content={"subtitle": "A talk", "speaker": "Bobby Ni"},
                ),
                DeckSlide(
                    kind="bullets",
                    title="Outline",
                    content={"bullets": ["Background", "Methods", "Results"]},
                ),
                DeckSlide(
                    kind="references",
                    title="References",
                    content={
                        "refs": [
                            {"n": 1, "citation": "Smith 2020. Nature.", "doi": "10.1/x"},
                            {"n": 2, "citation": "Doe 2021. Cell.", "doi": "10.2/y"},
                        ]
                    },
                ),
            ],
            theme="default",
        )

        out = build_deck(plan, tmp_path / "deck.pptx")
        assert out.exists()
        assert out.stat().st_size > 0

        pres = Presentation(str(out))
        assert len(pres.slides) == 3

    def test_build_deck_with_speaker_notes(self, tmp_path, pptx) -> None:
        from pptx import Presentation

        from vaultlab.slides import DeckPlan, DeckSlide, build_deck

        plan = DeckPlan(
            title="t",
            subtitle="s",
            speaker="b",
            affiliation="h",
            slides=[
                DeckSlide(
                    kind="title",
                    title="Hi",
                    content={},
                    notes="HOOK: open strong",
                ),
            ],
            theme="default",
        )
        out = build_deck(plan, tmp_path / "x.pptx")
        pres = Presentation(str(out))
        assert "HOOK" in pres.slides[0].notes_slide.notes_text_frame.text


class TestBuildDeckFigure:
    def test_build_deck_with_figure_slide(self, tmp_path, pptx, synthetic_png) -> None:
        """Use a real PNG, verify annotated-figure slide rendered."""
        from pptx import Presentation

        from vaultlab.figures.understand.models import ElementAnnotation
        from vaultlab.slides import DeckPlan, DeckSlide, build_deck

        plan = DeckPlan(
            title="t",
            subtitle="s",
            speaker="b",
            affiliation="h",
            sections=["Background"],
            slides=[
                DeckSlide(
                    kind="figure",
                    title="My figure",
                    content={
                        "figure_path": synthetic_png,
                        "annotations": [
                            ElementAnnotation(
                                label="Region A",
                                bbox_px=(100, 100, 200, 200),
                                motif_name="motif_a",
                            ),
                        ],
                        "motif_colors": {"motif_a": (200, 50, 50)},
                        "caption": "test caption",
                    },
                ),
            ],
            theme="default",
        )
        out = build_deck(plan, tmp_path / "fig_deck.pptx")
        pres = Presentation(str(out))
        assert len(pres.slides) == 1
        # Verify the annotated-figure slide actually populated shape names
        names = {sh.name for sh in pres.slides[0].shapes}
        assert "slide_title" in names
        assert any(n.startswith("ann1") for n in names)


class TestBuildDeckFromLineageResult:
    def test_build_deck_from_synthetic_lineage(self, tmp_path, pptx) -> None:
        """Synthetic LineageRunResult + summaries → composed deck."""
        from pptx import Presentation

        from vaultlab.kb.paths import slugify_doi
        from vaultlab.research.lineage import LineageRunResult
        from vaultlab.slides import build_deck_from_lineage_result

        kb_root = tmp_path / "kb"
        # Write three synthetic summaries: one per bucket
        summary_paths: dict[str, Path] = {}
        for doi, year, bucket, title in [
            ("10.1/history-paper", 1995, "history", "Foundational discovery"),
            ("10.1/development-paper", 2010, "development", "Evolution of the field"),
            ("10.1/sota-paper", 2024, "sota", "State of the art today"),
        ]:
            slug = slugify_doi(doi)
            p = kb_root / "Wiki" / "Summaries" / f"{slug}.md"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(
                f"---\n"
                f"doi: {doi}\n"
                f"title: {title}\n"
                f"authors: [Smith J]\n"
                f"year: {year}\n"
                f"journal: TestJournal\n"
                f"year_bucket: {bucket}\n"
                f"tier: A\n"
                f"---\n"
                f"\n## TL;DR\nThis is the {bucket} TL;DR for {title}.\n"
                f"\n## Key findings (with [page] provenance)\n"
                f"- Finding one for {bucket} [p1]\n"
                f"- Finding two [p2]\n",
                encoding="utf-8",
            )
            summary_paths[doi] = p

        # Synthetic arc file
        arc_path = kb_root / "Wiki" / "Concepts" / "test-topic-lineage-2026-04-29.md"
        arc_path.parent.mkdir(parents=True, exist_ok=True)
        arc_path.write_text(
            "---\ntopic: test\n---\n\n# Lineage: test\n\n"
            "The history of the field starts with foundational work. "
            "Development accelerated in the 2010s. "
            "Today the SOTA is dominated by deep learning approaches.\n",
            encoding="utf-8",
        )

        result = LineageRunResult(
            topic="test topic",
            arc_path=arc_path,
            summary_paths=summary_paths,
            search_log_path=Path(),
            corpus_size=3,
            pdfs_acquired=2,
            summaries_written=3,
            duration_seconds=0.0,
        )

        out = build_deck_from_lineage_result(
            result,
            speaker="Bobby Ni",
            kb_root=kb_root,
        )
        assert out.exists()
        # Routed via deck_path
        assert "Output" in out.parts
        pres = Presentation(str(out))
        # 7 slides: title + section_intro(bg) + bullets/figure + section_intro(dev)
        # + bullets(sota) + section_intro(synth) + references
        assert len(pres.slides) == 7

    def test_build_deck_skips_missing_figures(self, tmp_path, pptx) -> None:
        """When figure_assignments is empty, figure slot becomes bullets fallback."""
        from pptx import Presentation

        from vaultlab.kb.paths import slugify_doi
        from vaultlab.research.lineage import LineageRunResult
        from vaultlab.slides import build_deck_from_lineage_result

        kb_root = tmp_path / "kb"
        doi = "10.1/h"
        slug = slugify_doi(doi)
        p = kb_root / "Wiki" / "Summaries" / f"{slug}.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            f"---\ndoi: {doi}\ntitle: T\nauthors: [Smith J]\nyear: 1990\n"
            f"journal: J\nyear_bucket: history\ntier: A\n---\n\n"
            f"## TL;DR\nFoundation.\n\n"
            f"## Key findings (with [page] provenance)\n- Finding [p1]\n",
            encoding="utf-8",
        )
        arc = kb_root / "Wiki" / "Concepts" / "x-lineage-2026.md"
        arc.parent.mkdir(parents=True, exist_ok=True)
        arc.write_text("# Arc\n\nNarrative paragraph here.\n", encoding="utf-8")

        result = LineageRunResult(
            topic="x",
            arc_path=arc,
            summary_paths={doi: p},
            corpus_size=1,
        )

        # No figure_assignments — figure slide MUST become a bullets slide
        out = build_deck_from_lineage_result(
            result, speaker="B", kb_root=kb_root, figure_assignments={},
        )
        pres = Presentation(str(out))
        # Inspect the third slide (history slot) — should be a bullets slide,
        # not a figure slide. We detect by checking shape names: figure slides
        # have ann*_box / ann*_marker shapes; bullets have slide_bullets.
        names_per_slide = [
            {sh.name for sh in s.shapes} for s in pres.slides
        ]
        # The "Foundational findings" slide is index 2
        assert "slide_bullets" in names_per_slide[2]


class TestReferencesSlideFormatting:
    def test_references_slide_two_columns(self, tmp_path, pptx) -> None:
        """Verify the references slide builds two columns."""
        from pptx import Presentation

        from vaultlab.slides import DeckPlan, DeckSlide, build_deck

        # Build a references slide with 6 entries — should split 3/3
        refs = [
            {"n": i, "citation": f"Author {i} 202{i}. J{i}.", "doi": f"10.1/{i}"}
            for i in range(1, 7)
        ]
        plan = DeckPlan(
            title="t",
            subtitle="s",
            speaker="b",
            affiliation="h",
            slides=[
                DeckSlide(
                    kind="references",
                    title="References",
                    content={"refs": refs},
                ),
            ],
            theme="default",
        )
        out = build_deck(plan, tmp_path / "refs.pptx")
        pres = Presentation(str(out))
        assert len(pres.slides) == 1
        names = {sh.name for sh in pres.slides[0].shapes}
        # Two ref columns must exist
        assert "refs_col_0" in names
        assert "refs_col_1" in names
