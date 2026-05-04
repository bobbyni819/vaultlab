"""One-off runner: short-scope lit arc + deck for
multiscale tissue simulation for lung infectious disease.

Phase 1: search across 7 sources with 5 well-tuned sub-queries,
score, apply SHORT recency quotas, emit picks.json for the orchestrator.
"""
from __future__ import annotations
import json
from pathlib import Path
from datetime import date

from vaultlab.research.search import unified_search
from vaultlab.research.sources.paperclip import PaperclipClient
from vaultlab.research.sources.ncbi import NCBIClient
from vaultlab.research.sources.springer import SpringerClient
from vaultlab.research.sources.semantic import SemanticScholarClient
from vaultlab.research.sources.crossref import CrossRefClient
from vaultlab.research.sources.biorxiv import BioRxivClient
from vaultlab.research.sources.elsevier import ElsevierClient
from vaultlab.research.config import get_config
from vaultlab.research.scoring import blended_paper_score, citations_per_year
from vaultlab.research.recency_quota import (
    apply_recency_quotas, SHORT_QUOTA_24MO, SHORT_QUOTA_12MO,
)

OUT_DIR = Path("G:/My Drive/Knowledge/vaultlab/Wiki/Projects/multiscale-tissue-simulation-lung-infection/_short_2026_05_02_workspace")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# 5 well-tuned sub-queries from START_HERE.md
SUBQUERIES = [
    "multiscale tissue simulation Vivarium PhysiCell",
    "agent-based model lung infection alveolar",
    "host pathogen computational model spatial",
    "spatial proteomics CODEX multiscale tissue computational",
    "lung infection immune microenvironment imaging",
]

apis = get_config()
pc = PaperclipClient()
ncbi = NCBIClient(api_key=apis.get("ncbi_api_key"))
springer = SpringerClient(
    meta_api_key=apis.get("springer_meta_api_key", ""),
    oa_api_key=apis.get("springer_open_access_api_key", ""),
)
semantic = SemanticScholarClient(api_key=apis.get("semantic_scholar_api_key", ""))
crossref = CrossRefClient()
biorxiv = BioRxivClient()
elsevier = ElsevierClient(api_key=apis.get("elsevier_key", ""))

print(f"Running unified search across 5 sub-queries x 7 sources, max 30/source/query...")
papers, trace = unified_search(
    query=SUBQUERIES[0],            # primary anchor
    queries=SUBQUERIES,             # fan-out to all 5
    max_results=30,
    sources=["pubmed", "springer", "semantic", "crossref", "biorxiv", "scopus", "paperclip"],
    ncbi_client=ncbi,
    springer_client=springer,
    semantic_client=semantic,
    crossref_client=crossref,
    biorxiv_client=biorxiv,
    sciencedirect_client=elsevier,
    paperclip_client=pc,
    return_trace=True,
)
print(f"Total deduped: {len(papers)} papers")
print(f"Trace summary:")
for src, info in (trace.per_source if hasattr(trace, 'per_source') else {}).items():
    print(f"  {src}: {info}")

# Serialize the candidate pool with computed metrics
def paper_to_dict(p):
    d = p.to_dict() if hasattr(p, 'to_dict') else dict(p.__dict__)
    # ensure year is an int when present
    if d.get('year'):
        try:
            d['year'] = int(d['year'])
        except (TypeError, ValueError):
            pass
    d['cpy'] = citations_per_year(p)
    d['blended'] = blended_paper_score(p)
    return d

candidates = [paper_to_dict(p) for p in papers if getattr(p, 'doi', None)]
# normalize composite_score key on each candidate so apply_recency_quotas
# can use it for swap-in ranking
for c in candidates:
    c['composite_score'] = c.get('blended') or 0.0
candidates.sort(key=lambda d: d['composite_score'], reverse=True)
print(f"With DOI: {len(candidates)}")
print(f"Top 5 by blended score:")
for c in candidates[:5]:
    print(f"  {c['composite_score']:.2f}  {c.get('year','?')}  {c.get('doi','?')[:50]}  {(c.get('title','')[:70])}")

