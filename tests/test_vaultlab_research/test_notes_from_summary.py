"""Tests for vaultlab.research.notes_from_summary."""

from __future__ import annotations

from pathlib import Path

import pytest

from vaultlab.research.notes_from_summary import (
    SummaryRecord,
    _compose_extended_walkthrough,
    _compose_script,
    _derive_hook,
    _derive_key_claim,
    _extract_bullets,
    _extract_key_terms,
    _strip_md,
    _trim_to_word_target,
    parse_summary_file,
    speaker_notes_from_summary,
)


SAMPLE_SUMMARY = """\
---
doi: 10.1038/s41586-022-05672-3
title: 'Single-cell spatial landscapes of the lung tumour immune microenvironment'
authors:
- M. Sorin
- M. Rezanejad
year: 2023
journal: Nature
tier: A
role_in_set: keystone
---

## TL;DR

Sorin et al. apply 35-plex IMC to 416 LUAD patients (1.64M cells) and show
that **spatial cell-cell interactions predict survival/progression beyond
cell frequency alone**. A ResNet50 deep-learning model on raw IMC
predicts post-surgical progression at 95.9% accuracy from a single 1-mm²
core. CN21 (B-cell hot, Treg-low) is protective; CN25 adds CD4+ Th.

## Why it matters in this lineage

This is the empirical case for ABM-style spatial models in lung over
compartmental ones. Cell *frequencies* alone do not predict outcome —
*neighborhoods* do.

## Methods (extracted summary)

- 35-plex IMC (Hyperion) on FFPE LUAD cores; Mask R-CNN segmentation.
- Permutation-test pairwise spatial interaction (cells within 6 pixels).
- Cellular neighbourhoods: 10-NN windows clustered by MiniBatchKMeans → 30 CNs.
- Deep learning: ResNet50 → sparse PCA → SVM (RBF), 5-fold CV.

## Key findings (with [page] provenance)

- IMC 35-plex, 416 LUAD patients, 1.64M cells.
- 30 cellular neighbourhoods defined.
- ResNet50 95.9% progression accuracy [Fig. 4e].
- Validation cohort: 93.3% [p. 553].
"""


@pytest.fixture
def summary_file(tmp_path: Path) -> Path:
    p = tmp_path / "10.1038_s41586-022-05672-3.md"
    p.write_text(SAMPLE_SUMMARY, encoding="utf-8")
    return p


# --- parse_summary_file ---


def test_parse_extracts_frontmatter_fields(summary_file):
    r = parse_summary_file(summary_file)
    assert r.doi == "10.1038/s41586-022-05672-3"
    assert r.year == 2023
    assert r.journal == "Nature"
    assert r.tier == "A"
    assert r.role_in_set == "keystone"
    assert r.title.startswith("Single-cell spatial")


def test_parse_extracts_authors_list(summary_file):
    r = parse_summary_file(summary_file)
    assert r.authors == ["M. Sorin", "M. Rezanejad"]


def test_parse_extracts_tldr_section(summary_file):
    r = parse_summary_file(summary_file)
    assert "Sorin et al. apply 35-plex IMC" in r.tldr
    assert "95.9% accuracy" in r.tldr


def test_parse_extracts_methods_bullets(summary_file):
    r = parse_summary_file(summary_file)
    assert len(r.methods) == 4
    assert "Hyperion" in r.methods[0]
    assert "10-NN" in r.methods[2]


def test_parse_extracts_key_findings_bullets(summary_file):
    r = parse_summary_file(summary_file)
    assert len(r.key_findings) == 4
    assert "1.64M cells" in r.key_findings[0]


def test_parse_returns_empty_record_on_missing_frontmatter(tmp_path):
    p = tmp_path / "x.md"
    p.write_text("# Just a title\n\nbody", encoding="utf-8")
    r = parse_summary_file(p)
    assert r.doi == ""
    assert r.year is None
    assert r.tldr == ""


# --- SummaryRecord helpers ---


def test_authors_short_with_two_authors(summary_file):
    r = parse_summary_file(summary_file)
    assert r.authors_short() == "Sorin et al. 2023"


def test_authors_short_single_author():
    r = SummaryRecord(doi="x", title="t", authors=["John Doe"], year=2024)
    assert r.authors_short() == "Doe 2024"


def test_authors_short_no_authors():
    r = SummaryRecord(doi="x", title="t", year=2024)
    assert r.authors_short() == "(2024)"


