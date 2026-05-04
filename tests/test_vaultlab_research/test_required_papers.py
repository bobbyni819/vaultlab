"""Tests for vaultlab.research.required_papers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vaultlab.research.required_papers import (
    apply_required_to_picks,
    load_required_dois_from_project_config,
    normalize_dois,
    save_required_dois_to_project_config,
)


def test_normalize_strips_prefixes_and_lowercases():
    inputs = [
        "10.1038/x1",
        "  10.1038/X2  ",
        "doi:10.1038/x3",
        "https://doi.org/10.1038/x4",
        "http://doi.org/10.1038/x5",
        "DOI:10.1038/X6",
    ]
    result = normalize_dois(inputs)
    assert result == [
        "10.1038/x1",
        "10.1038/x2",
        "10.1038/x3",
        "10.1038/x4",
        "10.1038/x5",
        "10.1038/x6",
    ]


def test_normalize_drops_empty_and_dedupes():
    inputs = ["10.1/a", "", "10.1/A", "  ", "10.1/b", None]
    result = normalize_dois(inputs)
    assert result == ["10.1/a", "10.1/b"]  # dedupe (case-insensitive)


def test_apply_required_pins_existing_picks_to_top():
    picks = [
        {"doi": "10.1/recent", "rank": 1, "composite_score": 14.0},
        {"doi": "10.1/foundational", "rank": 5, "composite_score": 9.0},
        {"doi": "10.1/medium", "rank": 3, "composite_score": 11.0},
    ]
    result = apply_required_to_picks(
        picks=picks,
        required_dois=["10.1/foundational"],
    )

    assert result[0]["doi"] == "10.1/foundational"
    assert result[0]["rank"] == 1
    assert result[0]["required"] is True
    assert {p["doi"] for p in result[1:]} == {"10.1/recent", "10.1/medium"}
    # Ranks rewritten in order
    assert [p["rank"] for p in result] == [1, 2, 3]


def test_apply_required_synthesizes_entry_from_candidate_pool():
    picks = [{"doi": "10.1/a", "rank": 1}]
    candidate_pool = {
        "10.1/required": {
            "title": "Foundational paper",
            "year": 2018,
            "og_score": 0.5,
            "has_pdf": False,
            "is_seed": False,
        },
    }
    result = apply_required_to_picks(
        picks=picks,
        required_dois=["10.1/required"],
        candidate_pool=candidate_pool,
    )

    assert result[0]["doi"] == "10.1/required"
    assert result[0]["title"] == "Foundational paper"
    assert result[0]["required"] is True
    assert result[0]["composite_score"] == float("inf")
    assert result[1]["doi"] == "10.1/a"


def test_apply_required_warns_when_doi_unknown(caplog):
    """A required DOI not in picks AND not in candidate pool gets logged."""
    picks = [{"doi": "10.1/a", "rank": 1}]
    with caplog.at_level("WARNING"):
        result = apply_required_to_picks(
            picks=picks,
            required_dois=["10.1/missing"],
        )
    # The unknown DOI is dropped; original picks stand.
    assert result == [{"doi": "10.1/a", "rank": 1}]
    assert any("10.1/missing" in rec.message for rec in caplog.records)


def test_apply_required_idempotent_when_already_top_ranked():
    picks = [
        {"doi": "10.1/required", "rank": 1, "composite_score": 14.0},
        {"doi": "10.1/other", "rank": 2, "composite_score": 9.0},
    ]
    result = apply_required_to_picks(
        picks=picks,
        required_dois=["10.1/required"],
    )

    assert result[0]["doi"] == "10.1/required"
    assert result[0]["rank"] == 1
    assert result[0]["required"] is True
    assert result[1]["doi"] == "10.1/other"
    assert result[1]["rank"] == 2


def test_apply_required_handles_empty_required_list():
    picks = [{"doi": "10.1/a", "rank": 1}, {"doi": "10.1/b", "rank": 2}]
    result = apply_required_to_picks(picks=picks, required_dois=[])
    assert result == picks  # unchanged


def test_load_required_from_project_config(tmp_path: Path):
    config_path = tmp_path / ".vaultlab-project.json"
    config_path.write_text(
        json.dumps({"always_include": ["10.1/foo", "https://doi.org/10.1/BAR"]}),
        encoding="utf-8",
    )

    result = load_required_dois_from_project_config(project_dir=tmp_path)
    assert result == ["10.1/foo", "10.1/bar"]  # normalized


def test_load_required_returns_empty_when_no_config(tmp_path: Path):
    assert load_required_dois_from_project_config(project_dir=tmp_path) == []


def test_load_required_returns_empty_when_field_missing(tmp_path: Path):
    config_path = tmp_path / ".vaultlab-project.json"
    config_path.write_text(json.dumps({"slug": "test-project"}), encoding="utf-8")

    assert load_required_dois_from_project_config(project_dir=tmp_path) == []


def test_save_required_writes_to_project_config(tmp_path: Path):
    save_required_dois_to_project_config(
        project_dir=tmp_path,
        required_dois=["10.1/foo", "10.1/BAR"],
    )

    config_path = tmp_path / ".vaultlab-project.json"
    data = json.loads(config_path.read_text(encoding="utf-8"))
    assert data["always_include"] == ["10.1/foo", "10.1/bar"]


def test_save_preserves_other_config_fields(tmp_path: Path):
    config_path = tmp_path / ".vaultlab-project.json"
    config_path.write_text(
        json.dumps({"slug": "my-project", "topic": "X"}),
        encoding="utf-8",
    )

    save_required_dois_to_project_config(
        project_dir=tmp_path,
        required_dois=["10.1/foo"],
    )

    data = json.loads(config_path.read_text(encoding="utf-8"))
    assert data["slug"] == "my-project"
    assert data["topic"] == "X"
    assert data["always_include"] == ["10.1/foo"]
