"""Tests for :mod:`vaultlab.slides.self_review` — composite deck review pass.

Builds tiny test decks via :func:`vaultlab.slides.build_from_plan` and the
typed-Deck path, then runs :func:`vaultlab.slides.self_review.review_deck`
to assert the audits flag (or don't flag) the expected issues.
"""

from __future__ import annotations

from pathlib import Path

import pytest

PIL = pytest.importorskip("PIL")
pptx_mod = pytest.importorskip("pptx")

from PIL import Image
from pptx import Presentation as PptxPresentation
from pptx.util import Inches, Pt

from vaultlab.slides import build_from_plan
from vaultlab.slides.self_review import (
    ReviewReport,
    SlideReview,
    render_review_html,
    review_deck,
    write_review_report,
)
from vaultlab.slides.template import lab_template_path


pytestmark = pytest.mark.skipif(
    lab_template_path() is None,
    reason="Hickey Lab template not bundled — self_review tests need build_from_plan",
)


def _make_image(path: Path, color: str = "red") -> Path:
    Image.new("RGB", (200, 150), color).save(str(path))
    return path


# ---------------------------------------------------------------------------
# Helpers — build a known-good deck and a known-bad deck
# ---------------------------------------------------------------------------


@pytest.fixture
def good_deck(tmp_path: Path) -> Path:
    """A 5-slide deck that should pass every audit."""
    fig = _make_image(tmp_path / "good_fig.png", "green")
    plan = {
        "title": "Solid Deck",
        "author": "Test Author",
        "slides": [
            {
                "type": "title",
                "title": "Solid Deck",
                "subtitle": "All audits should pass",
                "author": "Test Author",
            },
            {"type": "section_divider", "title": "Background"},
            {
                "type": "figure",
                "title": "Spatial transcriptomics maps cell types in tissue",
                "image_path": str(fig),
                "caption": "Composite immunofluorescence",
                "bullets": ["Captures spatial context", "Resolves cell neighborhoods"],
                "citation_source": "Pentimalli et al., 2025",
            },
            {
                "type": "text",
                "title": "Three findings emerge from the spatial analysis",
                "bullets": ["Finding one with evidence", "Finding two with evidence"],
            },
            {
                "type": "references",
                "title": "References",
                "references": ["Pentimalli et al., 2025"],
            },
        ],
    }
    out = tmp_path / "good_deck.pptx"
    build_from_plan(plan, out, write_marp=False)
    return out


@pytest.fixture
def tiny_title_deck(tmp_path: Path) -> Path:
    """Synthetic deck with an intentionally too-small title font (8pt).

    Built directly via python-pptx (not build_from_plan, which enforces
    the hard rules) so we can introduce the violation deterministically.
    """
    prs = PptxPresentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    layout = prs.slide_layouts[6]  # blank
    slide = prs.slides.add_slide(layout)
    txbox = slide.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(12), Inches(1))
    tf = txbox.text_frame
    p = tf.paragraphs[0]
    run = p.add_run()
    run.text = "Some descriptive but tiny title"
    run.font.size = Pt(8)  # << violation — well under 28pt floor
    run.font.name = "Roboto"

    # Add a small body so the slide isn't classified as a section divider.
    bbox = slide.shapes.add_textbox(Inches(0.5), Inches(2.0), Inches(12), Inches(3))
    btf = bbox.text_frame
    bp = btf.paragraphs[0]
    brun = bp.add_run()
    brun.text = "Body text large enough to read"
    brun.font.size = Pt(24)
    brun.font.name = "Roboto"

    out = tmp_path / "tiny_title.pptx"
    prs.save(str(out))
    return out


@pytest.fixture
def overlap_deck(tmp_path: Path) -> Path:
    """Synthetic deck with two heavily overlapping shapes (critical issue)."""
    prs = PptxPresentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(layout)

    # Title at the top — large and Roboto so we don't trip other audits.
    tbox = slide.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(12), Inches(1))
    tf = tbox.text_frame
    p = tf.paragraphs[0]
    r = p.add_run()
    r.text = "Slide title that is sufficiently descriptive"
    r.font.size = Pt(32)
    r.font.name = "Roboto"

    # Two big boxes that overlap by ~5 inches.
    for left in (Inches(1), Inches(2)):
        b = slide.shapes.add_textbox(left, Inches(2), Inches(8), Inches(4))
        bf = b.text_frame
        bp = bf.paragraphs[0]
        br = bp.add_run()
        br.text = "Lots of body content here"
        br.font.size = Pt(24)
        br.font.name = "Roboto"

    out = tmp_path / "overlap.pptx"
    prs.save(str(out))
    return out


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestReviewDeckGoodCase:
    def test_known_good_deck_has_no_criticals(self, good_deck: Path) -> None:
        report = review_deck(good_deck)
        # Diagnostics surface as the failure message so a regression is loud.
        criticals = [i for i in report.all_issues() if i.get("severity") == "critical"]
        assert report.n_critical == 0, f"Expected zero criticals, got: {criticals}"
        assert report.ok() is True

    def test_review_report_dataclass_shape(self, good_deck: Path) -> None:
        report = review_deck(good_deck)
        assert isinstance(report, ReviewReport)
        assert report.pptx_path == good_deck
        assert report.n_slides == 5
        assert all(isinstance(s, SlideReview) for s in report.per_slide)

    def test_summary_lines_non_empty(self, good_deck: Path) -> None:
        report = review_deck(good_deck)
        lines = report.summary_lines()
        assert lines, "summary_lines should return at least one line"
        assert any("5" in line for line in lines), "Summary should mention slide count"


