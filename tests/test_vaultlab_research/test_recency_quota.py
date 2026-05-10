"""Tests for vaultlab.research.recency_quota."""

from __future__ import annotations

from vaultlab.research.recency_quota import (
    DEFAULT_QUOTA_12MO,
    DEFAULT_QUOTA_24MO,
    apply_recency_quotas,
)


def test_no_swap_when_quotas_already_met():
    picks = [
        {"doi": "10.1/a", "year": 2025, "rank": 1, "composite_score": 14.0},
        {"doi": "10.1/b", "year": 2024, "rank": 2, "composite_score": 13.0},
        {"doi": "10.1/c", "year": 2025, "rank": 3, "composite_score": 12.0},
        {"doi": "10.1/d", "year": 2025, "rank": 4, "composite_score": 11.0},
        {"doi": "10.1/e", "year": 2018, "rank": 5, "composite_score": 10.0},
    ]
    result = apply_recency_quotas(
        picks=picks,
        quota_24mo=2,  # Already have 4 papers from 2024-2025
        quota_12mo=2,  # Already have 3 papers from 2025
        current_year=2026,
    )
    assert result.n_swaps == 0
    assert result.picks == picks  # Unchanged


def test_swap_in_when_picks_lack_recent_papers():
    picks = [
        {"doi": "10.1/old1", "year": 2018, "rank": 1, "composite_score": 14.0},
        {"doi": "10.1/old2", "year": 2017, "rank": 2, "composite_score": 13.0},
        {"doi": "10.1/old3", "year": 2019, "rank": 3, "composite_score": 12.0},
    ]
    candidate_pool = {
        "10.1/recent1": {"year": 2025, "composite_score": 9.0},
        "10.1/recent2": {"year": 2025, "composite_score": 8.5},
    }

    result = apply_recency_quotas(
        picks=picks,
        candidate_pool=candidate_pool,
        quota_24mo=2,
        quota_12mo=2,
        current_year=2026,
        target_n=3,
    )

    dois = [p["doi"] for p in result.picks]
    assert "10.1/recent1" in dois
    assert "10.1/recent2" in dois
    assert result.n_swaps >= 2


def test_displaces_lowest_ranked_old_papers_first():
    picks = [
        {"doi": "10.1/best-old", "year": 2018, "rank": 1, "composite_score": 14.0},
        {"doi": "10.1/mid-old", "year": 2017, "rank": 2, "composite_score": 12.0},
        {"doi": "10.1/worst-old", "year": 2016, "rank": 3, "composite_score": 8.0},
    ]
    candidate_pool = {
        "10.1/recent": {"year": 2025, "composite_score": 5.0},
    }

    result = apply_recency_quotas(
        picks=picks,
        candidate_pool=candidate_pool,
        quota_24mo=1,
        quota_12mo=1,
        current_year=2026,
        target_n=3,
    )

    dois = [p["doi"] for p in result.picks]
    assert "10.1/recent" in dois
    assert "10.1/best-old" in dois  # Best-old kept
    assert "10.1/worst-old" not in dois  # Worst-old displaced


def test_unmet_quota_when_pool_insufficient():
    """When the candidate pool doesn't have enough recent papers,
    flag the unmet portion in the result."""
    picks = [
        {"doi": "10.1/old1", "year": 2018, "rank": 1, "composite_score": 14.0},
    ]
    candidate_pool = {}  # No recent candidates available

    result = apply_recency_quotas(
        picks=picks,
        candidate_pool=candidate_pool,
        quota_24mo=2,
        quota_12mo=1,
        current_year=2026,
    )

    assert result.unmet_24mo == 2  # Couldn't fill 2 24mo slots
    assert result.unmet_12mo == 1  # Couldn't fill 1 12mo slot
    assert result.n_swaps == 0


def test_12mo_quota_takes_priority_over_24mo_only():
    """A 12mo paper is preferred over a 13-24mo paper when both quotas need filling."""
    picks = [
        {"doi": "10.1/old", "year": 2010, "rank": 1, "composite_score": 14.0},
    ]
    candidate_pool = {
        "10.1/24mo-only": {"year": 2024, "composite_score": 5.0},
        "10.1/12mo": {"year": 2025, "composite_score": 4.0},  # Lower score but more recent
    }

    result = apply_recency_quotas(
        picks=picks,
        candidate_pool=candidate_pool,
        quota_24mo=1,
        quota_12mo=1,
        current_year=2026,
        target_n=2,
    )

    dois = [p["doi"] for p in result.picks]
    # 12mo paper should be added first (it satisfies BOTH quotas)
    assert "10.1/12mo" in dois


