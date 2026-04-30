"""Tests for Critic output parsers.

Lifted from ``bobby-tools/tests/test_bobby_ailab/test_parsers.py``.
"""

from __future__ import annotations

from vaultlab.parsers import (
    parse_critic_ratings,
    parse_finding_ratings,
    summarize_ratings,
)


CRITIC_SAMPLE_DATA_MODE = """
## F001
- **Rating:** ROBUST
- **Significance check:** rho = 0.776, p < 0.001
- **Null comparison:** observed 105x above permutation null
- **Verdict:** Strong evidence for LPI-epithelial correlation.

## F002
- **Rating:** NEEDS_VALIDATION
- **Significance check:** FDR = 0.04 before correction
- **Null comparison:** needed: permutation test at region level
- **Verdict:** Promising but needs null comparison.

## F003 (Stromal SM enrichment)
- **Rating:** WEAK
- **Confounds:** sample size imbalance across regions
- **Verdict:** Effect size small, confounds likely.
"""


CRITIC_SAMPLE_LITERATURE_MODE = """
## Finding 1
- **Rating:** STRONG_CONSENSUS
- **Consensus check:** 5 papers agree
- **Verdict:** Well-replicated.

## Finding 2
- **Rating:** SINGLE_STUDY
- **Sample sizes:** small
- **Verdict:** One paper only.
"""


def test_parse_critic_ratings_extracts_all_ids_and_ratings() -> None:
    ratings = parse_critic_ratings(CRITIC_SAMPLE_DATA_MODE)
    assert ratings == {"F001": "ROBUST", "F002": "NEEDS_VALIDATION", "F003": "WEAK"}


def test_parse_critic_ratings_handles_literature_mode() -> None:
    ratings = parse_critic_ratings(CRITIC_SAMPLE_LITERATURE_MODE)
    # ordinal fallback for "Finding N" style
    assert ratings == {"F_1": "STRONG_CONSENSUS", "F_2": "SINGLE_STUDY"}


def test_parse_critic_ratings_empty_on_no_sections() -> None:
    assert parse_critic_ratings("just a paragraph, no headings") == {}


def test_parse_critic_ratings_skips_section_without_rating() -> None:
    text = """
## F001
- **Notes:** no rating found here
- **Verdict:** skipped.

## F002
- **Rating:** ROBUST
- **Verdict:** yes.
"""
    assert parse_critic_ratings(text) == {"F002": "ROBUST"}


def test_parse_finding_ratings_constrains_to_known_ids() -> None:
    text = """
## F001
- **Rating:** ROBUST

## F999
- **Rating:** WEAK
"""
    # F999 not in known_ids — dropped
    ratings = parse_finding_ratings(text, known_ids=["F001", "F002"])
    assert ratings == {"F001": "ROBUST"}


def test_parse_finding_ratings_uses_ordinal_fallback_for_headless_findings() -> None:
    text = """
## Finding 1
- **Rating:** ROBUST

## Finding 2
- **Rating:** NEEDS_VALIDATION
"""
    ratings = parse_finding_ratings(text, known_ids=["F001", "F002", "F003"])
    assert ratings == {"F001": "ROBUST", "F002": "NEEDS_VALIDATION"}


def test_parse_finding_ratings_mixes_explicit_and_fallback() -> None:
    text = """
## F002
- **Rating:** ROBUST

## Finding 3
- **Rating:** WEAK
"""
    ratings = parse_finding_ratings(text, known_ids=["F001", "F002", "F003"])
    assert ratings["F002"] == "ROBUST"
    # ordinal iteration is separate from explicit matching — the first
    # "Finding N" consumed F001 from the fallback iterator
    assert "F001" in ratings
    assert ratings["F001"] == "WEAK"


def test_summarize_ratings_empty() -> None:
    assert summarize_ratings({}) == "no ratings parsed"


def test_summarize_ratings_counts_by_category() -> None:
    s = summarize_ratings({
        "F001": "ROBUST", "F002": "ROBUST", "F003": "WEAK",
    })
    assert "2 ROBUST" in s
    assert "1 WEAK" in s


def test_parse_handles_bold_rating_markers() -> None:
    text = """
## F001
**Rating:** ROBUST
extra notes.
"""
    assert parse_critic_ratings(text) == {"F001": "ROBUST"}


def test_parse_ignores_unknown_rating_words() -> None:
    text = """
## F001
- **Rating:** AMAZING
- **Verdict:** not a real rating.
"""
    assert parse_critic_ratings(text) == {}


def test_parse_uses_fallback_standalone_rating_word() -> None:
    text = """
## F001
The critic concluded:

ROBUST

because the data is clear.
"""
    assert parse_critic_ratings(text) == {"F001": "ROBUST"}
