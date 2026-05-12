"""Tests for vaultlab.slides.preview_html — keynav deck preview."""

from __future__ import annotations

from pathlib import Path

import pytest

from vaultlab.slides.preview_html import (
    build_deck_preview_html,
    write_deck_preview,
)


@pytest.fixture
def sample_plan() -> dict:
    return {
        "title": "Multi-lung review",
        "slides": [
            {
                "type": "title",
                "title": "Multi-lung review",
                "subtitle": "Spatial transcriptomics meets host-pathogen biology",
            },
            {
                "type": "figure",
                "title": "Method overview",
                "bullets": ["Method maps cells", "Across 3 tissue types"],
                "caption": "Adapted from Smith et al. 2020.",
                "citation_source": "Fig. 1 of [1]",
            },
            {
                "type": "bullets",
                "title": "Findings",
                "bullets": ["A", "B", "C"],
                "references": ["Smith 2020 — Nature", "Park 2023 — Cell"],
            },
        ],
    }


def test_renders_basic_preview(sample_plan):
    html = build_deck_preview_html(sample_plan)
    assert "<!doctype html>" in html
    assert "Multi-lung review" in html
    assert "3 slides" in html


def test_keynav_deck_present(sample_plan):
    html = build_deck_preview_html(sample_plan)
    assert "vl-deck" in html
    assert "Prev" in html
    assert "Next" in html
    assert "1 / 3" in html


def test_slide_content_renders(sample_plan):
    html = build_deck_preview_html(sample_plan)
    # Each slide title is in the deck
    assert "Method overview" in html
    assert "Findings" in html
    # Bullets
    assert "<li>Method maps cells</li>" in html
    assert "<li>A</li>" in html
    # Caption
    assert "Adapted from Smith et al. 2020." in html
    # Source
    assert "Fig. 1 of [1]" in html


def test_references_block(sample_plan):
    html = build_deck_preview_html(sample_plan)
    assert "References" in html
    assert "Smith 2020 — Nature" in html
    assert "Park 2023 — Cell" in html


def test_slide_type_shown(sample_plan):
    html = build_deck_preview_html(sample_plan)
    # types appear in uppercase eyebrow above slide content
    assert "title" in html.lower()
    assert "figure" in html.lower()


def test_empty_deck():
    html = build_deck_preview_html({"title": "x", "slides": []})
    assert "<!doctype html>" in html
    assert "(empty deck)" in html


def test_figure_embedding_when_file_exists(tmp_path: Path, sample_plan):
    # Create a tiny PNG (1x1 pixel)
    png = tmp_path / "f.png"
    png.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xff"
        b"\xff?\x03\x00\x05\xfe\x02\xfe\xa3\x35\x81\x84\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    plan = {
        "title": "x",
        "slides": [
            {"type": "figure", "title": "S1", "figure": str(png)},
        ],
    }
    html = build_deck_preview_html(plan, embed_figures=True)
    assert "data:image/png;base64," in html


def test_figure_missing_shows_placeholder():
    plan = {
        "title": "x",
        "slides": [
            {"type": "figure", "title": "S1", "figure": "/nonexistent/path.png"},
        ],
    }
    html = build_deck_preview_html(plan)
    assert "figure not found" in html


def test_embed_figures_false_shows_path():
    plan = {
        "title": "x",
        "slides": [
            {"type": "figure", "title": "S1", "figure": "/some/path.png"},
        ],
    }
    html = build_deck_preview_html(plan, embed_figures=False)
    assert "/some/path.png" in html
    assert "data:image/png" not in html


def test_xss_safe_against_evil_slide_title():
    plan = {
        "title": "x",
        "slides": [
            {"type": "title", "title": "<script>alert(1)</script>", "bullets": []},
        ],
    }
    html = build_deck_preview_html(plan)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_write_deck_preview(tmp_path: Path, sample_plan):
    out = tmp_path / "preview.html"
    written = write_deck_preview(out, sample_plan)
    assert written == out
    assert out.exists()