class TestReviewDeckCriticalCases:
    def test_tiny_title_font_is_critical(self, tiny_title_deck: Path) -> None:
        report = review_deck(tiny_title_deck)
        rules = {i["rule"] for i in report.all_issues() if i.get("severity") == "critical"}
        assert "min-title-font" in rules, (
            f"Expected min-title-font critical issue. Got: {list(report.all_issues())}"
        )
        assert report.ok() is False
        assert report.n_critical >= 1

    def test_shape_overlap_is_critical(self, overlap_deck: Path) -> None:
        report = review_deck(overlap_deck)
        rules = {i["rule"] for i in report.all_issues() if i.get("severity") == "critical"}
        assert "no-shape-overlap" in rules, (
            f"Expected overlap critical issue. Got: {list(report.all_issues())}"
        )
        assert report.ok() is False


class TestReviewDeckWarningCases:
    def test_short_title_flags_warning(self, tmp_path: Path) -> None:
        # A normal-looking deck except one slide has a one-word title.
        fig = _make_image(tmp_path / "fig.png")
        plan = {
            "title": "Deck",
            "author": "Test",
            "slides": [
                {"type": "title", "title": "Deck", "subtitle": "Subtitle", "author": "T"},
                {"type": "section_divider", "title": "Section"},
                {
                    "type": "text",
                    "title": "Findings",  # one-word → warning
                    "bullets": ["Bullet one", "Bullet two"],
                },
                {
                    "type": "figure",
                    "title": "Bigger descriptive title for figure slide",
                    "image_path": str(fig),
                    "caption": "Cap",
                    "bullets": ["Bullet"],
                },
            ],
        }
        out = tmp_path / "short_title.pptx"
        build_from_plan(plan, out, write_marp=False)
        report = review_deck(out)

        slide2 = report.per_slide[2]
        rules = {i["rule"] for i in slide2.issues}
        assert "descriptive-title" in rules, (
            f"Expected descriptive-title warning on slide 2. Issues: {slide2.issues}"
        )


class TestReviewDeckStoryArc:
    def test_empty_deck_flags_story_arc(self, tmp_path: Path) -> None:
        prs = PptxPresentation()
        out = tmp_path / "empty.pptx"
        prs.save(str(out))
        report = review_deck(out)
        rules = {i["rule"] for i in report.story_arc_issues}
        assert "story-arc-empty" in rules
        assert report.ok() is False


class TestReviewHtml:
    def test_render_review_html_is_non_empty(self, good_deck: Path) -> None:
        report = review_deck(good_deck)
        html = render_review_html(report)
        assert isinstance(html, str)
        assert len(html) > 500, "HTML report should not be a stub"
        # Should reference the deck name + the audit framing.
        assert good_deck.stem in html

    def test_render_review_html_contains_issue_text(self, tiny_title_deck: Path) -> None:
        report = review_deck(tiny_title_deck)
        html = render_review_html(report)
        # The audit_html builder uppercases the issue kind for display.
        assert "MIN-TITLE-FONT" in html, "Issue rule name should appear in the HTML"
        # The detail text should surface in the per-slide card.
        assert "28pt minimum" in html or "28pt" in html

    def test_write_review_report_writes_html_and_sidecars(
        self, good_deck: Path, tmp_path: Path
    ) -> None:
        out = tmp_path / "review.html"
        report = review_deck(good_deck)
        written = write_review_report(report, out)
        assert written.exists()
        assert written.stat().st_size > 500
        # Red Line #2 — sidecar pair next to the HTML.
        assert (out.parent / "review.html.provenance.json").exists()
        assert (out.parent / "review.html.method.md").exists()


class TestReviewDeckErrors:
    def test_missing_pptx_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            review_deck(tmp_path / "nope.pptx")


# ---------------------------------------------------------------------------
# WCAG color-contrast check (deferred-followups bundle, 2026-05-15)
# ---------------------------------------------------------------------------


