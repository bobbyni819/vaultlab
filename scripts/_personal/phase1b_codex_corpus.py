"""Phase 1B — corpus build with backward (CrossRef refs) + forward (S2 cited-by).

Tests:
* Backward expansion via CrossRef references (existing path)
* Forward expansion via Semantic Scholar /paper/{doi}/citations (new, #92)
* Corpus.cited_by field populated alongside Corpus.references
* OG-score / forward_influence metrics computed across the larger graph
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from vaultlab.research import ResearchClient
from vaultlab.research.query_expansion import expand_topic_deterministic
from vaultlab.research.corpus import build_corpus_from_seeds, expand_corpus_forward
from vaultlab.research.graph_metrics import compute_metrics


TOPIC = (
    "CODEX multiplexed imaging — methods and applications "
    "across tissue types"
)
MAX_SEEDS = 30  # new default (was 8)


def main() -> None:
    print(f"Topic: {TOPIC}")
    print(f"max_seeds: {MAX_SEEDS}")
    print()

    # 1. Search
    queries = expand_topic_deterministic(TOPIC, target_n=5)
    client = ResearchClient()
    print("Phase 1A: search...")
    t0 = time.time()
    papers, search_trace = client.search_with_trace(
        TOPIC, max_results=50, queries=queries
    )
    print(f"  --> {len(papers)} unique papers ({time.time()-t0:.1f}s)")

    # Cap to top max_seeds (recency-balanced ranking already applied)
    seeds = papers[:MAX_SEEDS]
    print(f"  --> top {len(seeds)} seeds kept")
    print()

    # 2. Backward corpus expansion (CrossRef refs)
    print("Phase 1B-1: backward expansion (CrossRef refs)...")
    t0 = time.time()
    corpus = build_corpus_from_seeds(seeds, topic=TOPIC)
    backward_elapsed = time.time() - t0
    backward_papers = corpus.n_papers
    backward_edges = corpus.n_edges
    print(
        f"  --> {backward_papers} corpus papers, "
        f"{backward_edges} backward edges ({backward_elapsed:.1f}s)"
    )
    print()

    # 3. Forward expansion (S2 cited-by) — the NEW path from #92
    print("Phase 1B-2: forward expansion (S2 cited-by, NEW)...")
    t0 = time.time()
    s2 = client._semantic
    if s2 is None or not hasattr(s2, "get_citations"):
        print("  --> SKIPPED: no S2 client available")
    else:
        def _fetch_forward(doi: str, limit: int):
            return s2.get_citations(doi, limit=limit)

        try:
            expand_corpus_forward(
                corpus,
                fetch_citations=_fetch_forward,
                seed_only=True,
                max_per_paper=50,  # default
            )
            forward_elapsed = time.time() - t0
            new_papers = corpus.n_papers - backward_papers
            forward_edges = sum(len(v) for v in corpus.cited_by.values())
            print(
                f"  --> +{new_papers} new papers from forward expansion, "
                f"{forward_edges} forward edges ({forward_elapsed:.1f}s)"
            )
            print(f"  --> total corpus: {corpus.n_papers} papers")
        except Exception as e:
            print(f"  --> forward expansion failed: {e}")
    print()

    # 4. Metrics across the full corpus
    print("Phase 1B-3: compute citation-graph metrics...")
    t0 = time.time()
    compute_metrics(corpus)
    print(f"  --> metrics computed ({time.time()-t0:.1f}s)")
    print()

    # 5. Corpus shape
    print("=" * 80)
    print("CORPUS SHAPE")
    print("=" * 80)
    print(f"  seeds:                       {len(corpus.seeds)}")
    print(f"  total papers:                {corpus.n_papers}")
    print(f"  backward edges (refs):       {corpus.n_edges}")
    print(f"  forward edges (cited_by):    "
          f"{sum(len(v) for v in corpus.cited_by.values())}")
    print(f"  papers with refs available:  {sum(1 for v in corpus.references.values() if v)}")
    print(f"  papers with cited_by:        {sum(1 for v in corpus.cited_by.values() if v)}")
    print()

    # 6. Top OG-score papers
    metrics = corpus.metrics
    if metrics:
        og = sorted(
            metrics.og_score.items(),
            key=lambda kv: kv[1],
            reverse=True,
        )[:15]
        print("Top 15 OG-score papers (cross-corpus citation frequency):")
        for doi, score in og:
            paper = corpus.papers.get(doi)
            title = (paper.title if paper else "(unknown)")[:60]
            year = paper.year if paper else 0
            print(f"  {score:>5.2f}  {year}  {doi[:40]:40s}  {title}")
        print()

    # 7. Year distribution — are 2024-25 papers in the corpus now?
    year_counts: dict[int, int] = {}
    for p in corpus.papers.values():
        if p.year:
            year_counts[p.year] = year_counts.get(p.year, 0) + 1
    print("Year distribution (top 10 most-recent years):")
    for year in sorted(year_counts.keys(), reverse=True)[:10]:
        bar = "#" * min(40, year_counts[year])
        print(f"  {year}: {year_counts[year]:>4d} {bar}")
    print()

    # 8. Save corpus state for downstream phases
    out_dir = Path("G:/My Drive/Knowledge/vaultlab/Output/_phase1b-codex-2026-05-01")
    out_dir.mkdir(exist_ok=True, parents=True)
    seed_list = [
        {"doi": s.doi, "title": s.title, "year": s.year,
         "citation_count": s.citation_count, "source_api": s.source_api}
        for s in seeds
    ]
    (out_dir / "seeds.json").write_text(
        json.dumps(seed_list, indent=2), encoding="utf-8"
    )
    corpus_summary = {
        "topic": TOPIC,
        "n_seeds": len(corpus.seeds),
        "n_papers": corpus.n_papers,
        "n_backward_edges": corpus.n_edges,
        "n_forward_edges": sum(len(v) for v in corpus.cited_by.values()),
        "year_distribution": year_counts,
        "top_og_papers": [
            {"doi": doi, "og_score": score,
             "title": (corpus.papers.get(doi).title if corpus.papers.get(doi) else "")}
            for doi, score in og[:30]
        ] if metrics else [],
    }
    (out_dir / "corpus-summary.json").write_text(
        json.dumps(corpus_summary, indent=2, default=str), encoding="utf-8"
    )
    print(f"Saved seeds.json and corpus-summary.json to {out_dir}")


if __name__ == "__main__":
    main()