# Persist candidate pool
(OUT_DIR / "candidates_full.json").write_text(
    json.dumps(candidates, indent=2, default=str), encoding="utf-8"
)

# Apply SHORT recency quotas. Take top-30 first as candidate picks, then quota-rerank to top-15.
target_n = 15
top30 = candidates[:30]
# Build picks list with required fields (doi, year, rank, composite_score, title)
picks_input = []
for i, c in enumerate(top30, start=1):
    picks_input.append({
        "doi": c.get("doi", ""),
        "year": c.get("year", 0) or 0,
        "rank": i,
        "composite_score": c["composite_score"],
        "title": c.get("title", ""),
    })
candidate_pool = {(c.get("doi") or "").lower(): {
    "doi": c.get("doi", ""),
    "year": c.get("year", 0) or 0,
    "composite_score": c["composite_score"],
    "title": c.get("title", ""),
} for c in candidates}

quota_result = apply_recency_quotas(
    picks=picks_input,
    candidate_pool=candidate_pool,
    target_n=target_n,
    quota_24mo=SHORT_QUOTA_24MO,
    quota_12mo=SHORT_QUOTA_12MO,
)
print()
print(f"Applied SHORT quotas (24mo={SHORT_QUOTA_24MO}, 12mo={SHORT_QUOTA_12MO}, target={target_n})")
print(f"Final picks: {len(quota_result.picks)}, swaps: {quota_result.n_swaps}, unmet_24mo: {quota_result.unmet_24mo}, unmet_12mo: {quota_result.unmet_12mo}")

# Add seed papers (from START_HERE.md --always-include) at top, dedup
SEEDS = [
    "10.1093/bioinformatics/btac049",        # Vivarium 2022
    "10.1038/s41586-023-05915-x",            # Hickey CODEX intestine
    "10.3389/fimmu.2021.727626",             # Hickey CODEX cell typing
    "10.1016/j.cobme.2019.10.001",           # multiscale models of infection
]
final_picks_dois = []
seen = set()
# seeds first
for d in SEEDS:
    dl = d.lower()
    if dl not in seen:
        final_picks_dois.append(d)
        seen.add(dl)
# then quota-balanced picks
for p in quota_result.picks:
    dl = (p.get("doi") or "").lower()
    if dl and dl not in seen:
        final_picks_dois.append(p["doi"])
        seen.add(dl)
# trim to target_n+seeds (so we have ~15+4 = up to 19)
final_picks_dois = final_picks_dois[: target_n + len(SEEDS)]

# Persist final picks
final_picks = []
candidate_by_doi = {(c.get("doi") or "").lower(): c for c in candidates}
for d in final_picks_dois:
    c = candidate_by_doi.get(d.lower())
    if c is None:
        # seed paper not in candidate pool � fetch metadata stub
        final_picks.append({"doi": d, "year": None, "title": "(seed; not in candidate pool)"})
    else:
        final_picks.append({
            "doi": c.get("doi"),
            "year": c.get("year"),
            "title": c.get("title"),
            "abstract": c.get("abstract", ""),
            "journal": c.get("journal", ""),
            "authors": c.get("authors", []),
            "citation_count": c.get("citation_count", 0),
            "source_api": c.get("source_api", ""),
            "composite_score": c.get("composite_score", 0.0),
        })

(OUT_DIR / "final_picks.json").write_text(
    json.dumps(final_picks, indent=2, default=str), encoding="utf-8"
)
print()
print(f"FINAL PICKS ({len(final_picks)}):")
for i, p in enumerate(final_picks, 1):
    print(f"  {i:2d}. {p.get('year','?')}  {(p.get('doi') or '')[:50]:50s}  {(p.get('title') or '')[:60]}")
print()
print(f"Wrote: {OUT_DIR / 'final_picks.json'}")
