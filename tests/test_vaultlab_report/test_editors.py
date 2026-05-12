"""Tests for vaultlab.report.editors — two-way HTML editors."""

from __future__ import annotations

from pathlib import Path

import pytest

from vaultlab.report.editors import (
    build_citation_triage_editor,
    build_deckplan_tuner,
    build_slide_reorder_editor,
    write_citation_triage_editor,
    write_deckplan_tuner,
    write_slide_reorder_editor,
)

# ---------------------------------------------------------------------------
# Slide reorder editor


@pytest.fixture
def reorder_plan() -> dict:
    return {
        "title": "Multi-lung review",
        "slides": [
            {"type": "title", "title": "Title", "section": "Intro"},
            {"type": "bullets", "title": "Background", "section": "Intro"},
            {"type": "figure", "title": "Method", "section": "Method"},
            {"type": "figure", "title": "Result 1", "section": "Results"},
            {"type": "figure", "title": "Result 2", "section": "Results"},
            {"type": "bullets", "title": "Discussion", "section": "Discussion"},
        ],
    }


def test_reorder_editor_renders(reorder_plan):
    html = build_slide_reorder_editor(reorder_plan)
    assert "<!doctype html>" in html
    assert "Multi-lung review" in html
    assert "vl-kanban" in html


def test_reorder_editor_groups_by_section(reorder_plan):
    html = build_slide_reorder_editor(reorder_plan)
    for section in ("Intro", "Method", "Results", "Discussion"):
        assert section in html
    # Cut bucket appears at end
    assert "Cut" in html


def test_reorder_editor_shows_slide_titles(reorder_plan):
    html = build_slide_reorder_editor(reorder_plan)
    for title in ("Title", "Background", "Method", "Result 1", "Result 2", "Discussion"):
        assert title in html


def test_reorder_editor_export_buttons(reorder_plan):
    html = build_slide_reorder_editor(reorder_plan)
    assert "Copy as markdown" in html
    assert "Copy as JSON" in html


def test_reorder_editor_explicit_sections(reorder_plan):
    html = build_slide_reorder_editor(reorder_plan, sections=["A", "B", "Cut"])
    assert "A" in html
    assert "B" in html


def test_reorder_editor_unsectioned_slides():
    plan = {
        "title": "x",
        "slides": [
            {"type": "title", "title": "T"},  # no section
        ],
    }
    html = build_slide_reorder_editor(plan)
    assert "Unsectioned" in html


def test_write_slide_reorder_editor(tmp_path: Path, reorder_plan):
    out = tmp_path / "reorder.html"
    written = write_slide_reorder_editor(out, reorder_plan)
    assert written == out
    assert out.exists()


# ---------------------------------------------------------------------------
# Citation triage editor


@pytest.fixture
def triage_cits() -> list[dict]:
    return [
        {
            "authors": "Smith J",
            "year": 2020,
            "claim": "Method X works.",
            "status": "verified_fulltext",
        },
        {
            "authors": "Park S",
            "year": 2023,
            "claim": "Y improves Z.",
            "status": "unverified",
        },
        {
            "authors": "Doe J",
            "year": 2099,
            "claim": "Future claim.",
            "status": "suspect",
        },
    ]


def test_triage_editor_renders(triage_cits):
    html = build_citation_triage_editor(triage_cits)
    assert "<!doctype html>" in html
    assert "Citation triage" in html
    assert "vl-kanban" in html


def test_triage_editor_buckets_by_status(triage_cits):
    html = build_citation_triage_editor(triage_cits)
    assert "Accept" in html
    assert "Reject" in html
    assert "Flag for plagiarism" in html
    # Verified → Accept; unverified → Pending; suspect → Flag
    assert "Smith J" in html
    assert "Park S" in html
    assert "Doe J" in html


def test_triage_editor_export_buttons(triage_cits):
    html = build_citation_triage_editor(triage_cits)
    assert "Copy as JSON" in html


def test_triage_editor_empty():
    html = build_citation_triage_editor([])
    assert "0 citations" in html


def test_write_citation_triage_editor(tmp_path: Path, triage_cits):
    out = tmp_path / "triage.html"
    written = write_citation_triage_editor(out, triage_cits)
    assert written == out
    assert out.exists()


# ---------------------------------------------------------------------------
# Deck-plan tuner


def test_tuner_renders():
    html = build_deckplan_tuner(
        template="Title: {{paper_title}} ({{year}})",
        samples=[
            {"paper_title": "Spatial transcriptomics method", "year": "2020"},
            {"paper_title": "Multi-modal follow-up", "year": "2023"},
        ],
    )
    assert "<!doctype html>" in html
    assert "vl-editor" in html
    assert "Title: {{paper_title}}" in html


def test_tuner_includes_sample_data():
    html = build_deckplan_tuner(
        template="Hi {{x}}",
        samples=[{"x": "Bobby"}, {"x": "Ana"}],
    )
    assert "data-context" in html
    # The sample contexts are JSON-encoded into data-context attributes
    assert "Bobby" in html
    assert "Ana" in html


def test_tuner_with_descriptions():
    html = build_deckplan_tuner(
        template="x",
        samples=[{"a": "b"}],
        sample_descriptions=["A real paper from 2024"],
    )
    assert "A real paper from 2024" in html


def test_tuner_copy_prompt_button():
    html = build_deckplan_tuner(template="x", samples=[{"a": "b"}])
    assert "Copy prompt" in html


def test_write_deckplan_tuner(tmp_path: Path):
    out = tmp_path / "tuner.html"
    written = write_deckplan_tuner(out, template="x", samples=[{"a": "b"}])
    assert written == out
    assert out.exists()
