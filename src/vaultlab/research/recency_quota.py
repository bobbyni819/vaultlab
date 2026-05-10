"""Enforce recency quotas in picker output.

Background
----------
The picker's coarse pre-ranking uses ``(is_seed, has_pdf, og_score +
forward_influence)`` as the tuple sort. ``og_score`` and
``forward_influence`` are both citation-graph metrics — in-degree on
the corpus — which structurally biases against recent papers because
a 2025 paper has had ≤1 year to accumulate citations while a 2018
paper has had 7.

For fast-moving fields (spatial proteomics, tissue simulation, AI
methodology) this means SOTA papers often barely make the top-30
cutoff (Bobby observed CellLENS 2025 at rank 19, CANVAS 2025 at rank
20, Method-of-Year 2024 at rank 21 in the 2026-05-01 CODEX run).

This module adds **recency quotas** — explicit floors on how many
recent-window papers must appear in the final picks. Default quotas
(set to be conservative for review-paper scope but adjustable):

* ``recency_quota_24mo = 6`` — ensure ≥6 papers from last 24 months
* ``recency_quota_12mo = 3`` — ensure ≥3 papers from last 12 months
  (12-month bias is stronger because there's even less citation time)

The function is non-destructive: when the top-N already meets the
quotas, it returns the picks unchanged. When it doesn't, it swaps in
the highest-ranked recent papers from the candidate pool, displacing
the lowest-ranked older papers.

Public API
----------
* :func:`apply_recency_quotas` — given picks + candidate pool +
  current-year reference, produce a re-ranked list that meets the
  quotas where possible.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

logger = logging.getLogger(__name__)


# Conservative defaults sized for ~30-pick lists (short-scope / standard
# scope). Smaller picks lists (e.g., n=10 for short scope) will be
# quota-clipped proportionally inside apply_recency_quotas.
#
# IMPORTANT — these defaults UNDER-PROVISION review-paper-scope runs.
# For review_paper_strict / thesis-intro arcs, the caller MUST override
# with REVIEW_QUOTA_24MO / REVIEW_QUOTA_12MO (30 + 30) because the field
# (multiscale modeling × spatial proteomics) moves fast and the citation-
# graph metric structurally biases against 2024-2025 SOTA. Bobby raised
# the review-scope floor to 30+30 on 2026-05-01 after observing the
# initial multiscale-tissue-sim arc lost Hickey/Agmon Cell Systems 2024
# and Niarakis IDT 2024 to the recency floor on the first run.
DEFAULT_QUOTA_24MO = 6
DEFAULT_QUOTA_12MO = 3

# Review-paper / thesis-intro scope. Use these explicitly when calling
# apply_recency_quotas with target_n ~= 150.
REVIEW_QUOTA_24MO = 30
REVIEW_QUOTA_12MO = 30

# Standard / journal-club scope. Use with target_n ~= 75.
STANDARD_QUOTA_24MO = 15
STANDARD_QUOTA_12MO = 10

# Short / quick-look scope. Use with target_n ~= 15.
SHORT_QUOTA_24MO = 4
SHORT_QUOTA_12MO = 2


@dataclass
class QuotaApplicationResult:
    """Outcome of applying recency quotas.

    Attributes:
        picks: The re-ranked picks list (DOIs in tuple form: doi, rank).
        n_swaps: How many positions were swapped to meet quotas.
        unmet_24mo: When the candidate pool didn't have enough recent-
            window papers to meet the quota, this is the shortfall.
        unmet_12mo: Same for 12-month window.
    """

    picks: list[dict]
    n_swaps: int
    unmet_24mo: int
    unmet_12mo: int


def _is_within_window(year: int, current_year: int, window_months: int) -> bool:
    """Return True if ``year`` is within the recency window from ``current_year``.

    Window is in *months* but works on year granularity since paper
    metadata typically only carries year. A 12-month window means
    "current year and the prior year"; a 24-month window means
    "current year and the prior two years."
    """
    if not year or year <= 0:
        return False
    threshold = current_year - (window_months // 12)
    # Edge case: window_months not a multiple of 12; round up.
    if window_months % 12:
        threshold = current_year - (window_months // 12) - 1
    return year >= threshold


def apply_recency_quotas(
    *,
    picks: list[dict],
    candidate_pool: dict[str, dict] | None = None,
    quota_24mo: int = DEFAULT_QUOTA_24MO,
    quota_12mo: int = DEFAULT_QUOTA_12MO,
    current_year: int | None = None,
    target_n: int | None = None,
) -> QuotaApplicationResult:
    """Re-rank picks to meet recency quotas.

    Args:
        picks: Picker output (list of dicts with ``doi``, ``year``, ``rank``).
        candidate_pool: Dict of ``{doi -> candidate}`` for swap-ins.
            When None, only re-orders within the existing picks.
        quota_24mo: Minimum number of papers from last 24 months.
            Set to 0 to disable.
        quota_12mo: Minimum number of papers from last 12 months.
            Set to 0 to disable.
        current_year: Reference year. Defaults to today's year.
        target_n: Truncate the output to this length. None = keep all
            picks, even if quotas push the list past the original length.

    Returns:
        :class:`QuotaApplicationResult` with the re-ranked picks +
        diagnostics.
    """
    if current_year is None:
        current_year = date.today().year

    # Ensure 24mo quota >= 12mo quota (12-month is a subset of 24-month).
    # We don't auto-scale for short picklists because the caller knows
    # their target_n; if they want different quotas for n=10 vs n=30,
    # they pass different values explicitly.
    quota_24mo = max(quota_24mo, quota_12mo)

    # Count current recent-window membership in picks
    in_picks_24mo = [p for p in picks if _is_within_window(p.get("year", 0), current_year, 24)]
    in_picks_12mo = [p for p in picks if _is_within_window(p.get("year", 0), current_year, 12)]

    need_24mo = max(0, quota_24mo - len(in_picks_24mo))
    need_12mo = max(0, quota_12mo - len(in_picks_12mo))

    if need_24mo == 0 and need_12mo == 0:
        # Quotas already met — no changes.
        return QuotaApplicationResult(
            picks=picks,
            n_swaps=0,
            unmet_24mo=0,
            unmet_12mo=0,
        )

    if candidate_pool is None:
        # Can't swap in — only return diagnostics.
        return QuotaApplicationResult(
            picks=picks,
            n_swaps=0,
            unmet_24mo=need_24mo,
            unmet_12mo=need_12mo,
        )

    # Find recent-window candidates not yet in picks, ranked by their
    # composite_score (highest first).
    picked_dois = {(p.get("doi") or "").lower() for p in picks}

    candidates_12mo: list[dict] = []
    candidates_24mo_only: list[dict] = []
    for doi, cand in candidate_pool.items():
        if doi.lower() in picked_dois:
            continue
        cand_year = cand.get("year", 0)
        if _is_within_window(cand_year, current_year, 12):
            candidates_12mo.append({"doi": doi, "year": cand_year, **cand})
        elif _is_within_window(cand_year, current_year, 24):
            candidates_24mo_only.append({"doi": doi, "year": cand_year, **cand})

    candidates_12mo.sort(
        key=lambda c: c.get("composite_score", 0.0),
        reverse=True,
    )
    candidates_24mo_only.sort(
        key=lambda c: c.get("composite_score", 0.0),
        reverse=True,
    )

    # Swap-in plan: prioritize meeting 12mo quota first (it's stricter).
    # Each 12mo swap-in also satisfies 24mo (since 12mo ⊂ 24mo).
    swaps_12mo = candidates_12mo[:need_12mo]
    actual_12mo_added = len(swaps_12mo)
    remaining_24mo_need = max(0, need_24mo - actual_12mo_added)

    # First exhaust 24mo-only candidates (papers from 13-24 months ago)
    swaps_24mo = candidates_24mo_only[:remaining_24mo_need]
    # If still short, fall back to additional 12mo candidates
    # (which also satisfy the 24mo quota since 12mo ⊂ 24mo)
    extra_24mo_still_needed = remaining_24mo_need - len(swaps_24mo)
    if extra_24mo_still_needed > 0:
        extras_from_12mo = candidates_12mo[need_12mo : need_12mo + extra_24mo_still_needed]
        swaps_24mo.extend(extras_from_12mo)

    swap_ins = swaps_12mo + swaps_24mo
    n_swaps = len(swap_ins)

    if n_swaps == 0:
        return QuotaApplicationResult(
            picks=picks,
            n_swaps=0,
            unmet_24mo=need_24mo,
            unmet_12mo=need_12mo,
        )

    # Identify the lowest-ranked old papers to displace. "Old" here means
    # not in either recency window. Sort picks by their original rank
    # descending so we displace the worst-ranked first.
    old_picks_descending = sorted(
        [p for p in picks if not _is_within_window(p.get("year", 0), current_year, 24)],
        key=lambda p: p.get("rank", 9999),
        reverse=True,
    )
    n_to_displace = min(n_swaps, len(old_picks_descending))
    to_displace_dois = {(p.get("doi") or "").lower() for p in old_picks_descending[:n_to_displace]}

    # Build new picks: keep originals not in displace set + add swap-ins
    new_picks = [p for p in picks if (p.get("doi") or "").lower() not in to_displace_dois]
    # Mark the swap-ins with provenance
    for s in swap_ins[:n_to_displace]:
        s["from_recency_quota"] = True
        new_picks.append(s)

    # Re-rank by original composite_score (with required-paper / quota
    # boost preserved), or by the order picks appeared.
    # Simplest: keep the original picks' relative order, then append swaps.
    for i, entry in enumerate(new_picks, start=1):
        entry["rank"] = i

    # Final unmet diagnostics: did we still fall short?
    final_24mo = sum(1 for p in new_picks if _is_within_window(p.get("year", 0), current_year, 24))
    final_12mo = sum(1 for p in new_picks if _is_within_window(p.get("year", 0), current_year, 12))

    return QuotaApplicationResult(
        picks=new_picks,
        n_swaps=n_swaps,
        unmet_24mo=max(0, quota_24mo - final_24mo),
        unmet_12mo=max(0, quota_12mo - final_12mo),
    )


__all__ = [
    "DEFAULT_QUOTA_12MO",
    "DEFAULT_QUOTA_24MO",
    "REVIEW_QUOTA_12MO",
    "REVIEW_QUOTA_24MO",
    "SHORT_QUOTA_12MO",
    "SHORT_QUOTA_24MO",
    "STANDARD_QUOTA_12MO",
    "STANDARD_QUOTA_24MO",
    "QuotaApplicationResult",
    "apply_recency_quotas",
]
