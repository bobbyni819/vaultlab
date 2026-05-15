"""Tests for investor_pitch deck template (sub-goal 5.2)."""

from __future__ import annotations

import pytest

pptx = pytest.importorskip("pptx", reason="python-pptx required")

from vaultlab.slides import build_from_plan
from vaultlab.slides.deck import SUPPORTED_PLAN_SLIDE_TYPES
from vaultlab.slides.template import lab_template_path
from vaultlab.slides.templates import build_investor_pitch


pytestmark = pytest.mark.skipif(
    lab_template_path() is None,
    reason="Hickey Lab template not bundled — investor_pitch tests need it",
)


# Real research-tool startup inputs — multiplexed-imaging analysis pitch.
SAMPLE_INPUTS = {
    "company": "Manifold",
    "one_liner": (
        "Reproducible multiplexed-imaging analysis for translational "
        "immunology labs"
    ),
    "founders": "Bobby Ni, John Hickey — Duke BME",
    "problem_headline": (
        "CODEX and IMC labs take 6-8 weeks to analyze a single slide and "
        "results rarely reproduce across operators"
    ),
    "problem_bullets": [
        "Cell-segmentation steps are stitched from 4-6 Jupyter notebooks per lab.",
        "Neighborhood-analysis parameters drift between cohorts; reviewers ask why.",
        "Two operators in the same lab produce divergent cluster labels on the same slide.",
    ],
    "current_state_headline": (
        "Today, labs either hand-roll pipelines or pay for software that "
        "doesn't fit their panel"
    ),
    "current_state_bullets": [
        "Manual: ImageJ + custom Python, hard to onboard new students.",
        "Commercial: Visiopharm / HALO — locked to fixed panels, $40k/year.",
        "Result: ~70% of CODEX papers cite custom pipelines that aren't released.",
    ],
    "product_headline": (
        "Manifold is a code-first analysis platform with reproducibility baked in"
    ),
    "product_bullets": [
        "Versioned pipelines for CODEX, IMC, MIBI, and CycIF panels.",
        "One-click neighborhood analysis with auditable parameter provenance.",
        "Built-in QC: stain bleed-through, mask drift, donor-level batch effects.",
        "Outputs publication-ready figures + a methods paragraph.",
    ],
    "technical_insight_headline": (
        "Our wedge: a cell-typing model that transfers across panels without retraining"
    ),
    "technical_insight_bullets": [
        "Trained on 4.2M cells across 17 tissues from public CODEX + IMC atlases.",
        "Panel-agnostic embedding: handles overlapping or missing markers gracefully.",
        "Closes the 'every lab retrains from scratch' loop that kills reproducibility.",
    ],
    "traction_headline": (
        "Three design-partner labs; 17 paper-grade analyses shipped in Q1 2026"
    ),
    "traction_bullets": [
        "Design partners: Hickey (Duke), Greenbaum (Sloan), Pearce (WashU).",
        "Two preprints citing Manifold pipelines on bioRxiv.",
        "Median analysis time: 6 weeks -> 4 days on the Hickey CODEX panel.",
    ],
    "competitors_left_header": "HALO / Visiopharm",
    "competitors_left_bullets": [
        "Closed-source, hard to extend.",
        "Panel-locked.",
        "$40k+ per seat per year.",
    ],
    "competitors_right_header": "Manifold",
    "competitors_right_bullets": [
        "Code-first, audit-trail by default.",
        "Panel-agnostic cell-typing.",
        "Open-source core + paid hosted runs.",
    ],
    "competitors_key_insight": (
        "Code-first reproducibility is what reviewers now require"
    ),
    "market_headline": (
        "~1,400 academic labs and ~30 pharma sites run multiplexed imaging today"
    ),
    "market_bullets": [
        "TAM: $180M/year multiplexed-imaging software + services.",
        "Growing 35%/year as IMC and CODEX instruments ship.",
        "Bottom-up: 1,400 labs * $20k average spend = $28M reachable now.",
    ],
    "business_model_headline": "Open-core + hosted compute + pharma services",
    "business_model_bullets": [
        "Free OSS pipelines for academics.",
        "Hosted runs at $0.50/slide for low-effort cohort analyses.",
        "Pharma contracts: $150k-$400k per cohort, includes panel design.",
    ],
    "team": [
        ("Bobby Ni", "Co-founder / CEO", "Duke BME PhD"),
        ("John Hickey", "Co-founder / Sci. advisor", "Duke BME PI"),
        ("Hire #1", "Founding engineer", "Imaging informatics"),
    ],
    "roadmap_headline": "12-month milestones",
    "roadmap_bullets": [
        "Q3 2026: 10 design-partner labs onboarded.",
        "Q4 2026: First pharma pilot signed ($250k).",
        "Q1 2027: Cell-typing model publication accepted.",
        "Q2 2027: $1M ARR run-rate from hosted + pharma.",
    ],
    "ask_headline": "Raising $2.5M seed",
    "ask_bullets": [
        "$2.5M seed at $12M post.",
        "Use of funds: 4 engineering hires + GPU compute for the cell-typing model.",
        "Runway: 24 months to Series A metrics.",
    ],
}


