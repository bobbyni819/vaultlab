"""Trial run for the citation-graph corpus layer.

Search 'CRISPR base editing', build a Corpus, compute metrics, print
verification stats. Run from vaultlab repo root:

    python scripts/_trial_corpus.py
"""

from __future__ import annotations

import logging
import os
import sys

# Force UTF-8 stdout so unicode in paper titles doesn't crash on Windows.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except Exception:
    pass

# Reduce noise from upstream API clients
logging.basicConfig(level=logging.WARNING)

# Suppress noisy hf_xet warnings
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

from vaultlab.research import (
    Corpus,
    ResearchClient,
    build_corpus_from_seeds,
    compute_metrics,
    get_references_via_crossref,
)


def main() -> int:
    print("=" * 70)
    print("TRIAL RUN: CRISPR base editing corpus")
    print("=" * 70)

    client = ResearchClient()
    print("\n[1/3] Searching 'CRISPR base editing' (max_results=10)...")
    raw_seeds = client.search("CRISPR base editing", max_results=10)
    # Multi-source search returns >max_results combined; cap to 10 with DOI.
    seeds = [s for s in raw_seeds if s.doi][:10]
    print(f"  Got {len(seeds)} seeds (with DOI, capped to 10)")
    for i, p in enumerate(seeds, 1):
        title = p.title[:80]
        print(f"    {i}. {title}  ({p.year})  doi={p.doi or '<none>'}")

    seeds_with_doi = [s for s in seeds if s.doi]
    print(f"\n[2/3] Building corpus from {len(seeds_with_doi)} seeds with DOIs...")
    corpus = build_corpus_from_seeds(
        seeds_with_doi,
        topic="CRISPR base editing",
        fetch_refs=get_references_via_crossref,
    )

    n_with_refs = sum(1 for d in corpus.seed_dois if corpus.references.get(d))
    print(f"  Seeds with refs from CrossRef: {n_with_refs}/{len(seeds_with_doi)}")
    print(f"  Total papers in corpus: {corpus.n_papers}")
    print(f"  Total citation edges: {corpus.n_edges}")

    if n_with_refs < 7:
        print(
            f"\n  FAIL: only {n_with_refs}/{len(seeds_with_doi)} seeds returned refs."
            " Verification target is >=7."
        )
        return 1

    print("\n[3/3] Computing metrics...")
    metrics = compute_metrics(corpus)
    print(f"  og_score papers: {len(metrics.og_score)}")
    print(f"  forward_influence papers: {len(metrics.forward_influence)}")
    print(f"  co_citation_pairs: {len(metrics.co_citation_pairs)}")

    # Top OG papers
    top = metrics.top_og(10)
    print("\n  Top 10 OG papers (most cited by seeds):")
    for doi, score in top:
        title = corpus.papers.get(doi).title if doi in corpus.papers else "<unknown>"
        title = title[:60]
        print(f"    {score:.2f}  {doi}  {title}")

    max_og = max(metrics.og_score.values()) if metrics.og_score else 0.0
    print(f"\n  Max OG score: {max_og:.3f}")
    if max_og < 0.3:
        print(f"  FAIL: max OG score {max_og:.3f} < 0.3 verification target.")
        return 1

    bucket_counts: dict[str, int] = {}
    for b in metrics.year_buckets.values():
        bucket_counts[b] = bucket_counts.get(b, 0) + 1
    print(f"  Year buckets: {bucket_counts}")
    has_h = bucket_counts.get("history", 0) > 0
    has_d = bucket_counts.get("development", 0) > 0
    has_s = bucket_counts.get("sota", 0) > 0
    if not (has_h and has_d and has_s):
        print("  FAIL: year buckets do not cover history+development+sota.")
        return 1

    print("\n  Top 10 forward-influence (in-degree on seed subgraph):")
    fi_top = sorted(
        metrics.forward_influence.items(), key=lambda x: x[1], reverse=True
    )[:10]
    for doi, count in fi_top:
        title = corpus.papers.get(doi).title[:60] if doi in corpus.papers else ""
        print(f"    {count}  {doi}  {title}")

    print("\n  Top 5 co-citation pairs:")
    for a, b, c in metrics.co_citation_pairs[:5]:
        print(f"    {c}x  {a}  +  {b}")

    print("\n" + "=" * 70)
    print("TRIAL RUN: ALL VERIFICATIONS PASSED")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
