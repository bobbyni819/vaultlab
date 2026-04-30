"""Stage B of the L4 e2e spatial-tx test.

Loads stage A state + a JSON map of doi -> response_json (which I, the
Claude Code session, will fill in by Reading each PDF), then drives:
  - Phase 6: build PaperSummary objects via prepare_summary_task /
    render_summary_from_response, write to Wiki/Summaries/
  - Phase 7: build the lineage arc via prepare_arc_task /
    render_arc_from_response, write to Wiki/Concepts/
  - Phase 8: provenance receipts

After this, runs figure acquisition + deck composition.
"""
from __future__ import annotations

import json
import os
import pickle
import sys
import time
from datetime import date
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

os.environ.pop("ANTHROPIC_API_KEY", None)

from vaultlab.kb.paths import (
    article_stub_path,
    concept_path,
    summary_path,
    slugify_doi,
)
from vaultlab.provenance import ProvenanceRecord, write_receipts
from vaultlab.research.acquisition import cache_path_for
from vaultlab.research.lineage import (
    LineageRunResult,
    prepare_arc_task,
    render_arc_from_response,
    render_arc_markdown,
    _pick_top_n_for_summarization,
)
from vaultlab.research.summarize import (
    DEFAULT_MODEL,
    prepare_summary_task,
    render_summary_from_response,
    write_summary_to_kb,
    _build_base_summary,
)

PROJECT_SLUG = "spatial-tx-tme-test"
KB_ROOT = Path(r"G:/My Drive/Knowledge/vaultlab")
STATE_PATH = KB_ROOT / "Output" / PROJECT_SLUG / "stage_a_state.pkl"
RESPONSE_PATH = KB_ROOT / "Output" / PROJECT_SLUG / "reader_responses.json"
ARC_RESPONSE_PATH = KB_ROOT / "Output" / PROJECT_SLUG / "arc_response.json"
MAX_PAPERS_TO_SUMMARIZE = 8


