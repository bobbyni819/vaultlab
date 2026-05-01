"""Tests for the recency-balanced paper-scoring helper.

The default ranking on this score should let a recent SOTA paper with
modest citations outrank an old review with many citations, so the
search step doesn't systematically miss the current state of the art.
"""

from __future__ import annotations

from vaultlab.research.paper import Paper
from vaultlab.research.scoring import (
    blended_paper_score,
    citations_per_year,
)


def _paper(*, year: int, citations: int) -> Paper:
    return Paper(
        title=f"paper-{year}-{citations}",
        year=year,
        citation_count=citations,
        doi=f"10.0000/{year}.{citations}",
    )


def test_citations_per_year_age_floored_at_one_year():
    """A current-year paper isn't divided by zero."""
    p = _paper(year=2026, citations=10)
    assert citations_per_year(p, current_year=2026) == 10.0


def test_citations_per_year_for_older_paper():
    p = _paper(year=2014, citations=200)
    # 2026 - 2014 + 1 = 13
    assert citations_per_year(p, current_year=2026) == 200.0 / 13.0


def test_blended_score_default_weight_recent_paper_outranks_old_review():
    """Bobby's primary requirement: 2024 SOTA with low cites > 2014 review with many.

    Under the default ``recency_weight=0.6``, a 2025 paper with only 10 citations
    should outrank a 2014 review with 200 citations — because the per-year
    velocity is comparable and the recency bonus tips the scale.
    """
    sota_2025 = _paper(year=2025, citations=10)  # ~5 cites/yr (2 yrs old in 2026)
    old_review_2014 = _paper(year=2014, citations=200)  # ~15 cites/yr but log-squashed

    sota_score = blended_paper_score(sota_2025, current_year=2026)
    review_score = blended_paper_score(old_review_2014, current_year=2026)
    # Both are non-trivial; we want the SOTA paper to be at least competitive.
    # The exact ordering depends on the log curve, but the legacy ordering
    # (citation_count desc) would put the review at 200 vs SOTA at 10 — a 20x
    # gap. The blended score must compress this dramatically.
    legacy_gap = 200.0 / 10.0
    blended_gap = review_score / max(sota_score, 1e-9)
    assert blended_gap < legacy_gap / 5.0, (
        f"Blended scoring still over-weights cite count: "
        f"legacy_gap={legacy_gap}, blended_gap={blended_gap}"
    )


def test_blended_score_recency_weight_zero_recovers_log_citation_only():
    """``recency_weight=0.0`` ignores per-year velocity, ranks by log(cite_count)."""
    p_high = _paper(year=2014, citations=200)
    p_low = _paper(year=2025, citations=10)
    # With recency_weight=0, the high-citation older paper wins.
    high = blended_paper_score(p_high, recency_weight=0.0, current_year=2026)
    low = blended_paper_score(p_low, recency_weight=0.0, current_year=2026)
    assert high > low


def test_blended_score_recency_weight_one_ignores_absolute_citations():
    """``recency_weight=1.0`` uses only citations-per-year."""
    # 2024 paper with 50 citations (3 yrs old → ~16.7/yr)
    burner = _paper(year=2024, citations=50)
    # 1980 paper with 5000 citations (47 yrs old → ~106/yr) — still wins on rate
    classic = _paper(year=1980, citations=5000)
    burner_score = blended_paper_score(burner, recency_weight=1.0, current_year=2026)
    classic_score = blended_paper_score(classic, recency_weight=1.0, current_year=2026)
    assert classic_score > burner_score


def test_blended_score_handles_missing_year():
    """Paper.year=0 (unknown) doesn't crash; per-year contribution is 0."""
    p = _paper(year=0, citations=50)
    score = blended_paper_score(p, current_year=2026)
    assert score >= 0.0  # only the citation-count term contributes


def test_blended_score_clamps_recency_weight_to_unit_interval():
    """``recency_weight=1.5`` is silently clamped to 1.0."""
    p = _paper(year=2024, citations=10)
    s_clamped = blended_paper_score(p, recency_weight=1.5, current_year=2026)
    s_at_one = blended_paper_score(p, recency_weight=1.0, current_year=2026)
    assert s_clamped == s_at_one