def test_journal_short_substitutes_known_names():
    r = SummaryRecord(doi="x", title="t", journal="Cell Systems")
    assert r.journal_short() == "Cell Sys"

    r = SummaryRecord(doi="x", title="t", journal="Frontiers in Microbiology")
    assert r.journal_short() == "Front Microbiol"


def test_journal_short_passthrough_unknown():
    r = SummaryRecord(doi="x", title="t", journal="J Some Journal")
    assert r.journal_short() == "J Some Journal"


def test_citation_footer_combines_authors_journal(summary_file):
    r = parse_summary_file(summary_file)
    assert r.citation_footer() == "Sorin et al. 2023 | Nature"


# --- bullet extraction ---


def test_extract_bullets_handles_dash_and_star():
    text = "- one\n- two\n* three"
    assert _extract_bullets(text) == ["one", "two", "three"]


def test_extract_bullets_joins_continuation_lines():
    text = "- one\n  continued\n- two"
    bullets = _extract_bullets(text)
    assert "one continued" in bullets[0]


def test_extract_bullets_empty_section():
    assert _extract_bullets("") == []


# --- key term extraction ---


def test_extract_key_terms_pulls_acronyms(summary_file):
    r = parse_summary_file(summary_file)
    terms = _extract_key_terms(r)
    assert "IMC" in terms
    assert "LUAD" in terms


def test_extract_key_terms_caps_at_max():
    r = SummaryRecord(
        doi="x", title="t",
        tldr="ABC DEF GHI JKL MNO PQR STU VWX YZA BCD",
        year=2024,
    )
    terms = _extract_key_terms(r, max_terms=3)
    assert len(terms) == 3


# --- strip markdown ---


def test_strip_md_removes_bold_italic():
    assert _strip_md("**bold** and *italic*") == "bold and italic"


def test_strip_md_unwraps_wikilinks():
    assert "Author Year" in _strip_md("[[10.1234_x|Author Year]]")


def test_strip_md_normalizes_whitespace():
    out = _strip_md("a\n\n\nb   c")
    assert out == "a b c"


# --- composers ---


def test_compose_script_uses_tldr(summary_file):
    r = parse_summary_file(summary_file)
    s = _compose_script(r)
    assert "Sorin" in s
    assert "**" not in s  # markdown stripped
    # Within reasonable word range
    n_words = len(s.split())
    assert 50 < n_words <= 350


def test_compose_extended_walkthrough_has_section_markers(summary_file):
    r = parse_summary_file(summary_file)
    w = _compose_extended_walkthrough(r)
    assert "BACKGROUND" in w
    assert "WHY IT MATTERS" in w
    assert "METHODS" in w
    assert "KEY FINDINGS" in w


def test_compose_extended_walkthrough_audience_familiar_skips_why(summary_file):
    r = parse_summary_file(summary_file)
    w = _compose_extended_walkthrough(r, audience_familiar=True)
    assert "WHY IT MATTERS" not in w
    assert "BACKGROUND" in w


def test_trim_to_word_target_respects_sentence_boundary():
    text = "Sentence one. Sentence two. Sentence three. Sentence four."
    out = _trim_to_word_target(text, target_words=4)
    # Should end on a period
    assert out.endswith(".")


def test_trim_to_word_target_passthrough_short_text():
    text = "short text"
    assert _trim_to_word_target(text, target_words=100) == text


# --- speaker_notes_from_summary ---


def test_speaker_notes_three_tiers_present(summary_file):
    r = parse_summary_file(summary_file)
    notes = speaker_notes_from_summary(r)
    # mental_map keys
    assert notes["hook"]
    assert notes["key_claim"]
    assert notes["evidence"]
    assert isinstance(notes["key_terms"], list)
    # Two-tier deep
    assert notes["script"]
    assert notes["extended_walkthrough"]


def test_speaker_notes_overrides_supersede_auto(summary_file):
    r = parse_summary_file(summary_file)
    notes = speaker_notes_from_summary(
        r,
        hook="custom hook",
        script="custom script verbatim",
    )
    assert notes["hook"] == "custom hook"
    assert notes["script"] == "custom script verbatim"
    # Non-overridden still auto
    assert notes["extended_walkthrough"]


def test_speaker_notes_handles_missing_sections():
    """Sparse summary still produces a usable notes dict."""
    r = SummaryRecord(
        doi="10.1/x", title="Test", authors=["X. Y."], year=2024,
        tldr="A short TL;DR.",
    )
    notes = speaker_notes_from_summary(r)
    assert notes["hook"]
    assert notes["script"]
    # extended_walkthrough may be short but should exist
    assert "BACKGROUND" in notes["extended_walkthrough"]
