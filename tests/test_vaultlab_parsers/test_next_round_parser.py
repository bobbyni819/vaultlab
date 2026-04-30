"""Tests for parse_next_round_tests — extracts Critic's Round 2 queue.

Lifted from ``bobby-tools/tests/test_bobby_ailab/test_next_round_parser.py``.
"""

from __future__ import annotations

from vaultlab.parsers import (
    PRIORITY_LEVELS,
    parse_next_round_tests,
    summarize_tests,
)


METABOLISM_CRITIC_SAMPLE = """
## Overall Round Verdict

Some prose about ratings.

**Priority next-round checks (ranked):**

1. [CRITICAL] Recompute aggregate at K=50 (or within-tissue at K=100) and re-check whether the Simpson's paradox sign-flip survives matched scale. If it collapses, F2 is a K-artifact and the whole reframe is rescinded.
2. [HIGH] Permutation null for the aggregate SM-Stromal rho and the within-tissue sign flips — specifically cell-type label shuffle within-pixel, 10,000 iterations.
3. [HIGH] Nerve abundance check in mucosa — how many pixels have detectable Nerve signature? If n<50, kill the rescue.
4. [MEDIUM] CD49ahi vs vascular co-localization — check spatial overlap with endothelial markers.
5. [MEDIUM] FDR audit — report the exact BH denominator used in S8.

**Bottom line:** Round 1 cannot yet conclude anything definitive.
"""


def test_parses_five_priority_items() -> None:
    records = parse_next_round_tests(METABOLISM_CRITIC_SAMPLE)
    assert len(records) == 5


def test_priority_tags_extracted_correctly() -> None:
    records = parse_next_round_tests(METABOLISM_CRITIC_SAMPLE)
    priorities = [r["priority"] for r in records]
    assert priorities == ["CRITICAL", "HIGH", "HIGH", "MEDIUM", "MEDIUM"]


def test_descriptions_are_captured() -> None:
    records = parse_next_round_tests(METABOLISM_CRITIC_SAMPLE)
    assert "K=50" in records[0]["description"]
    assert "Permutation null" in records[1]["description"]
    assert "CD49ahi" in records[3]["description"]


def test_positions_are_line_numbers() -> None:
    records = parse_next_round_tests(METABOLISM_CRITIC_SAMPLE)
    assert records[0]["position"] > 0
    for prev, curr in zip(records, records[1:]):
        assert curr["position"] > prev["position"]


def test_empty_text_returns_empty_list() -> None:
    assert parse_next_round_tests("") == []


def test_no_priority_items_returns_empty() -> None:
    text = "Just regular text with no priority tags.\n\nStill nothing here."
    assert parse_next_round_tests(text) == []


def test_bullet_style_items_also_work() -> None:
    text = """
- [CRITICAL] A critical test
- [HIGH] A high-priority test
* [MEDIUM] A medium test with asterisk bullet
"""
    records = parse_next_round_tests(text)
    assert len(records) == 3
    assert [r["priority"] for r in records] == ["CRITICAL", "HIGH", "MEDIUM"]


def test_bold_markup_around_priority_tag() -> None:
    text = "1. **[HIGH]** A test with bold brackets"
    records = parse_next_round_tests(text)
    assert len(records) == 1
    assert records[0]["priority"] == "HIGH"


def test_continuation_lines_go_into_detail() -> None:
    text = """1. [HIGH] First line of test
   A continuation line
   Another continuation

2. [MEDIUM] Second test
"""
    records = parse_next_round_tests(text)
    assert len(records) == 2
    assert "A continuation line" in records[0]["detail"]
    assert "Another continuation" in records[0]["detail"]
    assert records[1]["detail"] == ""


def test_low_priority_supported() -> None:
    text = "1. [LOW] An optional test"
    records = parse_next_round_tests(text)
    assert records[0]["priority"] == "LOW"


def test_case_insensitive_priority_tag() -> None:
    text = "1. [critical] lowercase input"
    records = parse_next_round_tests(text)
    assert records[0]["priority"] == "CRITICAL"


def test_summarize_tests_counts_by_priority() -> None:
    records = parse_next_round_tests(METABOLISM_CRITIC_SAMPLE)
    summary = summarize_tests(records)
    assert "1 CRITICAL" in summary
    assert "2 HIGH" in summary
    assert "2 MEDIUM" in summary


def test_summarize_tests_orders_by_priority_level() -> None:
    records = parse_next_round_tests(METABOLISM_CRITIC_SAMPLE)
    summary = summarize_tests(records)
    crit_pos = summary.find("CRITICAL")
    high_pos = summary.find("HIGH")
    med_pos = summary.find("MEDIUM")
    assert crit_pos < high_pos < med_pos


def test_summarize_tests_empty() -> None:
    assert summarize_tests([]) == "no tests parsed"


def test_priority_levels_constant() -> None:
    assert PRIORITY_LEVELS == ("CRITICAL", "HIGH", "MEDIUM", "LOW")
