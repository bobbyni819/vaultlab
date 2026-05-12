"""Tests for vaultlab.research.litarc_html — lit-arc HTML narrative consumer."""

from __future__ import annotations

from pathlib import Path

import pytest

from vaultlab.research.litarc_html import (
    build_litarc_report_html,
    write_litarc_report,
)


@pytest.fixture
def sample_papers() -> list[dict]:
    return [
        {
            "doi": "10.1234/a",
            "title": "First paper on spatial-tx",
            "authors": ["Smith J", "Jones K", "Lee M", "Park S", "Chen R"],
            "year": 2020,
            "journal": "Nature",
            "tier": "A",
            "year_bucket": "foundational",
            "role_in_set": "seed",
            "tldr": "A method that maps cells in tissue space.",
            "key_findings": ["finding 1", "finding 2", "finding 3", "finding 4"],
            "citation_count": 250,
        },
        {
            "doi": "10.1234/b",
            "title": "Follow-up multi-modal",
            "authors": ["Park S"],
            "year": 2023,
            "journal": "Cell",
            "tier": "B",
            "year_bucket": "validation",
            "role_in_set": "cited",
            "tldr": "Validates Smith et al. across 5 tissue types.",
            "citation_count": 80,
        },
        {
            "doi": "10.1234/c",
            "title": "Third paper",
            "year": 2024,
            "tier": "C",
            "year_bucket": "recent",
        },
    ]


@pytest.fixture
def sample_narrative() -> str:
    return """# Lit-arc overview

The field starts with **Smith et al.** establishing the foundational method.

## Validation phase

A series of validation studies extended the method:

- Park et al. across tissues
- Lee et al. with multi-modal integration

## Open questions

Citation [[10.1234/a]] anchors the narrative.
"""


def test_renders_basic_report(sample_papers, sample_narrative):
    html = build_litarc_report_html(
        topic="spatial transcriptomics",
        narrative=sample_narrative,
        papers=sample_papers,
    )
    assert "<!doctype html>" in html
    assert "spatial transcriptomics" in html
    assert "3 papers" in html


def test_renders_tier_chips(sample_papers, sample_narrative):
    html = build_litarc_report_html(topic="x", narrative=sample_narrative, papers=sample_papers)
    # Tier counts in summary
    assert "Tier A: 1" in html
    assert "Tier B: 1" in html
    assert "Tier C: 1" in html


def test_renders_narrative_with_markdown(sample_papers, sample_narrative):
    html = build_litarc_report_html(topic="x", narrative=sample_narrative, papers=sample_papers)
    # Heading
    assert "<h3>Lit-arc overview</h3>" in html or "<h4>Lit-arc overview</h4>" in html
    # Bold
    assert "<strong>Smith et al.</strong>" in html
    # Bullet list
    assert "<ul>" in html
    assert "Park et al. across tissues" in html
    # Wikilink styling
    assert "[[ 10.1234/a ]]" in html


def test_paper_cards_carry_metadata(sample_papers, sample_narrative):
    html = build_litarc_report_html(topic="x", narrative=sample_narrative, papers=sample_papers)
    assert "First paper on spatial-tx" in html
    assert "Smith J, Jones K, Lee M" in html  # first 3 authors
    assert "+ 2" in html  # plus 2 more
    assert "cites: 250" in html
    assert "Nature" in html


def test_filter_bar_renders_per_tier(sample_papers, sample_narrative):
    html = build_litarc_report_html(topic="x", narrative=sample_narrative, papers=sample_papers)
    assert 'data-filter="tier-a"' in html
    assert 'data-filter="tier-b"' in html
    assert 'data-filter="tier-c"' in html


def test_citation_graph_appears_when_provided(sample_papers, sample_narrative):
    html = build_litarc_report_html(
        topic="x",
        narrative=sample_narrative,
        papers=sample_papers,
        citations=[
            ("10.1234/b", "10.1234/a"),
            ("10.1234/c", "10.1234/a"),
            ("10.1234/c", "10.1234/b"),
        ],
    )
    assert "Citation graph" in html
    assert "<svg" in html


def test_no_citation_graph_when_no_citations(sample_papers, sample_narrative):
    html = build_litarc_report_html(topic="x", narrative=sample_narrative, papers=sample_papers)
    assert "Citation graph" not in html


def test_no_citation_graph_when_too_few(sample_papers, sample_narrative):
    """Fewer than 3 papers in the citation edges — graph is hidden."""
    html = build_litarc_report_html(
        topic="x",
        narrative=sample_narrative,
        papers=sample_papers,
        citations=[("10.1234/a", "10.1234/b")],
    )
    assert "Citation graph" not in html


def test_xss_safe_against_evil_paper_title():
    papers = [
        {
            "doi": "x",
            "title": "<script>alert(1)</script>",
            "tldr": "<img src=x onerror=y>",
        }
    ]
    html = build_litarc_report_html(topic="x", narrative="x", papers=papers)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    assert "<img src=x onerror" not in html


def test_empty_papers():
    html = build_litarc_report_html(topic="x", narrative="hello", papers=[])
    assert "<!doctype html>" in html
    assert "No papers in corpus" in html


def test_write_litarc_report(tmp_path: Path, sample_papers, sample_narrative):
    out = tmp_path / "arc.html"
    written = write_litarc_report(out, topic="x", narrative=sample_narrative, papers=sample_papers)
    assert written == out
    assert out.exists()


def test_scope_appears_in_eyebrow(sample_papers, sample_narrative):
    html = build_litarc_report_html(
        topic="x",
        narrative=sample_narrative,
        papers=sample_papers,
        scope="review_paper_strict",
    )
    assert "review_paper_strict" in html
