"""Recency-balanced paper scoring.

The naive ranking ``citation_count desc`` systematically favours older
established papers. A 2014 review with 200 citations always outranks a
2024 SOTA paper with 5 citations, even when the 2024 paper has the
higher citation *velocity* (citations per year) and is more relevant to
the current state of the field.

This module supplies a blended score that gives recent high-velocity
work a fighting chance:

    score = recency_weight * citations_per_year_z
           + (1 - recency_weight) * citation_count_z

where the per-year and absolute citation counts are first squashed
through ``log1p`` so a paper with 1000 citations doesn't completely
dominate a paper with 50 citations / year purely on the absolute count.

The default ``recency_weight=0.6`` means citations-per-year contributes
60 % of the score. Set ``recency_weight=0.0`` to recover the legacy
"cite count desc" ordering.
"""

from __future__ import annotations

import math
from datetime import datetime

from vaultlab.research.paper import Paper

# Default weight on citations-per-year vs absolute citation count.
DEFAULT_RECENCY_WEIGHT: float = 0.6


def _resolve_current_year(current_year: int | None) -> int:
    if current_year is not None:
        return current_year
    return datetime.now().year


def citations_per_year(
    paper: Paper, *, current_year: int | None = None
) -> float:
    """Citations divided by the number of completed years since publication.

    A paper published in the current year gets ``citation_count / 1`` (we
    floor the divisor at 1 to avoid div-by-zero and to avoid pathologically
    inflating brand-new papers). A paper from 5 years ago with 100 citations
    has citations_per_year = 20.0.
    """
    year = int(paper.year or 0)
    if year <= 0:
        return 0.0
    cy = _resolve_current_year(current_year)
    age_years = max(1, cy - year + 1)
    return float(paper.citation_count) / float(age_years)


def blended_paper_score(
    paper: Paper,
    *,
    recency_weight: float = DEFAULT_RECENCY_WEIGHT,
    current_year: int | None = None,
) -> float:
    """Recency-balanced ranking score for a single paper.

    ``recency_weight`` blends:

    * ``recency_weight=0.0`` → pure ``log1p(citation_count)`` (legacy
      "always pick the most-cited paper" behaviour).
    * ``recency_weight=1.0`` → pure ``log1p(citations_per_year)`` (favours
      recent work with high traction; ignores absolute prestige).
    * ``recency_weight=0.6`` (default) → blend; recent SOTA papers with
      reasonable per-year traction can outrank older reviews.

    Both terms pass through ``log1p`` so heavy-hitters don't crush the
    long tail. A paper with 1000 citations gets ``log(1001)≈6.9``;
    a paper with 50 citations gets ``log(51)≈3.9``. The ratio is ~1.8,
    not 20.

    Args:
        paper: A :class:`Paper` instance.
        recency_weight: Float in ``[0, 1]``. Defaults to ``0.6``.
        current_year: Optional override for the current year (useful in
            tests). Defaults to the system clock.

    Returns:
        A float score; bigger is better. Multiple papers can be sorted by
        this score directly with ``key=blended_paper_score, reverse=True``.
    """
    rw = max(0.0, min(1.0, float(recency_weight)))
    cit_count = max(0, int(paper.citation_count))
    cit_per_yr = citations_per_year(paper, current_year=current_year)
    abs_term = math.log1p(cit_count)
    rate_term = math.log1p(max(0.0, cit_per_yr))
    return rw * rate_term + (1.0 - rw) * abs_term


__all__ = [
    "DEFAULT_RECENCY_WEIGHT",
    "citations_per_year",
    "blended_paper_score",
]
