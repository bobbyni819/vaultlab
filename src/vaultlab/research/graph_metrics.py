"""Citation-graph metrics over a :class:`vaultlab.research.corpus.Corpus`.

These are the descriptive statistics requested by Bobby for the
literature-search v2 design (grill-research-pipeline-2026-04-29 §F.7):

* **og_score** — for each paper observed (whether seed or merely cited
  by a seed), what fraction of corpus papers cite it. The "OG-paper
  score": which historical works keep showing up in the seed set's
  reference lists.
* **forward_influence** — for papers that ARE in the corpus's seed set,
  how many other corpus papers cite them. This is in-degree on the
  N x N subgraph induced by the corpus's seed papers.
* **co_citation_pairs** — pairs ``(doi_a, doi_b, count)`` where at
  least two corpus papers cite both ``doi_a`` and ``doi_b``. Sorted
  by count descending. Useful for detecting tightly-coupled cited-pair
  clusters.
* **year_buckets** — coarse "history / development / sota" bucket per
  paper, computed from publication-year quartiles within the corpus.

The implementation is pure-Python; for the 10-500 paper corpora this
module is designed for, that's well within budget. (DuckDB would be
nice for >5k-paper corpora but is overkill here.)
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vaultlab.research.corpus import Corpus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public dataclass
# ---------------------------------------------------------------------------


@dataclass
class CorpusMetrics:
    """Descriptive citation-graph statistics for a :class:`Corpus`.

    Attributes:
        og_score: ``doi -> fraction of corpus seed papers that cite it``,
            in [0, 1]. Includes papers that are NOT in the seed set
            (e.g. a foundational paper cited by 8 of 10 seeds gets 0.8).
        forward_influence: For papers in the seed set, the number of
            OTHER seed papers that cite it. This is the in-degree on the
            seed-x-seed subgraph.
        co_citation_pairs: ``(doi_a, doi_b, count)`` tuples where
            ``count >= 2`` corpus papers cite both. ``doi_a < doi_b`` by
            string order so each pair appears once. Sorted by count
            descending.
        year_buckets: ``doi -> {"history", "development", "sota"}`` based
            on publication-year quartiles within the corpus. Papers with
            no year fall into ``"unknown"``.
    """

    og_score: dict[str, float] = field(default_factory=dict)
    forward_influence: dict[str, int] = field(default_factory=dict)
    co_citation_pairs: list[tuple[str, str, int]] = field(default_factory=list)
    year_buckets: dict[str, str] = field(default_factory=dict)

    def top_og(self, n: int = 10) -> list[tuple[str, float]]:
        """Return the top-``n`` ``(doi, score)`` pairs by OG score."""
        return sorted(self.og_score.items(), key=lambda x: x[1], reverse=True)[:n]


# ---------------------------------------------------------------------------
# Year-bucket helper
# ---------------------------------------------------------------------------


def _year_bucket_assignments(
    years_by_doi: dict[str, int],
) -> dict[str, str]:
    """Assign each paper to ``"history" | "development" | "sota" | "unknown"``.

    Buckets are computed from the within-corpus year distribution:
    - history: bottom quartile (oldest papers)
    - development: middle two quartiles
    - sota: top quartile (newest)
    - unknown: papers with year == 0

    With <4 datable papers we degrade gracefully: 1 paper -> all "sota";
    2 papers -> oldest "history", newest "sota"; 3 papers -> oldest
    "history", middle "development", newest "sota".
    """
    valid = [(d, y) for d, y in years_by_doi.items() if y]
    if not valid:
        return {d: "unknown" for d in years_by_doi}

    valid.sort(key=lambda kv: kv[1])
    n = len(valid)
    buckets: dict[str, str] = {}

    if n == 1:
        buckets[valid[0][0]] = "sota"
    elif n == 2:
        buckets[valid[0][0]] = "history"
        buckets[valid[1][0]] = "sota"
    elif n == 3:
        buckets[valid[0][0]] = "history"
        buckets[valid[1][0]] = "development"
        buckets[valid[2][0]] = "sota"
    else:
        # Use rank-based quartiles so we always hit all three buckets,
        # even when many papers share a single year.
        q1 = max(1, n // 4)
        q3 = max(q1 + 1, (3 * n) // 4)
        for i, (doi, _y) in enumerate(valid):
            if i < q1:
                buckets[doi] = "history"
            elif i < q3:
                buckets[doi] = "development"
            else:
                buckets[doi] = "sota"

    for doi, y in years_by_doi.items():
        if not y:
            buckets[doi] = "unknown"
    return buckets


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_metrics(corpus: "Corpus") -> CorpusMetrics:
    """Compute :class:`CorpusMetrics` for ``corpus`` and attach to it.

    Mutates ``corpus.metrics`` and also returns the metrics object.

    Args:
        corpus: Corpus with seeds and references already populated. Edges
            with empty target lists (PDF-fallback markers) are ignored.

    Returns:
        The :class:`CorpusMetrics` computed for the corpus.
    """
    # ------------------------------------------------------------------
    # 1. OG score: for each cited DOI, fraction of seed papers citing it.
    # ------------------------------------------------------------------
    seed_dois = corpus.seed_dois
    n_seeds_with_refs = sum(1 for d in seed_dois if corpus.references.get(d))
    cite_count: Counter[str] = Counter()
    for seed_doi in seed_dois:
        cited = corpus.references.get(seed_doi) or []
        # Dedupe within a paper so a single paper citing the same DOI
        # twice doesn't inflate.
        for d in set(cited):
            cite_count[d] += 1

    og_score: dict[str, float] = {}
    if n_seeds_with_refs > 0:
        for doi, count in cite_count.items():
            og_score[doi] = count / n_seeds_with_refs

    # ------------------------------------------------------------------
    # 2. Forward influence: in-degree on the seed x seed subgraph.
    # ------------------------------------------------------------------
    seed_set = set(seed_dois)
    forward_influence: dict[str, int] = {d: 0 for d in seed_dois}
    for seed_doi in seed_dois:
        cited = corpus.references.get(seed_doi) or []
        for target in set(cited):
            if target in seed_set and target != seed_doi:
                forward_influence[target] = forward_influence.get(target, 0) + 1

    # ------------------------------------------------------------------
    # 3. Co-citation pairs: pairs cited together by >=2 corpus papers.
    # ------------------------------------------------------------------
    pair_counts: Counter[tuple[str, str]] = Counter()
    for citing_doi, cited_list in corpus.references.items():
        if not cited_list:
            continue
        # Only consider citing papers that are in the corpus (almost
        # always true — the corpus is built from refs of seeds).
        if citing_doi not in corpus.papers:
            continue
        unique = sorted(set(cited_list))
        for i in range(len(unique)):
            for j in range(i + 1, len(unique)):
                pair_counts[(unique[i], unique[j])] += 1

    co_citation_pairs = [
        (a, b, c) for (a, b), c in pair_counts.items() if c >= 2
    ]
    co_citation_pairs.sort(key=lambda x: (-x[2], x[0], x[1]))

    # ------------------------------------------------------------------
    # 4. Year buckets — only consider papers actually known to the corpus
    #    (i.e. in corpus.papers). Papers referenced but unknown to us are
    #    skipped here.
    # ------------------------------------------------------------------
    years_by_doi = {doi: paper.year for doi, paper in corpus.papers.items()}
    year_buckets = _year_bucket_assignments(years_by_doi)

    metrics = CorpusMetrics(
        og_score=og_score,
        forward_influence=forward_influence,
        co_citation_pairs=co_citation_pairs,
        year_buckets=year_buckets,
    )
    corpus.metrics = metrics
    return metrics


__all__ = [
    "CorpusMetrics",
    "compute_metrics",
]