class TestInvestorPitchPlanShape:
    def test_returns_dict_plan(self):
        plan = build_investor_pitch(**SAMPLE_INPUTS)
        assert isinstance(plan, dict)
        assert "slides" in plan
        assert "title" in plan
        assert plan["title"] == "Manifold"

    def test_slide_count_within_band(self):
        plan = build_investor_pitch(**SAMPLE_INPUTS)
        n = len(plan["slides"])
        # 10-12 target ± 2 → [8, 14]
        assert 8 <= n <= 14, f"Expected 10-12 (±2) slides, got {n}"

    def test_all_slide_types_supported(self):
        plan = build_investor_pitch(**SAMPLE_INPUTS)
        for slide in plan["slides"]:
            stype = slide.get("type")
            assert stype in SUPPORTED_PLAN_SLIDE_TYPES, (
                f"Slide type {stype!r} not in supported plan types"
            )

    def test_starts_with_title_slide(self):
        plan = build_investor_pitch(**SAMPLE_INPUTS)
        assert plan["slides"][0]["type"] == "title"
        assert plan["slides"][0]["title"] == "Manifold"

    def test_ends_with_ask(self):
        """Investor decks MUST end with an ask slide — non-negotiable."""
        plan = build_investor_pitch(**SAMPLE_INPUTS)
        last = plan["slides"][-1]
        assert last["type"] == "text"
        assert "raising" in last["title"].lower() or "ask" in last["title"].lower()

    def test_includes_problem_section(self):
        plan = build_investor_pitch(**SAMPLE_INPUTS)
        titles = " ".join(s.get("title", "").lower() for s in plan["slides"])
        # Problem headline contains "CODEX and IMC labs" etc — check
        # that the problem bullets land somewhere.
        all_bullets = []
        for s in plan["slides"]:
            all_bullets.extend(s.get("bullets", []))
        bullet_text = " ".join(all_bullets).lower()
        assert "segmentation" in bullet_text or "reproduce" in titles

    def test_includes_technical_insight_section(self):
        plan = build_investor_pitch(**SAMPLE_INPUTS)
        all_text = " ".join(
            s.get("title", "") + " " + " ".join(s.get("bullets", []))
            for s in plan["slides"]
        )
        assert "panel-agnostic" in all_text.lower() or "transfer" in all_text.lower()

    def test_includes_traction_section(self):
        plan = build_investor_pitch(**SAMPLE_INPUTS)
        all_text = " ".join(
            s.get("title", "") + " " + " ".join(s.get("bullets", []))
            for s in plan["slides"]
        )
        assert "design partner" in all_text.lower()

    def test_team_uses_acknowledgments_grid(self):
        plan = build_investor_pitch(**SAMPLE_INPUTS)
        ack_slides = [
            s for s in plan["slides"] if s.get("type") == "acknowledgments_grid"
        ]
        assert len(ack_slides) == 1
        people = ack_slides[0]["people"]
        names = [p[0] for p in people]
        assert "Bobby Ni" in names

    def test_comparison_table_used(self):
        plan = build_investor_pitch(**SAMPLE_INPUTS)
        cmp_slides = [
            s for s in plan["slides"] if s.get("type") == "comparison_table"
        ]
        assert len(cmp_slides) == 1
        assert cmp_slides[0]["left_header"] == "HALO / Visiopharm"


class TestInvestorPitchMinimal:
    def test_omits_optional_sections(self):
        """With no comparison / market / team / roadmap, the deck still
        produces a valid plan (just shorter)."""
        plan = build_investor_pitch(
            company="Foo",
            one_liner="A one-liner",
            founders="A founder",
            problem_headline="A problem",
            problem_bullets=["b1"],
            current_state_headline="Current",
            current_state_bullets=["c1"],
            product_headline="Product",
            product_bullets=["p1"],
            technical_insight_headline="Insight",
            technical_insight_bullets=["i1"],
            traction_headline="Traction",
            traction_bullets=["t1"],
        )
        # Title + 5 narrative + ask = 7 (no comparison, market, model,
        # team, roadmap)
        assert 6 <= len(plan["slides"]) <= 8
        # Still has an ask
        assert plan["slides"][-1]["type"] == "text"
        assert "raising" in plan["slides"][-1]["title"].lower()


class TestInvestorPitchRenders:
    def test_render_via_build_from_plan(self, tmp_path):
        plan = build_investor_pitch(**SAMPLE_INPUTS)
        out = tmp_path / "investor.pptx"
        result = build_from_plan(plan, out, write_marp=False)
        assert result["pptx"] == out
        assert out.exists()
        assert out.stat().st_size > 0
