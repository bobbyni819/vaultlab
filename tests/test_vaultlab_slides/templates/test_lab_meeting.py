"""Tests for lab_meeting deck template (sub-goal 5.2)."""

from __future__ import annotations

from pathlib import Path

import pytest

PIL = pytest.importorskip("PIL")
pptx = pytest.importorskip("pptx", reason="python-pptx required")

from PIL import Image

from vaultlab.slides import build_from_plan
from vaultlab.slides.deck import SUPPORTED_PLAN_SLIDE_TYPES
from vaultlab.slides.template import lab_template_path
from vaultlab.slides.templates import build_lab_meeting


pytestmark = pytest.mark.skipif(
    lab_template_path() is None,
    reason="Hickey Lab template not bundled — lab_meeting tests need it",
)


def make_test_image(path: Path, color: str = "red") -> Path:
    Image.new("RGB", (200, 150), color).save(str(path))
    return path


@pytest.fixture
def sample_inputs(tmp_path):
    fig1 = make_test_image(tmp_path / "codex_qc.png", "red")
    fig2 = make_test_image(tmp_path / "neighborhood.png", "blue")
    fig3 = make_test_image(tmp_path / "donor_compare.png", "green")
    return {
        "project": "Phospholipid programs in IBD",
        "week_of": "Week of 2026-05-12",
        "presenter": "Bobby Ni",
        "recap_bullets": [
            "Said: re-run B12 donor with the new lipid-mask. "
            "Did: done — mask flagged 3 misregistered ROIs we excluded.",
            "Said: ingest 4 new MALDI runs. Did: 3/4 ingested; "
            "donor 17 has a stage drift artifact, re-acquisition queued.",
            "Said: draft figure-2 captions. Did: drafted, "
            "sent to John for comment Tue.",
        ],
        "progress_entries": [
            {
                "title": (
                    "CODEX QC pipeline catches 3 mis-registered ROIs on B12 donor"
                ),
                "figure": str(fig1),
                "caption": "Per-ROI alignment score; red dots are flagged ROIs.",
                "bullets": [
                    "Threshold: ROI excluded when alignment < 0.85.",
                    "All 3 flagged ROIs had a known stage drift in the run log.",
                ],
                "citation": "Internal CODEX run 2026-05-09",
            },
            {
                "title": (
                    "Phospholipid neighborhood enrichment recapitulates the "
                    "Schurch 2020 macrophage motif"
                ),
                "figure": str(fig2),
                "caption": (
                    "Neighborhood-frequency heatmap — column = phospholipid "
                    "class, row = cellular neighborhood."
                ),
                "bullets": [
                    "PC36:2 enriched in HEV-adjacent neighborhoods (q < 0.01).",
                    "Matches Schurch 2020 macrophage-rich CN9 motif.",
                ],
                "citation": "Schurch et al. 2020, Cell",
            },
            {
                "title": (
                    "Donor-level batch effects vanish after RUVg normalization"
                ),
                "figure": str(fig3),
                "caption": "PCA before vs after RUVg, colored by donor.",
                "bullets": [
                    "Pre-normalization: PC1 captures donor identity (38% variance).",
                    "Post-RUVg: donor identity drops to PC4 (4% variance).",
                ],
                "citation": "Internal analysis",
            },
        ],
        "open_questions": [
            "Should we drop donor 17 entirely or wait for re-acquisition?",
            "Is PC36:2-in-HEV-neighborhoods a real biological signal or "
            "a panel artifact?",
            "John's call — should figure-2 use the Schurch motif overlay "
            "or just the raw heatmap?",
        ],
        "next_week_bullets": [
            "Re-acquire donor 17 once stage is recalibrated.",
            "Draft methods paragraph for the RUVg normalization.",
            "Pull bulk-lipidomic data for the 4 IBD donors as orthogonal validation.",
        ],
        "ask_bullets": [
            "John: 30 min to debate the figure-2 motif overlay.",
            "Lab: anyone with bulk-lipidomic LC-MS time this week?",
        ],
    }


