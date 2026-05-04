"""Tests for vaultlab.research.tier_b."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from vaultlab.research.tier_b import (
    MIN_ABSTRACT_CHARS,
    apply_tier_b_response,
    build_tier_b_prompt,
    prepare_tier_b_task,
    should_run_tier_b,
    tier_b_response_schema,
)


# Minimal PaperSummary stand-in — avoids importing the real one to
# keep tests fast and uncoupled from the larger summarize module.
@dataclass
class _FakePaperSummary:
    doi: str = ""
    title: str = ""
    tier: str = "C"
    tldr: str = ""
    why_it_matters: list = field(default_factory=list)
    methods_summary: str = ""
    key_findings: list = field(default_factory=list)
    extracted_references: list = field(default_factory=list)
    extracted_at: str = ""
    extracted_via: str = "claude"
    source_pdf: str = ""


# ---------------------------------------------------------------------------
# should_run_tier_b
# ---------------------------------------------------------------------------


def test_should_run_tier_b_when_no_pdf_and_long_abstract():
    abstract = "x" * 200
    assert should_run_tier_b(pdf_acquired=False, abstract=abstract) is True


def test_should_not_run_when_pdf_acquired():
    """Tier-A wins; Tier-B is only for no-PDF papers."""
    abstract = "x" * 200
    assert should_run_tier_b(pdf_acquired=True, abstract=abstract) is False


def test_should_not_run_when_abstract_empty():
    assert should_run_tier_b(pdf_acquired=False, abstract="") is False


def test_should_not_run_when_abstract_too_short():
    short = "x" * (MIN_ABSTRACT_CHARS - 1)
    assert should_run_tier_b(pdf_acquired=False, abstract=short) is False


def test_should_run_when_abstract_exactly_at_threshold():
    at_threshold = "x" * MIN_ABSTRACT_CHARS
    assert should_run_tier_b(pdf_acquired=False, abstract=at_threshold) is True


def test_should_not_run_when_abstract_is_only_whitespace():
    assert should_run_tier_b(pdf_acquired=False, abstract="   \n  \t  ") is False


# ---------------------------------------------------------------------------
# build_tier_b_prompt
# ---------------------------------------------------------------------------


def test_prompt_includes_metadata_and_abstract():
    prompt = build_tier_b_prompt(
        paper_metadata={
            "title": "CODEX multiplexed imaging",
            "authors": ["Goltsev Y", "Nolan G"],
            "year": 2018,
            "journal": "Cell",
            "doi": "10.1016/j.cell.2018.07.010",
        },
        abstract="A 30-marker DNA-barcoded antibody imaging method.",
    )
    assert "CODEX multiplexed imaging" in prompt
    assert "Goltsev Y" in prompt
    assert "Nolan G" in prompt
    assert "2018" in prompt
    assert "Cell" in prompt
    assert "10.1016/j.cell.2018.07.010" in prompt
    assert "DNA-barcoded antibody imaging" in prompt
    assert "Return ONLY a JSON object" in prompt
    assert "[pN]" in prompt  # NO [pN] guidance present


def test_prompt_truncates_long_author_list():
    authors = [f"Author{i}" for i in range(15)]
    prompt = build_tier_b_prompt(
        paper_metadata={
            "title": "T",
            "authors": authors,
            "year": 2020,
            "journal": "J",
            "doi": "10.0/x",
        },
        abstract="some abstract" * 20,
    )
    assert "Author0" in prompt
    assert "Author4" in prompt
    assert "+ 10 others" in prompt
    # Authors past the first 5 should not appear individually
    assert "Author10" not in prompt


def test_prompt_includes_role_hint_when_provided():
    prompt = build_tier_b_prompt(
        paper_metadata={"title": "T", "authors": [], "year": 2020,
                        "journal": "J", "doi": "10.0/x"},
        abstract="abstract",
        role_hint="foundational",
    )
    assert "ROLE HINT" in prompt
    assert "foundational" in prompt


def test_prompt_omits_role_hint_when_empty():
    prompt = build_tier_b_prompt(
        paper_metadata={"title": "T", "authors": [], "year": 2020,
                        "journal": "J", "doi": "10.0/x"},
        abstract="abstract",
    )
    assert "ROLE HINT" not in prompt


# ---------------------------------------------------------------------------
# tier_b_response_schema
# ---------------------------------------------------------------------------


def test_schema_requires_three_fields():
    schema = tier_b_response_schema()
    assert schema["type"] == "object"
    assert set(schema["required"]) == {"tldr", "why_it_matters", "role_context"}
    # No methods_summary / key_findings / extracted_references in schema
    assert "methods_summary" not in schema["properties"]
    assert "key_findings" not in schema["properties"]


def test_schema_caps_why_it_matters_bullets():
    schema = tier_b_response_schema()
    why = schema["properties"]["why_it_matters"]
    assert why["minItems"] == 1
    assert why["maxItems"] == 2


# ---------------------------------------------------------------------------
# prepare_tier_b_task
# ---------------------------------------------------------------------------


def test_prepare_returns_complete_task(tmp_path: Path):
    task = prepare_tier_b_task(
        doi="10.1038/s41596-021-00556-8",
        paper_metadata={
            "title": "CODEX protocol",
            "authors": ["Black S", "Phillips D", "Hickey J"],
            "year": 2021,
            "journal": "Nature Protocols",
            "doi": "10.1038/s41596-021-00556-8",
        },
        abstract="The canonical CODEX protocol paper. " * 10,
        output_path=tmp_path / "Wiki" / "Summaries" / "10.1038_s41596-021-00556-8.md",
        role_hint="foundational-protocol",
    )

    assert task.doi == "10.1038/s41596-021-00556-8"
    assert "CODEX protocol" in task.prompt
    assert "Hickey J" in task.prompt
    assert "foundational-protocol" in task.prompt
    assert task.response_schema["type"] == "object"
    assert task.system_prompt  # non-empty
    assert task.output_path.name == "10.1038_s41596-021-00556-8.md"


# ---------------------------------------------------------------------------
# apply_tier_b_response
# ---------------------------------------------------------------------------


def test_apply_response_sets_tier_b_and_fields():
    summary = _FakePaperSummary(doi="10.0/x", title="Test paper")
    response = {
        "tldr": "First sentence. Second sentence.",
        "why_it_matters": [
            "It is widely cited.",
            "It anchors the methodology lineage.",
        ],
        "role_context": "This paper defines the protocol used by the field.",
    }
    apply_tier_b_response(summary=summary, response=response)

    assert summary.tier == "B"
    assert summary.tldr == "First sentence. Second sentence."
    assert summary.why_it_matters == [
        "It is widely cited.",
        "It anchors the methodology lineage.",
    ]
    assert "Tier-B summary provenance" in summary.methods_summary
    assert "Role context" in summary.methods_summary
    assert "defines the protocol" in summary.methods_summary
    # Tier-B leaves these empty by design
    assert summary.key_findings == []
    assert summary.extracted_references == []
    # Provenance fields populated
    assert summary.extracted_via == "claude-tier-b"
    assert summary.extracted_at  # ISO timestamp populated
    assert summary.source_pdf == ""


def test_apply_response_handles_missing_role_context():
    summary = _FakePaperSummary()
    response = {
        "tldr": "TL;DR.",
        "why_it_matters": ["Why."],
        # role_context omitted
    }
    apply_tier_b_response(summary=summary, response=response)

    assert summary.tier == "B"
    # methods_summary still has provenance line, but no role-context line
    assert "Tier-B summary provenance" in summary.methods_summary
    assert "Role context" not in summary.methods_summary


def test_apply_response_handles_empty_response():
    """Defensive: an LLM that returns empty/None fields shouldn't crash."""
    summary = _FakePaperSummary()
    response: dict = {}
    apply_tier_b_response(summary=summary, response=response)

    assert summary.tier == "B"
    assert summary.tldr == ""
    assert summary.why_it_matters == []


def test_apply_response_strips_whitespace():
    summary = _FakePaperSummary()
    response = {
        "tldr": "  TL;DR.  \n",
        "why_it_matters": ["bullet 1"],
        "role_context": "  trimmed.  ",
    }
    apply_tier_b_response(summary=summary, response=response)

    assert summary.tldr == "TL;DR."
    # role_context appears trimmed in methods_summary
    assert "trimmed." in summary.methods_summary
    assert "  trimmed.  " not in summary.methods_summary