def test_short_picklist_caller_chooses_quotas():
    """For a 10-pick list, the caller passes scaled quotas (e.g., 2 + 1)
    explicitly. The function honors them as given without auto-scaling."""
    picks = [
        {"doi": f"10.1/old{i}", "year": 2010, "rank": i + 1, "composite_score": 10 - i}
        for i in range(10)
    ]
    candidate_pool = {
        f"10.1/recent{i}": {"year": 2025, "composite_score": 8 - i * 0.1} for i in range(5)
    }

    result = apply_recency_quotas(
        picks=picks,
        candidate_pool=candidate_pool,
        quota_24mo=2,  # caller-scaled for short list
        quota_12mo=1,
        current_year=2026,
        target_n=10,
    )

    # Both quotas met by adding 2 recent papers
    recent_count = sum(1 for p in result.picks if p.get("year", 0) >= 2024)
    assert recent_count >= 2


def test_skips_zero_or_negative_years():
    """Papers with year=0 (unknown) should NOT count toward quota."""
    picks = [
        {"doi": "10.1/no-year", "year": 0, "rank": 1, "composite_score": 14.0},
    ]

    result = apply_recency_quotas(
        picks=picks,
        candidate_pool={},
        quota_24mo=1,
        quota_12mo=0,
        current_year=2026,
    )

    assert result.unmet_24mo == 1  # year=0 doesn't satisfy quota


def test_returns_diagnostics_when_no_pool_provided():
    """Without a candidate pool, return picks unchanged but flag unmet."""
    picks = [
        {"doi": "10.1/old", "year": 2018, "rank": 1, "composite_score": 14.0},
    ]

    result = apply_recency_quotas(
        picks=picks,
        candidate_pool=None,
        quota_24mo=1,
        quota_12mo=1,
        current_year=2026,
    )

    assert result.n_swaps == 0
    assert result.unmet_24mo == 1
    assert result.unmet_12mo == 1
    assert result.picks == picks


def test_disabling_quotas_with_zero_does_nothing():
    picks = [
        {"doi": "10.1/old", "year": 2010, "rank": 1, "composite_score": 14.0},
    ]
    candidate_pool = {
        "10.1/recent": {"year": 2025, "composite_score": 5.0},
    }

    result = apply_recency_quotas(
        picks=picks,
        candidate_pool=candidate_pool,
        quota_24mo=0,
        quota_12mo=0,
        current_year=2026,
    )

    assert result.n_swaps == 0
    assert result.picks == picks


def test_default_quotas_are_reasonable():
    """24mo default should be larger than 12mo default."""
    assert DEFAULT_QUOTA_24MO > DEFAULT_QUOTA_12MO
    # 6 + 3 = 30% of a 30-pick list — reasonable for fast-moving fields
    assert DEFAULT_QUOTA_24MO == 6
    assert DEFAULT_QUOTA_12MO == 3


def test_review_quotas_match_bobbys_2026_05_01_floor():
    """Bobby raised the review-paper recency floor to 30+30 on
    2026-05-01 after observing Hickey/Agmon Cell Systems 2024 + Niarakis
    IDT 2024 + other 2024-2025 SOTA were under-represented at the
    default 6+3 level. Review-paper scope picks ~150 papers; 30+30
    recency is 20% by count but covers the SOTA window."""
    from vaultlab.research.recency_quota import (
        REVIEW_QUOTA_12MO,
        REVIEW_QUOTA_24MO,
        SHORT_QUOTA_12MO,
        SHORT_QUOTA_24MO,
        STANDARD_QUOTA_12MO,
        STANDARD_QUOTA_24MO,
    )

    assert REVIEW_QUOTA_24MO == 30
    assert REVIEW_QUOTA_12MO == 30
    # Standard scope ~75-pick lists
    assert STANDARD_QUOTA_24MO == 15
    assert STANDARD_QUOTA_12MO == 10
    # Short scope ~15-pick lists
    assert SHORT_QUOTA_24MO == 4
    assert SHORT_QUOTA_12MO == 2
    # Ordering invariants: review > standard > short
    assert REVIEW_QUOTA_24MO > STANDARD_QUOTA_24MO > SHORT_QUOTA_24MO
    assert REVIEW_QUOTA_12MO > STANDARD_QUOTA_12MO > SHORT_QUOTA_12MO


def test_ranks_are_rewritten_after_swap():
    picks = [
        {"doi": "10.1/old", "year": 2010, "rank": 1, "composite_score": 14.0},
    ]
    candidate_pool = {
        "10.1/recent": {"year": 2025, "composite_score": 5.0},
    }

    result = apply_recency_quotas(
        picks=picks,
        candidate_pool=candidate_pool,
        quota_24mo=0,  # only 12mo quota active
        quota_12mo=1,
        current_year=2026,
        target_n=1,
    )

    # Ranks should be sequentially rewritten
    ranks = [p["rank"] for p in result.picks]
    assert ranks == list(range(1, len(result.picks) + 1))
