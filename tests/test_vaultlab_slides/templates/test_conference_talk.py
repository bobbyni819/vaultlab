"""Tests for conference_talk deck template (sub-goal 5.2)."""

from __future__ import annotations

from pathlib import Path

import pytest

PIL = pytest.importorskip("PIL")
pptx = pytest.importorskip("pptx", reason="python-pptx required")

from PIL import Image

from vaultlab.slides import build_from_plan
from vaultlab.slides.deck import SUPPORTED_PLAN_SLIDE_TYPES
from vaultlab.slides.template import lab_template_path
from vaultlab.slides.templates import build_conference_talk


pytestmark = pytest.mark.skipif(
    lab_template_path() is None,
    reason="Hickey Lab template not bundled — conference_talk tests need it",
)


def make_test_image(path: Path, color: str = "red") -> Path:
    Image.new("RGB", (200, 150), color).save(str(path))
    return path


@pytest.fixture
def sample_inputs(tmp_path):
    methods_fig = make_test_image(tmp_path / "methods.png", "red")
    fig_a = make_test_image(tmp_path / "fig_a.png", "blue")
    fig_b = make_test_image(tmp_path / "fig_b.png", "green")
    fig_c = make_test_image(tmp_path / "fig_c.png", "yellow")
    fig_d = make_test_image(tmp_path / "fig_d.png", "purple")
    synthesis_fig = make_test_image(tmp_path / "synth.png", "orange")
    return {
        "talk_title": (
            "Panel-agnostic cell typing closes the reproducibility gap "
            "in multiplexed imaging"
        ),
        "authors": "Bobby Ni, John Hickey — Duke BME",
        "conference": "ISMB 2026, Berkeley CA",
        "motivation_headline": (
            "Multiplexed-imaging panels differ between labs, so cell-typing "
            "models have to be retrained every time"
        ),
        "motivation_bullets": [
            "CODEX, IMC, MIBI panels rarely share more than 60% of markers.",
            "Retraining the cell-typing model is the rate-limiting "
            "step in a new study.",
            "Across-study comparisons require manual marker mapping, "
            "which doesn't scale.",
        ],
        "prior_work_headline": (
            "Prior cell-typing methods assume a fixed panel"
        ),
        "prior_work_bullets": [
            "STELLAR (Brbic 2022) requires panel parity with the training set.",
            "Astir (Geuenich 2021) uses panel-specific marker dictionaries.",
            "ImmunoCluster (Opzoomer 2021) — manual gating; not transferable.",
        ],
        "gap_headline": (
            "No method handles arbitrary panel overlap without retraining"
        ),
        "gap_bullets": [
            "Panel mismatch -> ~40% accuracy drop in zero-shot transfer.",
            "Cross-study atlases stall because no shared cell-typing layer exists.",
        ],
        "approach_entry": {
            "title": (
                "We embed every cell into a panel-agnostic latent space"
            ),
            "figure": str(methods_fig),
            "caption": (
                "Schematic — markers from any panel map to a shared 256-d "
                "latent; cell types are decoded from the latent."
            ),
            "bullets": [
                "Trained on 4.2M cells from 17 public CODEX + IMC atlases.",
                "Masked-marker objective handles missing channels gracefully.",
            ],
            "citation": "This work",
        },
        "results_entries": [
            {
                "title": (
                    "Panel-agnostic embedding recovers known cell types on "
                    "held-out CODEX panels"
                ),
                "figure": str(fig_a),
                "caption": "UMAP of held-out cells colored by ground truth.",
                "bullets": [
                    "F1 = 0.91 on the Goltsev 2018 tonsil CODEX dataset (held out).",
                ],
                "citation": "Goltsev et al. 2018, Cell",
            },
            {
                "title": (
                    "Zero-shot transfer to IMC panels matches in-panel "
                    "retraining accuracy"
                ),
                "figure": str(fig_b),
                "caption": "F1 vs panel overlap — ours plateaus at 0.88.",
                "bullets": [
                    "Existing methods drop to F1=0.5 at <70% panel overlap.",
                    "Our method holds F1=0.85 at 40% overlap.",
                ],
                "citation": "Hartmann et al. 2021, Nat Immunol",
            },
            {
                "title": (
                    "Cross-study integration of 6 IBD cohorts reveals a "
                    "conserved tissue-resident macrophage program"
                ),
                "figure": str(fig_c),
                "caption": (
                    "Cross-cohort UMAP — 280k cells, 6 IBD studies, colored "
                    "by integrated cell type."
                ),
                "bullets": [
                    "TRM-like macrophages cluster across all 6 studies.",
                    "Batch effects collapse on the latent space.",
                ],
                "citation": "Internal integration, 2026",
            },
            {
                "title": "Ablation: masked-marker training is the key ingredient",
                "figure": str(fig_d),
                "caption": "Ablation grid — drop each loss term, measure F1.",
                "bullets": [
                    "Drop masked-marker loss: F1 falls 0.20.",
                    "Drop contrastive loss: F1 falls 0.06.",
                ],
                "citation": "This work",
            },
        ],
        "synthesis_entry": {
            "title": "A shared cell-typing layer unlocks the multiplexed-imaging atlas",
            "figure": str(synthesis_fig),
            "caption": "Schematic — how labs plug into the shared layer.",
            "bullets": [
                "Drop-in inference for any panel.",
                "First step toward a community-scale multiplexed atlas.",
            ],
        },
        "limits_headline": "Limits and what's next",
        "limits_bullets": [
            "Latent space assumes consistent staining protocols — pre-treated "
            "tissue (formalin vs frozen) still needs separate models.",
            "Cell types not in training atlases (rare tumor states) are mis-typed.",
            "Working on adapter modules for novel panels with <5 shared markers.",
        ],
        "conclusions_bullets": [
            "Panel-agnostic cell typing solves the cross-study transfer problem.",
            "Zero-shot F1 = 0.88 matches retrained baselines.",
            "Open-sourced; available at github.com/manifold/celltyper.",
        ],
        "acknowledgments": [
            ("John Hickey", "PI", "Duke BME"),
            ("Schurch lab", "Collaborator", "WashU"),
            ("Greenbaum lab", "Collaborator", "Sloan Kettering"),
            ("NIH R01-AI123456", "Funding", "NIAID"),
        ],
        "references": [
            "Goltsev et al. 2018, Cell. DOI: 10.1016/j.cell.2018.07.010",
            "Brbic et al. 2022, Nat Methods. DOI: 10.1038/s41592-022-01651-8",
            "Geuenich et al. 2021, Cell Systems. DOI: 10.1016/j.cels.2021.08.012",
        ],
    }