class TestLabMeetingPlanShape:
    def test_returns_dict_plan(self, sample_inputs):
        plan = build_lab_meeting(**sample_inputs)
        assert isinstance(plan, dict)
        assert "slides" in plan

    def test_slide_count_within_band(self, sample_inputs):
        plan = build_lab_meeting(**sample_inputs)
        n = len(plan["slides"])
        # Target 7-10 ± 2 → [5, 12]
        assert 5 <= n <= 12, f"Expected 7-10 (±2) slides, got {n}"

    def test_all_types_supported(self, sample_inputs):
        plan = build_lab_meeting(**sample_inputs)
        for slide in plan["slides"]:
            assert slide.get("type") in SUPPORTED_PLAN_SLIDE_TYPES

    def test_starts_with_title(self, sample_inputs):
        plan = build_lab_meeting(**sample_inputs)
        assert plan["slides"][0]["type"] == "title"
        assert "Phospholipid" in plan["slides"][0]["title"]

    def test_includes_recap(self, sample_inputs):
        plan = build_lab_meeting(**sample_inputs)
        # Recap is slide 2
        recap = plan["slides"][1]
        assert "Last week" in recap["title"] or "recap" in recap["title"].lower()

    def test_includes_progress_figure_slides(self, sample_inputs):
        plan = build_lab_meeting(**sample_inputs)
        figure_slides = [s for s in plan["slides"] if s.get("type") == "figure"]
        assert len(figure_slides) == 3
        assert all(s.get("image_path") for s in figure_slides)

    def test_includes_open_questions(self, sample_inputs):
        plan = build_lab_meeting(**sample_inputs)
        titles = [s.get("title", "") for s in plan["slides"]]
        assert any("Open questions" in t for t in titles)

    def test_includes_next_week(self, sample_inputs):
        plan = build_lab_meeting(**sample_inputs)
        titles = [s.get("title", "") for s in plan["slides"]]
        assert any("next week" in t.lower() for t in titles)

    def test_includes_asks_when_provided(self, sample_inputs):
        plan = build_lab_meeting(**sample_inputs)
        titles = [s.get("title", "") for s in plan["slides"]]
        assert any("ask" in t.lower() for t in titles)

    def test_no_asks_slide_when_omitted(self, sample_inputs):
        sample_inputs.pop("ask_bullets")
        plan = build_lab_meeting(**sample_inputs)
        titles = [s.get("title", "") for s in plan["slides"]]
        # No "Asks" title when ask_bullets omitted
        assert not any("ask" in t.lower() for t in titles)


class TestLabMeetingRequiresProgress:
    def test_raises_with_no_progress(self):
        with pytest.raises(ValueError, match="progress"):
            build_lab_meeting(
                project="Foo",
                week_of="W1",
                presenter="P",
                recap_bullets=[],
                progress_entries=[],
                open_questions=[],
                next_week_bullets=[],
            )


class TestLabMeetingTextOnlyProgress:
    def test_text_progress_entry(self, tmp_path):
        plan = build_lab_meeting(
            project="Foo",
            week_of="W1",
            presenter="P",
            recap_bullets=["r1"],
            progress_entries=[
                {
                    "title": "Result without figure yet",
                    "bullets": ["pulled data", "QC clean"],
                },
            ],
            open_questions=["q1"],
            next_week_bullets=["nw1"],
        )
        # Progress entry without a figure should still emit a text slide
        progress = [s for s in plan["slides"] if s.get("title") == "Result without figure yet"]
        assert len(progress) == 1
        assert progress[0]["type"] == "text"


class TestLabMeetingRenders:
    def test_render_via_build_from_plan(self, sample_inputs, tmp_path):
        plan = build_lab_meeting(**sample_inputs)
        out = tmp_path / "lab_meeting.pptx"
        result = build_from_plan(plan, out, write_marp=False)
        assert result["pptx"] == out
        assert out.exists()
        assert out.stat().st_size > 0
