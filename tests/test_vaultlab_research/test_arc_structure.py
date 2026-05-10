"""Tests for variable-length arc structures + binning integration."""

from __future__ import annotations

import pytest

from vaultlab.research.arc_structure import (
    REVIEW_PAPER,
    SHORT,
    STANDARD,
    get_named_structure,
    make_custom_structure,
    resolve_structure,
)
from vaultlab.research.binning import (
    binning_response_schema,
    prepare_binning_task,
    render_binning_from_response,
)
from vaultlab.research.corpus import Corpus
from vaultlab.research.graph_metrics import compute_metrics
from vaultlab.research.paper import Paper

# ---------------------------------------------------------------------------
# ArcStructure module
# ---------------------------------------------------------------------------


def test_short_template_has_three_sections():
    assert len(SHORT.sections) == 3
    assert [s.id for s in SHORT.sections] == ["history", "development", "sota"]
    assert SHORT.total_target_paragraphs == 3


def test_standard_template_has_six_sections():
    assert len(STANDARD.sections) == 6
    assert "foundations" in STANDARD.section_ids
    assert "open_questions" in STANDARD.section_ids


def test_review_paper_template_has_ten_sections_and_long_paragraph_total():
    assert len(REVIEW_PAPER.sections) == 10
    assert REVIEW_PAPER.total_target_paragraphs >= 12


def test_resolve_structure_none_returns_short():
    assert resolve_structure(None) is SHORT


def test_resolve_structure_string_looks_up_template():
    assert resolve_structure("standard") is STANDARD
    assert resolve_structure("review-paper") is REVIEW_PAPER
    # Underscore alias
    assert resolve_structure("review_paper") is REVIEW_PAPER


def test_resolve_structure_passes_through_arc_structure():
    custom = make_custom_structure(
        "custom",
        sections=[{"id": "intro", "title": "Intro", "criterion": "preamble"}],
    )
    assert resolve_structure(custom) is custom


def test_resolve_structure_unknown_string_raises():
    with pytest.raises(KeyError):
        resolve_structure("not-a-template")


def test_make_custom_structure_validates_required_fields():
    with pytest.raises(ValueError):
        make_custom_structure(
            "broken",
            sections=[{"id": "x", "title": "X"}],  # missing criterion
        )


def test_make_custom_structure_rejects_duplicate_ids():
    with pytest.raises(ValueError):
        make_custom_structure(
            "broken",
            sections=[
                {"id": "x", "title": "X", "criterion": "c"},
                {"id": "x", "title": "X2", "criterion": "c2"},
            ],
        )


def test_make_custom_structure_rejects_empty_sections():
    with pytest.raises(ValueError):
        make_custom_structure("broken", sections=[])


def test_section_by_id_returns_match_or_none():
    assert SHORT.section_by_id("history") is not None
    assert SHORT.section_by_id("nonexistent") is None


# ---------------------------------------------------------------------------
# Binning integration
# ---------------------------------------------------------------------------


def _seeds() -> list[Paper]:
    return [
        Paper(
            title="Goltsev",
            authors=["Goltsev Y"],
            year=2018,
            doi="10.1/goltsev",
            citation_count=100,
            source_api="pubmed",
            abstract="We introduce CODEX...",
        ),
        Paper(
            title="Schurch",
            authors=["Schurch C"],
            year=2020,
            doi="10.1/schurch",
            citation_count=80,
            source_api="pubmed",
            abstract="We apply CODEX to colorectal cancer...",
        ),
    ]


def _corpus() -> Corpus:
    seeds = _seeds()
    corpus = Corpus(topic="CODEX", seeds=seeds, papers={s.doi: s for s in seeds})
    compute_metrics(corpus)
    return corpus


def test_prepare_binning_task_default_uses_short_structure():
    """Backward compat: no ``arc_structure`` arg → 3-bucket SHORT."""
    task = prepare_binning_task(_corpus(), "CODEX")
    assert task.valid_section_ids == ("history", "development", "sota")