class TestColorContrastCheck:
    """Per-text-shape WCAG contrast ratio.

    AA threshold = 4.5 for normal text; <3.0 = critical, 3.0-4.5 = warning.
    Theme/scheme colors must NOT trip the check (no false positives).
    """

    def _build_contrast_deck(
        self,
        tmp_path: Path,
        *,
        fg: tuple[int, int, int],
        bg: tuple[int, int, int] | None = None,
        name: str = "contrast.pptx",
    ) -> Path:
        """Build a single-slide pptx with a known fg/bg color pair."""
        from pptx.dml.color import RGBColor

        prs = PptxPresentation()
        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)
        layout = prs.slide_layouts[6]
        slide = prs.slides.add_slide(layout)

        # Title at top (large + Roboto, satisfies other audits).
        tbox = slide.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(12), Inches(1))
        tp = tbox.text_frame.paragraphs[0]
        tr = tp.add_run()
        tr.text = "Slide title that is sufficiently descriptive"
        tr.font.size = Pt(32)
        tr.font.name = "Roboto"

        # Body shape — apply explicit fill if bg given; else leave default.
        body = slide.shapes.add_textbox(Inches(1), Inches(2), Inches(11), Inches(3))
        if bg is not None:
            body.fill.solid()
            body.fill.fore_color.rgb = RGBColor(*bg)
        bp = body.text_frame.paragraphs[0]
        br = bp.add_run()
        br.text = "Body text that should be legible at projector distance"
        br.font.size = Pt(24)
        br.font.name = "Roboto"
        br.font.color.rgb = RGBColor(*fg)

        out = tmp_path / name
        prs.save(str(out))
        return out

    def test_low_contrast_text_is_critical(self, tmp_path: Path) -> None:
        # Light-gray text on white background — ratio ≈ 1.6 (well below 3.0).
        deck = self._build_contrast_deck(
            tmp_path, fg=(0xDD, 0xDD, 0xDD), bg=(0xFF, 0xFF, 0xFF)
        )
        report = review_deck(deck)
        rules = {(i["severity"], i["rule"]) for i in report.all_issues()}
        assert ("critical", "color-contrast") in rules, (
            f"Expected color-contrast critical. Got: {list(report.all_issues())}"
        )

    def test_borderline_contrast_is_warning(self, tmp_path: Path) -> None:
        # Mid-gray text on white — ratio in the 3.0-4.5 band (warning, not critical).
        # #888888 on white has ratio ≈ 3.54.
        deck = self._build_contrast_deck(
            tmp_path, fg=(0x88, 0x88, 0x88), bg=(0xFF, 0xFF, 0xFF)
        )
        report = review_deck(deck)
        contrast_issues = [
            i for i in report.all_issues() if i.get("rule") == "color-contrast"
        ]
        assert any(i.get("severity") == "warning" for i in contrast_issues), (
            f"Expected color-contrast warning at borderline ratio. Got: {contrast_issues}"
        )
        # And not critical, since we're above 3.0.
        assert not any(i.get("severity") == "critical" for i in contrast_issues)

    def test_high_contrast_is_silent(self, tmp_path: Path) -> None:
        # Black on white — ratio = 21:1 (max). No contrast issue should fire.
        deck = self._build_contrast_deck(
            tmp_path, fg=(0x00, 0x00, 0x00), bg=(0xFF, 0xFF, 0xFF)
        )
        report = review_deck(deck)
        contrast_issues = [
            i for i in report.all_issues() if i.get("rule") == "color-contrast"
        ]
        assert not contrast_issues, (
            f"High-contrast deck should not raise contrast issues. Got: {contrast_issues}"
        )

    def test_unset_run_color_does_not_flag(self, tmp_path: Path) -> None:
        """No fg color set → theme inherited → must skip silently (no false positive)."""
        prs = PptxPresentation()
        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)
        layout = prs.slide_layouts[6]
        slide = prs.slides.add_slide(layout)

        tbox = slide.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(12), Inches(1))
        tp = tbox.text_frame.paragraphs[0]
        tr = tp.add_run()
        tr.text = "Slide title that is sufficiently descriptive"
        tr.font.size = Pt(32)
        tr.font.name = "Roboto"

        body = slide.shapes.add_textbox(Inches(1), Inches(2), Inches(11), Inches(3))
        bp = body.text_frame.paragraphs[0]
        br = bp.add_run()
        br.text = "Body text with no explicit color"
        br.font.size = Pt(24)
        br.font.name = "Roboto"
        # NOTE: deliberately not touching br.font.color

        out = tmp_path / "theme.pptx"
        prs.save(str(out))
        report = review_deck(out)
        contrast_issues = [
            i for i in report.all_issues() if i.get("rule") == "color-contrast"
        ]
        assert not contrast_issues, (
            f"Themed colors should not be flagged. Got: {contrast_issues}"
        )

    def test_contrast_helpers_match_wcag(self) -> None:
        from vaultlab.slides.self_review import _contrast_ratio

        # Black on white is exactly 21:1 (the WCAG-defined max).
        assert abs(_contrast_ratio((0, 0, 0), (255, 255, 255)) - 21.0) < 0.01
        # Same color → ratio = 1.0.
        assert abs(_contrast_ratio((128, 128, 128), (128, 128, 128)) - 1.0) < 1e-9
        # Symmetry: order of args must not matter.
        a = _contrast_ratio((0x11, 0x55, 0x99), (0xEE, 0xEE, 0xEE))
        b = _contrast_ratio((0xEE, 0xEE, 0xEE), (0x11, 0x55, 0x99))
        assert abs(a - b) < 1e-9
