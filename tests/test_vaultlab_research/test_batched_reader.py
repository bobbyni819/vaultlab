"""Tests for vaultlab.research.batched_reader."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from vaultlab.research.batched_reader import (
    DEFAULT_BATCH_SIZE,
    MAX_BATCH_PDF_BYTES,
    MIN_BATCH_SIZE,
    apply_batch_response_to_summary,
    batch_response_schema,
    build_batch_prompt,
    parse_batch_response,
    prepare_batch_task,
    should_batch,
)


@dataclass
class _FakePaperSummary:
    doi: str = ""
    tier: str = "C"
    tldr: str = ""
    why_it_matters: list = field(default_factory=list)
    methods_summary: str = ""
    key_findings: list = field(default_factory=list)
    extracted_references: list = field(default_factory=list)
    extracted_at: str = ""
    extracted_via: str = "claude"
    source_pdf: str = ""


def _fake_pdf(path: Path, size_bytes: int = 1024) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"X" * size_bytes)
    return path


# ---------------------------------------------------------------------------
# should_batch
# ---------------------------------------------------------------------------


def test_should_batch_true_for_two_or_more_existing_pdfs(tmp_path: Path):
    p1 = _fake_pdf(tmp_path / "a.pdf")
    p2 = _fake_pdf(tmp_path / "b.pdf")
    specs = [
        ("10.1/a", p1, {}),
        ("10.1/b", p2, {}),
    ]
    assert should_batch(specs) is True


def test_should_batch_false_for_single_paper(tmp_path: Path):
    p1 = _fake_pdf(tmp_path / "a.pdf")
    assert should_batch([("10.1/a", p1, {})]) is False


def test_should_batch_false_for_empty_list():
    assert should_batch([]) is False


def test_should_batch_false_when_pdf_missing(tmp_path: Path):
    p1 = _fake_pdf(tmp_path / "a.pdf")
    missing = tmp_path / "nonexistent.pdf"
    specs = [("10.1/a", p1, {}), ("10.1/missing", missing, {})]
    assert should_batch(specs) is False


def test_should_batch_false_when_pdf_path_none(tmp_path: Path):
    p1 = _fake_pdf(tmp_path / "a.pdf")
    specs = [("10.1/a", p1, {}), ("10.1/none", None, {})]
    assert should_batch(specs) is False


def test_should_batch_respects_total_size_cap(tmp_path: Path):
    p1 = _fake_pdf(tmp_path / "a.pdf", size_bytes=600)
    p2 = _fake_pdf(tmp_path / "b.pdf", size_bytes=600)
    # Total = 1200 bytes, cap = 1000 → should not batch
    specs = [("10.1/a", p1, {}), ("10.1/b", p2, {})]
    assert should_batch(specs, max_total_bytes=1000) is False
    # Cap = 2000 → should batch
    assert should_batch(specs, max_total_bytes=2000) is True


# ---------------------------------------------------------------------------
# build_batch_prompt
# ---------------------------------------------------------------------------


def test_prompt_includes_each_paper_with_numbered_label(tmp_path: Path):
    specs = [
        (
            "10.1/a", tmp_path / "a.pdf",
            {"title": "Alpha paper", "authors": ["Author A"], "year": 2020,
             "journal": "JournalA"},
        ),
        (
            "10.1/b", tmp_path / "b.pdf",
            {"title": "Beta paper", "authors": ["Author B"], "year": 2021,
             "journal": "JournalB"},
        ),
    ]
    prompt = build_batch_prompt(pdf_specs=specs)

    assert "PAPER 1" in prompt
    assert "PAPER 2" in prompt
    assert "Alpha paper" in prompt
    assert "Beta paper" in prompt
    assert "Author A" in prompt
    assert "Author B" in prompt
    assert "10.1/a" in prompt
    assert "10.1/b" in prompt


def test_prompt_includes_role_hints_when_provided(tmp_path: Path):
    specs = [
        ("10.1/a", tmp_path / "a.pdf", {"title": "T", "authors": [],
                                        "year": 2020, "journal": "J"}),
    ]
    prompt = build_batch_prompt(
        pdf_specs=specs,
        role_hints={"10.1/a": "foundational"},
    )
    assert "Role hint: foundational" in prompt


def test_prompt_truncates_long_author_lists(tmp_path: Path):
    long_authors = [f"Author{i}" for i in range(15)]
    specs = [
        ("10.1/a", tmp_path / "a.pdf",
         {"title": "T", "authors": long_authors, "year": 2020, "journal": "J"}),
    ]
    prompt = build_batch_prompt(pdf_specs=specs)
    assert "Author0" in prompt
    assert "Author4" in prompt
    assert "+ 10 others" in prompt
    assert "Author10" not in prompt


def test_prompt_lists_all_dois_in_output_format_block(tmp_path: Path):
    specs = [
        ("10.1/a", tmp_path / "a.pdf", {}),
        ("10.1/b", tmp_path / "b.pdf", {}),
        ("10.1/c", tmp_path / "c.pdf", {}),
    ]
    prompt = build_batch_prompt(pdf_specs=specs)
    # Each DOI should be referenced in the JSON template at the bottom
    assert prompt.count("10.1/a") >= 2  # once in header, once in JSON
    assert prompt.count("10.1/b") >= 2
    assert prompt.count("10.1/c") >= 2


# ---------------------------------------------------------------------------
# batch_response_schema
# ---------------------------------------------------------------------------


def test_schema_requires_summaries_key():
    schema = batch_response_schema(["10.1/a", "10.1/b"])
    assert schema["type"] == "object"
    assert "summaries" in schema["required"]


def test_schema_requires_each_doi_key():
    schema = batch_response_schema(["10.1/a", "10.1/b"])
    summaries_schema = schema["properties"]["summaries"]
    assert "10.1/a" in summaries_schema["required"]
    assert "10.1/b" in summaries_schema["required"]


def test_schema_lowercases_dois():
    schema = batch_response_schema(["10.1/A", "10.1/B"])
    summaries_schema = schema["properties"]["summaries"]
    assert "10.1/a" in summaries_schema["required"]
    assert "10.1/b" in summaries_schema["required"]


# ---------------------------------------------------------------------------
# prepare_batch_task
# ---------------------------------------------------------------------------


def test_prepare_returns_complete_task(tmp_path: Path):
    p1 = _fake_pdf(tmp_path / "a.pdf")
    p2 = _fake_pdf(tmp_path / "b.pdf")
    specs = [
        ("10.1/A", p1, {"title": "T1", "authors": [], "year": 2020,
                        "journal": "J"}),
        ("10.1/B", p2, {"title": "T2", "authors": [], "year": 2021,
                        "journal": "J"}),
    ]
    task = prepare_batch_task(pdf_specs=specs)

    assert task.dois == ["10.1/a", "10.1/b"]  # lowercased
    assert task.pdf_paths == [p1, p2]
    assert len(task.paper_metadata) == 2
    assert "T1" in task.prompt
    assert "T2" in task.prompt
    assert task.system_prompt  # non-empty


# ---------------------------------------------------------------------------
# parse_batch_response
# ---------------------------------------------------------------------------


def test_parse_extracts_per_doi_summaries():
    response = {
        "summaries": {
            "10.1/a": {"tldr": "TL;DR A"},
            "10.1/b": {"tldr": "TL;DR B"},
        },
    }
    result = parse_batch_response(response=response, dois=["10.1/a", "10.1/b"])
    assert result == {
        "10.1/a": {"tldr": "TL;DR A"},
        "10.1/b": {"tldr": "TL;DR B"},
    }


def test_parse_lowercases_doi_keys_in_response():
    response = {
        "summaries": {
            "10.1/A": {"tldr": "uppercase doi"},
        },
    }
    result = parse_batch_response(response=response, dois=["10.1/a"])
    assert "10.1/a" in result
    assert result["10.1/a"]["tldr"] == "uppercase doi"


def test_parse_warns_about_unexpected_dois(caplog):
    response = {
        "summaries": {
            "10.1/expected": {"tldr": "ok"},
            "10.1/unexpected": {"tldr": "wrong"},
        },
    }
    with caplog.at_level("WARNING"):
        result = parse_batch_response(
            response=response, dois=["10.1/expected"]
        )
    assert "10.1/expected" in result
    assert "10.1/unexpected" not in result
    assert any("10.1/unexpected" in rec.message for rec in caplog.records)


def test_parse_warns_about_missing_dois(caplog):
    response = {
        "summaries": {
            "10.1/a": {"tldr": "ok"},
        },
    }
    with caplog.at_level("WARNING"):
        result = parse_batch_response(
            response=response, dois=["10.1/a", "10.1/b"]
        )
    assert set(result.keys()) == {"10.1/a"}
    assert any("10.1/b" in rec.message for rec in caplog.records)


def test_parse_returns_empty_when_summaries_key_missing():
    assert parse_batch_response(response={}, dois=["10.1/a"]) == {}
    assert parse_batch_response(
        response={"other_key": {}}, dois=["10.1/a"]
    ) == {}


def test_parse_skips_non_dict_per_paper_values(caplog):
    response = {
        "summaries": {
            "10.1/a": "not a dict",  # invalid
            "10.1/b": {"tldr": "valid"},
        },
    }
    with caplog.at_level("WARNING"):
        result = parse_batch_response(
            response=response, dois=["10.1/a", "10.1/b"]
        )
    assert "10.1/a" not in result
    assert "10.1/b" in result


# ---------------------------------------------------------------------------
# apply_batch_response_to_summary
# ---------------------------------------------------------------------------


def test_apply_sets_tier_a_and_populates_fields(tmp_path: Path):
    summary = _FakePaperSummary(doi="10.1/a")
    pdf_path = tmp_path / "a.pdf"
    pdf_path.write_bytes(b"x")
    response = {
        "tldr": "Three sentences.",
        "why_it_matters": ["bullet 1", "bullet 2"],
        "methods_summary": "Methods text.",
        "key_findings": ["finding [p1]", "finding 2 [p3]"],
        "extracted_references": [],
    }

    apply_batch_response_to_summary(
        summary=summary,
        per_paper_response=response,
        pdf_path=pdf_path,
    )

    assert summary.tier == "A"
    assert summary.tldr == "Three sentences."
    assert summary.why_it_matters == ["bullet 1", "bullet 2"]
    assert summary.methods_summary == "Methods text."
    assert summary.key_findings == ["finding [p1]", "finding 2 [p3]"]
    assert summary.extracted_via == "claude-batch"  # batch provenance marker
    assert summary.extracted_at  # ISO timestamp populated
    assert summary.source_pdf == str(pdf_path)


def test_apply_handles_missing_fields_gracefully():
    summary = _FakePaperSummary(doi="10.1/a")
    apply_batch_response_to_summary(
        summary=summary,
        per_paper_response={},
    )
    assert summary.tier == "A"
    assert summary.tldr == ""
    assert summary.why_it_matters == []
    assert summary.extracted_via == "claude-batch"