def test_prepare_binning_task_with_standard_structure():
    """STANDARD structure produces 6 valid section IDs."""
    task = prepare_binning_task(_corpus(), "CODEX", arc_structure=STANDARD)
    assert len(task.valid_section_ids) == 6
    assert "foundations" in task.valid_section_ids
    assert "open_questions" in task.valid_section_ids


def test_prepare_binning_task_with_review_paper_structure():
    """REVIEW_PAPER structure produces 10 valid section IDs."""
    task = prepare_binning_task(_corpus(), "CODEX", arc_structure=REVIEW_PAPER)
    assert len(task.valid_section_ids) == 10
    assert "introduction" in task.valid_section_ids
    assert "limitations_and_future" in task.valid_section_ids


def test_binning_prompt_embeds_section_criteria():
    """The prompt body lists each section's criterion."""
    task = prepare_binning_task(_corpus(), "CODEX", arc_structure=STANDARD)
    # Each section's criterion must appear in the prompt
    for section in STANDARD.sections:
        # Criterion is the LLM hint — the prompt embeds it verbatim
        assert section.criterion in task.prompt
        # The id appears in the section list
        assert section.id in task.prompt


def test_binning_response_schema_enum_matches_structure():
    """Schema enum lists the structure's section IDs."""
    schema = binning_response_schema(STANDARD.section_ids)
    bucket_enum = schema["properties"]["assignments"]["items"]["properties"]["bucket"]["enum"]
    assert sorted(bucket_enum) == sorted(STANDARD.section_ids)


def test_binning_response_schema_default_is_legacy_three_buckets():
    """No structure passed → legacy enum (back-compat)."""
    schema = binning_response_schema()
    bucket_enum = schema["properties"]["assignments"]["items"]["properties"]["bucket"]["enum"]
    assert sorted(bucket_enum) == ["development", "history", "sota"]


def test_render_binning_accepts_standard_structure_buckets():
    """LLM responses with STANDARD section IDs are accepted, not dropped."""
    task = prepare_binning_task(_corpus(), "CODEX", arc_structure=STANDARD)
    response = {
        "assignments": [
            {
                "doi": "10.1/goltsev",
                "bucket": "seminal_methods",
                "rationale": "Goltsev introduced CODEX itself.",
            },
            {
                "doi": "10.1/schurch",
                "bucket": "applications",
                "rationale": "Schurch applies CODEX clinically.",
            },
        ]
    }
    result = render_binning_from_response(response, task)
    assert result.bucket_by_doi["10.1/goltsev"] == "seminal_methods"
    assert result.bucket_by_doi["10.1/schurch"] == "applications"


def test_render_binning_drops_invalid_section_id():
    """LLM picking a bucket NOT in the structure → no rationale, fallback path.

    Known limitation: the deterministic fallback (corpus.metrics.year_buckets)
    still produces history/development/sota labels regardless of arc_structure,
    so a STANDARD-structure task may end up with legacy bucket values when
    the LLM gives nothing usable. The validation here is that the LLM's
    INVALID assignment didn't make it into the result with rationale.
    """
    task = prepare_binning_task(_corpus(), "CODEX", arc_structure=STANDARD)
    response = {
        "assignments": [
            {
                "doi": "10.1/goltsev",
                "bucket": "totally-fake-bucket",
                "rationale": "Trying to use a bogus section name.",
            },
        ]
    }
    result = render_binning_from_response(response, task)
    # The bogus bucket must be rejected — its rationale must NOT appear.
    assert "10.1/goltsev" not in result.rationale_by_doi
    # The DOI is still accounted for (filled from deterministic fallback)
    assert "10.1/goltsev" in result.bucket_by_doi


def test_render_binning_coverage_includes_all_structure_sections():
    """Coverage summary pre-seeds every structure section, even if 0."""
    task = prepare_binning_task(_corpus(), "CODEX", arc_structure=STANDARD)
    # Empty response → all DOIs fall back to deterministic
    result = render_binning_from_response({"assignments": []}, task)
    # Every STANDARD section must appear in coverage_summary
    for sid in STANDARD.section_ids:
        assert sid in result.coverage_summary


def test_get_named_structure_returns_canonical():
    assert get_named_structure("short") is SHORT
    assert get_named_structure("STANDARD") is STANDARD  # case-insensitive