class TestConferenceTalkPlanShape:
    def test_returns_dict_plan(self, sample_inputs):
        plan = build_conference_talk(**sample_inputs)
        assert isinstance(plan, dict)
        assert "slides" in plan

    def test_slide_count_within_band(self, sample_inputs):
        plan = build_conference_talk(**sample_inputs)
        n = len(plan["slides"])
        # Target 12-15 ± 2 → [10, 17]
        assert 10 <= n <= 17, f"Expected 12-15 (±2) slides, got {n}"

    def test_all_types_supported(self, sample_inputs):
        plan = build_conference_talk(**sample_inputs)
        for slide in plan["slides"]:
            assert slide.get("type") in SUPPORTED_PLAN_SLIDE_TYPES

    def test_starts_with_title(self, sample_inputs):
        plan = build_conference_talk(**sample_inputs)
        assert plan["slides"][0]["type"] == "title"

    def test_methods_then_results(self, sample_inputs):
        plan = build_conference_talk(**sample_inputs)
        # First figure slide should be the approach (methods) entry.
        # The approach entry's title contains "panel-agnostic latent space".
        first_figure = next(s for s in plan["slides"] if s.get("type") == "figure")
        assert "panel-agnostic latent" in first_figure["title"].lower()

    def test_includes_conclusions(self, sample_inputs):
        plan = build_conference_talk(**sample_inputs)
        titles = [s.get("title", "") for s in plan["slides"]]
        assert "Conclusions" in titles

    def test_includes_acknowledgments(self, sample_inputs):
        plan = build_conference_talk(**sample_inputs)
        ack = [s for s in plan["slides"] if s.get("type") == "acknowledgments_grid"]
        assert len(ack) == 1
        names = [p[0] for p in ack[0]["people"]]
        assert "John Hickey" in names

    def test_includes_references(self, sample_inputs):
        plan = build_conference_talk(**sample_inputs)
        refs = [s for s in plan["slides"] if s.get("type") == "references"]
        assert len(refs) == 1

    def test_results_emit_figure_slides(self, sample_inputs):
        plan = build_conference_talk(**sample_inputs)
        figures = [s for s in plan["slides"] if s.get("type") == "figure"]
        # approach + 4 results + synthesis = 6 figure slides
        assert len(figures) == 6


class TestConferenceTalkRequiresResults:
    def test_raises_with_no_results(self, tmp_path):
        with pytest.raises(ValueError, match="results"):
            build_conference_talk(
                talk_title="T",
                authors="A",
                conference="C",
                motivation_headline="M",
                motivation_bullets=[],
                prior_work_headline="P",
                prior_work_bullets=[],
                gap_headline="G",
                gap_bullets=[],
                approach_entry={"title": "Approach"},
                results_entries=[],
            )


class TestConferenceTalkRenders:
    def test_render_via_build_from_plan(self, sample_inputs, tmp_path):
        plan = build_conference_talk(**sample_inputs)
        out = tmp_path / "conf.pptx"
        result = build_from_plan(plan, out, write_marp=False)
        assert result["pptx"] == out
        assert out.exists()
        assert out.stat().st_size > 0
