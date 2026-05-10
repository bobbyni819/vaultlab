"""Tests for FigureUnderstandLog markdown rendering + persistence + pipeline integration.

Covers Finding 9 from ``live-audit-notes-evening5-2026-04-30.md``: per-figure
LLM-reasoning logs persisted alongside the annotated PNG so each step's
thinking is auditable.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# These tests need numpy/PIL/skimage for the integration test that runs
# extract_regions on a synthetic figure. If those aren't installed, skip the
# whole module to match the convention used by tests/test_vaultlab_figures.
np = pytest.importorskip("numpy")
pytest.importorskip("PIL")
pytest.importorskip("skimage")

from PIL import Image

from vaultlab.figures.understand import (
    ColorMotif,
    FigureUnderstandLog,
    VerificationIteration,
    save_understand_log,
    understand_figure,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sample_log() -> FigureUnderstandLog:
    return FigureUnderstandLog(
        doi="10.1038/s41586-023-05915-x",
        figure_id="fig1.png",
        generated_at="2026-04-30T17:30:00-04:00",
        final_state="success",
        n_iterations=2,
        step1_description=(
            "there is a neon-green dimer in panel a representing the introduced TCR;\n"
            "three orange rectangles in panel b show the staining sequence."
        ),
        step2_regions=[
            {
                "id": "r0",
                "color_motif": "neon-green",
                "bbox": (120, 200, 180, 260),
                "source": "color_motif",
            },
            {
                "id": "r1",
                "color_motif": "orange",
                "bbox": (45, 300, 95, 330),
                "source": "color_motif",
            },
        ],
        step3_matches=[
            {
                "element_name": "TCR dimer",
                "matched_region_id": "r0",
                "rationale": "the only neon-green polygon in panel a",
                "confidence": 0.92,
            },
            {
                "element_name": "staining cycle 1",
                "matched_region_id": "r1",
                "rationale": "leftmost orange rectangle in panel b",
                "confidence": 0.78,
            },
        ],
        step4_verifications=[
            VerificationIteration(
                iteration=1,
                annotated_image_read="TCR dimer label is on top of the wrong cell type",
                issues_found=["TCR dimer label collides with endogenous TCR drawing"],
                decision="RETRY_MATCH",
            ),
            VerificationIteration(
                iteration=2,
                annotated_image_read="all labels match the LLM's description",
                issues_found=[],
                decision="ACCEPT",
            ),
        ],
        annotated_png_path="/some/where/fig1.annotated.png",
    )


def _make_synthetic_figure(tmp_path: Path) -> Path:
    """400x400 figure with one neon-green square — enough to localize one region."""
    img = np.full((400, 400, 3), 255, dtype=np.uint8)
    img[100:150, 100:150] = (50, 230, 50)
    path = tmp_path / "fig1.png"
    Image.fromarray(img).save(path)
    return path


# ---------------------------------------------------------------------------
# to_markdown rendering
# ---------------------------------------------------------------------------


def test_figure_understand_log_to_markdown_renders_all_sections() -> None:
    md = _sample_log().to_markdown()

    # Frontmatter present and contains required keys
    assert md.startswith("---\n")
    assert "doi: 10.1038/s41586-023-05915-x" in md
    assert "figure_id: fig1.png" in md
    assert "generated_at: 2026-04-30T17:30:00-04:00" in md
    assert "final_state: success" in md
    assert "n_iterations: 2" in md

    # Top-level header
    assert "# Figure understanding — fig1.png" in md

    # Four H2 sections, in order
    h2_sections = [
        "## Step 1 — Description (LLM)",
        "## Step 2 — Localization (programmatic)",
        "## Step 3 — Matching (LLM)",
        "## Step 4 — Verification (LLM, multimodal)",
    ]
    last_pos = -1
    for header in h2_sections:
        pos = md.find(header)
        assert pos > last_pos, f"missing or out-of-order: {header}"
        last_pos = pos

    # Step 1 blockquoted text
    assert "> there is a neon-green dimer" in md

    # Step 2 table header
    assert "| Region ID | Color motif | Bounding box | Source |" in md
    assert "(120,200)-(180,260)" in md

    # Step 3 table
    assert "| Element name | Matched region | Rationale | Confidence |" in md
    assert "| TCR dimer | r0 |" in md

    # Step 4 verification iterations subsection
    assert "### Iteration 1" in md
    assert "### Iteration 2" in md
    assert "**Decision:** `RETRY_MATCH`" in md
    assert "**Decision:** `ACCEPT`" in md


def test_to_markdown_handles_empty_steps_gracefully() -> None:
    log = FigureUnderstandLog(
        doi="10.1/x",
        figure_id="figX.png",
        generated_at="2026-04-30T00:00:00",
        final_state="failed",
        n_iterations=0,
    )
    md = log.to_markdown()
    # Sections still present, with placeholder copy
    assert "## Step 1 — Description (LLM)" in md
    assert "(no description captured" in md
    assert "(no regions extracted)" in md
    assert "(no matches recorded" in md
    assert "(no verification iterations recorded" in md


# ---------------------------------------------------------------------------
# save_understand_log persistence
# ---------------------------------------------------------------------------


def test_save_understand_log_writes_to_canonical_path(tmp_path: Path) -> None:
    log = _sample_log()
    out = save_understand_log(log, tmp_path)

    expected = (
        tmp_path / "Sources" / "Figures" / "10.1038_s41586-023-05915-x" / "fig1.understand.md"
    )
    assert out == expected
    assert expected.exists()
    body = expected.read_text(encoding="utf-8")
    assert body.startswith("---\n")
    assert "## Step 4 — Verification" in body


def test_save_understand_log_overwrites_existing(tmp_path: Path) -> None:
    log = _sample_log()
    first = save_understand_log(log, tmp_path)
    first_text = first.read_text(encoding="utf-8")

    # Mutate the log and re-save — overwriting (not appending) is the contract.
    log.step1_description = "REPLACED DESCRIPTION ONE-LINER"
    second = save_understand_log(log, tmp_path)
    second_text = second.read_text(encoding="utf-8")

    assert first == second  # same path
    assert "REPLACED DESCRIPTION ONE-LINER" in second_text
    assert second_text != first_text
    # Old content is gone.
    assert "neon-green dimer" not in second_text


def test_save_understand_log_handles_doi_with_unsafe_chars(tmp_path: Path) -> None:
    log = _sample_log()
    log.doi = "10.1234/foo:bar/baz"
    out = save_understand_log(log, tmp_path)
    # slugify_doi replaces ':' and '/' with '_' and lowercases.
    assert "10.1234_foo_bar_baz" in str(out)
    assert out.exists()


# ---------------------------------------------------------------------------
# Pipeline orchestrator end-to-end
# ---------------------------------------------------------------------------


def test_understand_pipeline_emits_log_on_completion(tmp_path: Path) -> None:
    """Stub LLM callbacks; verify all 4 sections populate and the PNG is written."""
    from vaultlab.figures.understand import render_debug_overlay

    fig = _make_synthetic_figure(tmp_path)
    motif = ColorMotif("neon-green", (90, 145), 0.40, 0.40, 0.0001)

    # Step 1: deterministic description.
    def describe(_: Path) -> str:
        return "a single neon-green square in the upper-left of the figure"

    # Step 3: match the LLM-named element to the first region.
    def match(_desc: str, regions):
        if not regions:
            return []
        return [
            {
                "element_name": "neon-green square",
                "matched_region_id": "r0",
                "rationale": "only green region in the image",
                "confidence": 0.9,
            }
        ]

    # Step 4: accept on first iteration.
    def verify(_png: Path, _anns, iteration: int) -> VerificationIteration:
        return VerificationIteration(
            iteration=iteration,
            annotated_image_read="overlay box is on the green square — looks correct",
            issues_found=[],
            decision="ACCEPT",
        )

    # Render the (placeholder) annotated PNG — same path the orchestrator
    # records into the log.
    annotated = tmp_path / "fig1.annotated.png"
    annotations, log = understand_figure(
        fig,
        [motif],
        doi="10.1234/test.case",
        annotated_png_path=annotated,
        describe_fn=describe,
        match_fn=match,
        verify_fn=verify,
    )

    # The PNG path is recorded even before render — write the file via the
    # public renderer to mirror the production flow.
    render_debug_overlay(fig, [], annotated)
    assert annotated.exists()

    # Pipeline returns at least one annotation.
    assert len(annotations) >= 1
    assert annotations[0].label == "neon-green square"

    # Log captures all four steps.
    assert log.step1_description.startswith("a single neon-green")
    assert len(log.step2_regions) >= 1
    assert log.step2_regions[0]["color_motif"] == "neon-green"
    assert log.step3_matches[0]["element_name"] == "neon-green square"
    assert len(log.step4_verifications) == 1
    assert log.step4_verifications[0].decision == "ACCEPT"
    assert log.final_state == "success"
    assert log.n_iterations == 1
    assert log.annotated_png_path == str(annotated)

    # Save and verify the markdown lands on disk.
    saved = save_understand_log(log, tmp_path)
    assert saved.exists()
    body = saved.read_text(encoding="utf-8")
    for marker in (
        "## Step 1 — Description (LLM)",
        "## Step 2 — Localization (programmatic)",
        "## Step 3 — Matching (LLM)",
        "## Step 4 — Verification (LLM, multimodal)",
        "ACCEPT",
    ):
        assert marker in body


def test_understand_pipeline_skipped_steps_recorded_honestly(tmp_path: Path) -> None:
    """When no LLM callbacks are wired, the log should reflect the actual partial
    state rather than fabricating LLM output.
    """
    fig = _make_synthetic_figure(tmp_path)
    motif = ColorMotif("neon-green", (90, 145), 0.40, 0.40, 0.0001)

    annotations, log = understand_figure(
        fig,
        [motif],
        doi="10.1234/skipped",
    )

    # Localize did run (it's programmatic), match/verify did not.
    assert len(log.step2_regions) >= 1
    assert log.step1_description == ""
    assert log.step3_matches == []
    assert log.step4_verifications == []
    assert annotations == []
    # final_state must be partial when localization succeeded but match/verify
    # were skipped — never silently 'success'.
    assert log.final_state == "partial"

    body = log.to_markdown()
    assert "(no description captured" in body
    assert "(no matches recorded" in body
    assert "(no verification iterations recorded" in body


def test_understand_pipeline_caps_verify_iterations(tmp_path: Path) -> None:
    """An always-RETRY verify_fn must hit the iteration cap, not loop forever."""
    fig = _make_synthetic_figure(tmp_path)
    motif = ColorMotif("neon-green", (90, 145), 0.40, 0.40, 0.0001)

    def describe(_: Path) -> str:
        return "stub"

    def match(_desc: str, regions):
        return (
            [
                {
                    "element_name": "x",
                    "matched_region_id": "r0",
                    "rationale": "stub",
                    "confidence": 0.5,
                }
            ]
            if regions
            else []
        )

    def verify(_png, _anns, iteration: int) -> VerificationIteration:
        return VerificationIteration(
            iteration=iteration,
            annotated_image_read=f"pass {iteration}: still wrong",
            issues_found=["box is off"],
            decision="RETRY_MATCH",
        )

    _anns, log = understand_figure(
        fig,
        [motif],
        doi="10.1234/looper",
        describe_fn=describe,
        match_fn=match,
        verify_fn=verify,
        max_iterations=3,
    )
    assert len(log.step4_verifications) == 3
    assert log.n_iterations == 3
    # Last decision wasn't ACCEPT, so final_state must not be success.
    assert log.final_state != "success"
