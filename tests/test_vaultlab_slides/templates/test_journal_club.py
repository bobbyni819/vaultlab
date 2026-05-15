"""Tests for journal_club deck template (sub-goal 5.2).

Distinct from ``test_journal_club_arcs.py`` — that covers the
arc-registry; this covers the full deck builder.
"""

from __future__ import annotations

from pathlib import Path

import pytest

PIL = pytest.importorskip("PIL")
pptx = pytest.importorskip("pptx", reason="python-pptx required")

from PIL import Image

from vaultlab.slides import build_from_plan
from vaultlab.slides.deck import SUPPORTED_PLAN_SLIDE_TYPES
from vaultlab.slides.template import lab_template_path
from vaultlab.slides.templates import (
    READ_FIRST_PATH,
    build_journal_club,
    format_label_bullet,
)


pytestmark = pytest.mark.skipif(
    lab_template_path() is None,
    reason="Hickey Lab template not bundled — journal_club tests need it",
)


def make_test_image(path: Path, color: str = "red") -> Path:
    Image.new("RGB", (200, 150), color).save(str(path))
    return path


@pytest.fixture
def sample_inputs(tmp_path):
    fig1 = make_test_image(tmp_path / "fig1.png", "red")
    fig2 = make_test_image(tmp_path / "fig2.png", "blue")
    fig3 = make_test_image(tmp_path / "fig3.png", "green")
    return {
        "paper_citation": "Goltsev et al., Cell 2018",
        "paper_doi": "10.1016/j.cell.2018.07.010",
        "presenter": "Bobby Ni",
        "presented_on": "2026-05-15",
        "why_this_paper_bullets": [
            "CODEX (CO-Detection by indEXing) — the panel-agnostic method "
            "that defined the multiplexed-imaging field.",
            "Foundational for our lab's spatial-proteomics arc on IBD donors.",
            "Field is now revisiting Goltsev's normalization choices — "
            "worth a re-read.",
        ],
        "lab_context_bullets": [
            "Our IBD CODEX panel directly extends the Goltsev tonsil panel.",
            "John's 2021 paper benchmarks the cell-typing model against this dataset.",
            "Our QC pipeline still inherits the per-ROI alignment threshold here.",
        ],
        "field_context_bullets": [
            "Schurch 2020 (Cell) — extended CODEX to colorectal cancer cohorts.",
            "Phillips 2021 (Nat Immunol) — applied CODEX to autoimmune skin disease.",
            "Hartmann 2021 (Nat Immunol) — IMC alternative; similar marker breadth.",
        ],
        "figures": [
            {
                "title": (
                    "Figure 2 — CODEX panel resolves 28 markers across "
                    "tonsil follicles"
                ),
                "image_path": str(fig1),
                "caption": (
                    "Whole-tonsil section stained with the 28-marker CODEX panel; "
                    "germinal centers, T-cell zones, and HEVs visible at a glance."
                ),
                "strengths": [
                    format_label_bullet(
                        "Panel breadth",
                        "28 markers in one section is a 6x improvement over "
                        "standard IF.",
                    ),
                    format_label_bullet(
                        "Spatial fidelity",
                        "Germinal-center architecture is preserved end-to-end.",
                    ),
                ],
                "limits": [
                    format_label_bullet(
                        "Panel locked",
                        "Custom-conjugated antibodies; not portable to new labs.",
                    ),
                    format_label_bullet(
                        "Bleed-through",
                        "Authors don't report per-marker bleed-through QC.",
                    ),
                ],
                "citation": "Goltsev et al. 2018, Cell",
            },
            {
                "title": (
                    "Figure 3 — Cellular neighborhoods reveal a B-cell:DC "
                    "niche near HEVs"
                ),
                "image_path": str(fig2),
                "caption": (
                    "Neighborhood-frequency heatmap — 9 cellular neighborhoods "
                    "(CNs) clustered from local marker abundance."
                ),
                "strengths": [
                    format_label_bullet(
                        "Neighborhood definition",
                        "Window-based composition vector is reproducible across operators.",
                    ),
                    format_label_bullet(
                        "Biological insight",
                        "CN9 (B-cell:DC) maps cleanly to HEV-adjacent regions.",
                    ),
                ],
                "limits": [
                    format_label_bullet(
                        "Window-size sensitivity",
                        "Authors fix window radius at 10um — no sensitivity analysis.",
                    ),
                    format_label_bullet(
                        "Donor n",
                        "Only 1 donor — generalization unclear.",
                    ),
                ],
                "citation": "Goltsev et al. 2018, Cell",
            },
            {
                "title": (
                    "Figure 5 — Lupus tonsils show a perturbed B-cell:DC neighborhood"
                ),
                "image_path": str(fig3),
                "caption": (
                    "Compare healthy vs lupus tonsils — CN9 abundance drops "
                    "and is replaced by an inflammatory CN3."
                ),
                "strengths": [
                    format_label_bullet(
                        "Disease signal",
                        "CN9 -> CN3 substitution is robust across the 4 lupus donors.",
                    ),
                ],
                "limits": [
                    format_label_bullet(
                        "Sample size",
                        "n=4 lupus, n=2 healthy — statistical claims overstated.",
                    ),
                    format_label_bullet(
                        "Causality",
                        "No functional follow-up — neighborhood shift is correlative.",
                    ),
                ],
                "citation": "Goltsev et al. 2018, Cell",
            },
        ],
        "take_home_quote": (
            "These data reveal that cellular neighborhoods, "
            "rather than individual cell types, encode the spatial "
            "organization of immune tissues."
        ),
        "take_home_attribution": "Goltsev et al. 2018, Cell",
        "take_home_bullets": [
            "For our lab: neighborhood definitions should be a first-class "
            "output of our IBD pipeline, not a downstream afterthought.",
            "Inherit Goltsev's per-ROI QC, but add bleed-through controls.",
            "Adopt window-radius sensitivity analysis the original paper skipped.",
        ],
        "discussion_prompts": [
            "Is the CN definition robust to panel changes, or does it bake "
            "in panel-specific assumptions?",
            "Should we use Goltsev's window size (10um) for the IBD panel, "
            "or recompute from cell density?",
            "Lupus n=4 is small — what's the minimum n we want for our "
            "disease-condition claims?",
        ],
        "references": [
            "Goltsev et al. 2018, Cell. DOI: 10.1016/j.cell.2018.07.010",
            "Schurch et al. 2020, Cell. DOI: 10.1016/j.cell.2020.07.005",
            "Phillips et al. 2021, Nat Immunol. DOI: 10.1038/s41590-020-00845-6",
        ],
    }