def main() -> int:
    started = time.time()
    print("=" * 72)
    print("STAGE B: spatial-tx-tme — summaries + arc + provenance")
    print("=" * 72)

    with open(STATE_PATH, "rb") as f:
        state = pickle.load(f)
    topic = state["topic"]
    date_str = state["date_str"]
    seeds = state["seeds"]
    corpus = state["corpus"]
    acq_results = state["acq_results"]
    pdf_cache_dir = Path(state["pdf_cache_dir"])
    log_path = Path(state["log_path"])
    article_stubs = [Path(p) for p in state["article_stubs"]]
    pdfs_acquired = state["pdfs_acquired"]
    print(f"Topic: {topic}")
    print(f"Corpus: {corpus.n_papers} papers, {corpus.n_edges} edges")
    print(f"PDFs acquired: {pdfs_acquired}")

    # Load reader responses (DOI -> response_json)
    # Tier-A treatment is granted to ALL DOIs we have a response for
    # (these are the top-N with PDFs, picked manually since the
    # _pick_top_n_for_summarization picker doesn't filter by PDF
    # availability and would yield fewer than N actually-readable PDFs)
    with open(RESPONSE_PATH, "r", encoding="utf-8") as f:
        reader_responses = json.load(f)
    keep_set = set(d.lower() for d in reader_responses.keys())
    print(f"Tier-A picks (top {len(keep_set)} with PDFs): {len(keep_set)}")
    print(f"Reader responses provided for: {len(reader_responses)} DOIs")

    metrics = corpus.metrics
    summaries = {}
    summary_paths = {}

    # Build summaries for every paper in the corpus
    for doi in corpus.papers:
        paper = corpus.papers[doi]
        pdf_path = cache_path_for(doi, pdf_cache_dir)
        in_tier_a_pool = doi in keep_set and pdf_path.exists()
        has_reader_response = doi in reader_responses

        if in_tier_a_pool and has_reader_response:
            # Tier A path
            refs_missing = doi in corpus.references and not corpus.references.get(doi)
            acq_res = acq_results.get(doi)
            acq_source = getattr(acq_res, "source", "") or ""
            acq_license = getattr(acq_res, "license", None) or ""
            task = prepare_summary_task(
                doi=doi,
                pdf_path=pdf_path,
                paper_metadata={
                    "title": paper.title,
                    "authors": paper.authors,
                    "year": paper.year,
                    "journal": paper.journal,
                    "doi": paper.doi,
                    "citation_count": paper.citation_count,
                },
                corpus_metrics=metrics,
                corpus=corpus,
                crossref_refs_missing=refs_missing,
                kb_root=KB_ROOT,
                acquisition_source=acq_source,
                acquisition_license=acq_license,
            )
            summary = render_summary_from_response(
                task,
                reader_responses[doi],
                corpus_metrics=metrics,
                corpus=corpus,
            )
        else:
            # Tier C stub
            summary = _build_base_summary(
                doi=doi,
                paper_metadata={
                    "title": paper.title,
                    "authors": paper.authors,
                    "year": paper.year,
                    "journal": paper.journal,
                    "doi": paper.doi,
                    "citation_count": paper.citation_count,
                },
                corpus_metrics=metrics,
                corpus=corpus,
                acquisition_source="",
                acquisition_license="",
            )
            summary.tier = "C"
            summary.source_pdf = ""
        write_summary_to_kb(summary, KB_ROOT, overwrite=True)
        summaries[doi] = summary
        summary_paths[doi] = summary_path(KB_ROOT, doi)

    summaries_written = sum(1 for p in summary_paths.values() if p.exists())
    tier_a_count = sum(1 for s in summaries.values() if s.tier == "A")
    print(f"Summaries written: {summaries_written}  (Tier A: {tier_a_count}, Tier C: {summaries_written - tier_a_count})")

    # ---- Build arc task ----
    print("\nBuilding lineage arc...")
    arc_task = prepare_arc_task(
        topic=topic,
        corpus=corpus,
        summaries=summaries,
        kb_root=KB_ROOT,
        date_str=date_str,
    )
    print(f"Arc output path: {arc_task.output_path}")

    # Load arc response
    if ARC_RESPONSE_PATH.exists():
        with open(ARC_RESPONSE_PATH, "r", encoding="utf-8") as f:
            arc_response = json.load(f)
        print(f"Arc response loaded: history={len(arc_response.get('history', ''))}c, dev={len(arc_response.get('development', ''))}c, sota={len(arc_response.get('sota', ''))}c")
    else:
        print("WARNING: No arc response file; emitting structured tables only")
        arc_response = {}

    arc_path = render_arc_from_response(arc_task, arc_response, corpus)
    print(f"Arc written: {arc_path}")

    # ---- Provenance receipts ----
    record = ProvenanceRecord(
        generated_by="vaultlab.research.lineage.run_lit_arc (e2e Stage B)",
        project=PROJECT_SLUG,
        topic=topic,
        kind="lineage_arc",
        inputs=[str(p) for p in summary_paths.values()],
        params={
            "max_seeds": state["max_seeds"],
            "max_papers_to_summarize": MAX_PAPERS_TO_SUMMARIZE,
            "pdf_cache_dir": str(pdf_cache_dir),
            "narration": "claude" if arc_response else "skipped",
        },
        model=DEFAULT_MODEL if arc_response else "",
        related_outputs=[str(log_path), *[str(p) for p in article_stubs]],
        notes="L4 e2e test — Claude Code reader path",
    )
    write_receipts(arc_path, record)
    print(f"Provenance receipts written")

    duration = time.time() - started
    result = LineageRunResult(
        topic=topic,
        arc_path=arc_path,
        summary_paths=summary_paths,
        search_log_path=log_path,
        corpus_size=corpus.n_papers,
        pdfs_acquired=pdfs_acquired,
        summaries_written=summaries_written,
        duration_seconds=duration,
    )

    # Save result for Stage C
    result_path = KB_ROOT / "Output" / PROJECT_SLUG / "stage_b_result.pkl"
    with open(result_path, "wb") as f:
        pickle.dump({"result": result, "corpus": corpus, "summaries": summaries}, f)
    print(f"\nStage B result saved: {result_path}")
    print(f"Elapsed: {duration:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
