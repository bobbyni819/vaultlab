"""Phase 1A — exercise search step on CODEX with the new flags.

Tests:
* 5 query variants (deterministic fallback) fan out across all sources
* Scopus is in the source list
* Per-source hit counts visible in the trace
* Recency-balanced ranking applied post-dedup
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from vaultlab.research import ResearchClient
from vaultlab.research.query_expansion import expand_topic_deterministic
from vaultlab.research.scoring import blended_paper_score


TOPIC = (
    "CODEX multiplexed imaging — methods and applications "
    "across tissue types"
)


def main() -> None:
    print(f"Topic: {TOPIC}")
    print()

    # 1. Multi-query expansion (deterministic fallback — no LLM)
    queries = expand_topic_deterministic(TOPIC, target_n=5)
    print(f"Query variants ({len(queries)}):")
    for i, q in enumerate(queries, 1):
        print(f"  {i}. {q}")
    print()

    # 2. Initialize the research client (auto-instantiates Scopus client
    # if elsevier_key is configured)
    client = ResearchClient()
    available = []
    if client._ncbi:
        available.append("pubmed")
    if client._springer:
        available.append("springer")
    if client._semantic:
        available.append("semantic")
    if client._crossref:
        available.append("crossref")
    if client._biorxiv:
        available.append("biorxiv")
    if client._sciencedirect:
        available.append("scopus")
    print(f"Sources available: {', '.join(available)}")
    print()

    # 3. Run unified search with multi-query expansion + recency-balanced ranking
    print("Running unified_search (multi-query, recency-balanced)...")
    started = time.time()
    papers, trace = client.search_with_trace(
        TOPIC,
        max_results=50,  # new default
        queries=queries,
    )
    elapsed = time.time() - started
    print(f"  --> {len(papers)} unique papers after dedup ({elapsed:.1f}s)")
    print()

    # 4. Per-source breakdown
    print("Per-source trace (raw hits before dedup):")
    for source_id, src_trace in trace.per_source.items():
        errs = (
            f", errors: {len(src_trace.errors)}"
            if src_trace.errors
            else ""
        )
        print(
            f"  {source_id:20s} {src_trace.hits:>4d} hits  "
            f"({src_trace.wall_time_ms:>5d}ms{errs})"
        )
    print()
    print(f"  total raw hits across all sources x all queries: "
          f"{sum(s.hits for s in trace.per_source.values())}")
    print(f"  deduped unique papers: {trace.deduped_seeds}")
    print()
    print("by_source_after_dedup (which source 'won' the primary record):")
    for k, v in sorted(trace.by_source_after_dedup.items()):
        print(f"  {k:20s} {v:>4d} primary records")
    print()

    # 5. Top-10 by recency-balanced score (the new ranking)
    print("Top 10 papers by recency-balanced ranking:")
    print(f"{'#':>3}  {'year':>4}  {'cites':>5}  {'score':>6}  title")
    print("-" * 100)
    for i, p in enumerate(papers[:10], 1):
        score = blended_paper_score(p, current_year=2026)
        title = (p.title or "(no title)")[:65]
        print(
            f"{i:>3}  {p.year:>4}  {p.citation_count:>5}  "
            f"{score:>6.2f}  {title}"
        )
    print()

    # 6. Save trace to disk
    out_dir = Path("G:/My Drive/Knowledge/vaultlab/Output/_phase1a-codex-2026-05-01")
    out_dir.mkdir(exist_ok=True, parents=True)
    out_path = out_dir / "search-trace.json"
    out_path.write_text(json.dumps(trace.to_dict(), indent=2), encoding="utf-8")
    papers_path = out_dir / "top-papers.json"
    papers_path.write_text(
        json.dumps(
            [
                {
                    "rank": i + 1,
                    "title": p.title,
                    "year": p.year,
                    "citation_count": p.citation_count,
                    "doi": p.doi,
                    "source_api": p.source_api,
                    "blended_score": round(
                        blended_paper_score(p, current_year=2026), 3
                    ),
                }
                for i, p in enumerate(papers[:30])
            ],
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Saved: {out_path}")
    print(f"Saved: {papers_path}")


if __name__ == "__main__":
    main()
