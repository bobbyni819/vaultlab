"""Tests for vaultlab.manuscript.polish."""

from __future__ import annotations

import json
from pathlib import Path

from vaultlab.manuscript.polish import (
    BRITISH_ENGLISH_PAIRS,
    POLISH_RULES,
    WORKFLOW_STEPS,
    check_sentence_length,
    check_us_spelling,
    find_rule,
    rules_by_category,
    write_polish_report,
)


def test_25_rules_present():
    assert len(POLISH_RULES) >= 25


def test_workflow_is_12_steps():
    assert len(WORKFLOW_STEPS) == 12


def test_rules_by_category_covers_all():
    grouped = rules_by_category()
    assert len(grouped) == 7
    # All seven categories present
    for cat in (
        "sentence_architecture",
        "hedging",
        "section_tense",
        "vocabulary",
        "citation_integrity",
        "overclaim",
        "house_style",
    ):
        assert cat in grouped


def test_find_rule_by_id():
    rule = find_rule("sentence-length")
    assert rule is not None
    assert "≤ 30 words" in rule.rule


def test_find_rule_unknown_returns_none():
    assert find_rule("not-a-real-rule") is None


def test_british_pairs_are_us_to_uk():
    assert BRITISH_ENGLISH_PAIRS["color"] == "colour"
    assert BRITISH_ENGLISH_PAIRS["analyze"] == "analyse"
    assert BRITISH_ENGLISH_PAIRS["modeling"] == "modelling"
    assert BRITISH_ENGLISH_PAIRS["center"] == "centre"


def test_check_sentence_length_flags_overlong():
    text = "Short sentence. " + ("word " * 35) + "."
    flagged = check_sentence_length(text)
    assert len(flagged) == 1
    assert flagged[0][1] >= 30


def test_check_sentence_length_clean_text():
    text = "This is short. So is this. And this."
    assert check_sentence_length(text) == []


def test_check_us_spelling_finds_words():
    text = "We analyzed the behavior of cells in 3 different colors."
    findings = check_us_spelling(text)
    found_words = {f[0].lower() for f in findings}
    assert "analyzed" in found_words
    assert "behavior" in found_words
    assert "colors" in found_words


def test_check_us_spelling_preserves_case():
    text = "Behavior was Color."
    findings = check_us_spelling(text)
    suggestions = {f[0]: f[1] for f in findings}
    assert suggestions.get("Behavior") == "Behaviour"
    assert suggestions.get("Color") == "Colour"


def test_check_us_spelling_skips_already_british():
    text = "We analysed behaviour and colour."
    findings = check_us_spelling(text)
    assert findings == []


def test_write_polish_report_emits_provenance(tmp_path: Path):
    """Writing a polish report must emit provenance receipts (red line #2)."""
    text = "We analyzed the behavior of cells. " + ("word " * 35) + "."
    out = tmp_path / "polish-report.md"
    written = write_polish_report(out, text, source_path="manuscript.md")
    assert Path(written) == out
    assert out.exists()
    body = out.read_text(encoding="utf-8")
    assert "Polish report" in body or "polish" in body.lower()
    # Provenance sidecars
    prov_path = out.with_suffix(out.suffix + ".provenance.json")
    method_path = out.with_suffix(out.suffix + ".method.md")
    assert prov_path.exists()
    assert method_path.exists()
    record = json.loads(prov_path.read_text(encoding="utf-8"))
    assert record["kind"] == "manuscript_polish"
    assert record["generated_by"] == "vaultlab.manuscript.polish.write_polish_report"