class TestJournalClubPlanShape:
    def test_returns_dict_plan(self, sample_inputs):
        plan = build_journal_club(**sample_inputs)
        assert isinstance(plan, dict)
        assert "slides" in plan

    def test_slide_count_within_band(self, sample_inputs):
        plan = build_journal_club(**sample_inputs)
        n = len(plan["slides"])
        # Target 10-12 ± 2 → [8, 14]
        assert 8 <= n <= 14, f"Expected 10-12 (±2) slides, got {n}"

    def test_all_types_supported(self, sample_inputs):
        plan = build_journal_club(**sample_inputs)
        for slide in plan["slides"]:
            assert slide.get("type") in SUPPORTED_PLAN_SLIDE_TYPES

    def test_title_uses_paper_citation(self, sample_inputs):
        plan = build_journal_club(**sample_inputs)
        assert plan["slides"][0]["type"] == "title"
        assert "Goltsev" in plan["slides"][0]["title"]

    def test_has_why_lab_field_context_sections(self, sample_inputs):
        plan = build_journal_club(**sample_inputs)
        titles = [s.get("title", "") for s in plan["slides"]]
        joined = " ".join(titles).lower()
        assert "why" in joined
        assert "our lab" in joined or "lab's" in joined
        assert "field" in joined or "other groups" in joined

    def test_section_divider_before_figures(self, sample_inputs):
        plan = build_journal_club(**sample_inputs)
        types = [s.get("type") for s in plan["slides"]]
        # Find first section_divider; everything after it (until quote)
        # should be figure slides
        assert "section_divider" in types
        sd_idx = types.index("section_divider")
        # The slide right after should be a figure
        assert types[sd_idx + 1] == "figure"

    def test_figures_emit_with_strengths_and_limits(self, sample_inputs):
        plan = build_journal_club(**sample_inputs)
        fig_slides = [s for s in plan["slides"] if s.get("type") == "figure"]
        assert len(fig_slides) == 3
        # Each figure should have Strengths: and Limits: in bullets
        for fig in fig_slides:
            bullets = fig.get("bullets", [])
            assert any("Strengths" in b for b in bullets), (
                f"Figure {fig['title']!r} missing Strengths header"
            )

    def test_take_home_quote_slide(self, sample_inputs):
        plan = build_journal_club(**sample_inputs)
        quotes = [s for s in plan["slides"] if s.get("type") == "quote"]
        assert len(quotes) == 1
        assert "cellular neighborhoods" in quotes[0]["quote"]

    def test_discussion_prompts_present(self, sample_inputs):
        plan = build_journal_club(**sample_inputs)
        titles = [s.get("title", "") for s in plan["slides"]]
        assert any("Discussion" in t for t in titles)

    def test_references_slide_present(self, sample_inputs):
        plan = build_journal_club(**sample_inputs)
        refs = [s for s in plan["slides"] if s.get("type") == "references"]
        assert len(refs) == 1


class TestJournalClubRequiresFigures:
    def test_raises_with_no_figures(self):
        with pytest.raises(ValueError, match="figure"):
            build_journal_club(
                paper_citation="P",
                paper_doi="d",
                presenter="P",
                presented_on="2026-01-01",
                why_this_paper_bullets=[],
                lab_context_bullets=[],
                field_context_bullets=[],
                figures=[],
                take_home_quote="q",
                take_home_attribution="a",
                take_home_bullets=[],
                discussion_prompts=[],
            )


class TestJournalClubHelpers:
    def test_format_label_bullet(self):
        assert format_label_bullet("Panel", "28 markers") == "Panel — 28 markers"

    def test_read_first_path_constant(self):
        # Documentation-facing constant — the canonical companion-briefing filename.
        assert READ_FIRST_PATH == "READ_FIRST_journal_club.md"


class TestJournalClubMinimalReferences:
    def test_defaults_references_to_paper_only(self, sample_inputs):
        sample_inputs.pop("references")
        plan = build_journal_club(**sample_inputs)
        refs = [s for s in plan["slides"] if s.get("type") == "references"]
        assert len(refs) == 1
        # The lone reference should mention the paper DOI
        ref_text = " ".join(refs[0]["references"])
        assert "10.1016/j.cell.2018.07.010" in ref_text


class TestJournalClubRenders:
    def test_render_via_build_from_plan(self, sample_inputs, tmp_path):
        plan = build_journal_club(**sample_inputs)
        out = tmp_path / "jc.pptx"
        result = build_from_plan(plan, out, write_marp=False)
        assert result["pptx"] == out
        assert out.exists()
        assert out.stat().st_size > 0
