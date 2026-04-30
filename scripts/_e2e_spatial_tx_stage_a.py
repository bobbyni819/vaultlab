"""Stage A of the L4 e2e spatial-tx test.

Runs the deterministic phases (1-5) of run_lit_arc:
  - Phase 1: search seeds
  - Phase 2: write search log
  - Phase 3: write article stubs
  - Phase 4: build corpus + compute metrics
  - Phase 5: acquire PDFs (waterfall)

Then pickles the state to disk so Stage B (the Claude Code reader pass)
can pick it up.
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
    ensure_parent,
    search_log_path,
    slugify_topic,
)
from vaultlab.research import ResearchClient
from vaultlab.research.acquisition import acquire_pdfs_for_corpus, cache_path_for
from vaultlab.research.corpus import build_corpus_from_seeds
from vaultlab.research.graph_metrics import compute_metrics
from vaultlab.research.lineage import _write_search_log, _write_article_stub

TOPIC = "spatial transcriptomics tumor microenvironment"
KB_ROOT = Path(r"G:/My Drive/Knowledge/vaultlab")
PROJECT_SLUG = "spatial-tx-tme-test"
MAX_SEEDS = 12
DATE_STR = date.today().strftime("%Y-%m-%d")
STATE_PATH = KB_ROOT / "Output" / PROJECT_SLUG / "stage_a_state.pkl"


def main() -> int:
    started = time.time()
    print("=" * 72)
    print("STAGE A: spatial-tx-tme — search, corpus, metrics, PDFs")
    print("=" * 72)
    print(f"Topic: {TOPIC}")
    print(f"KB:    {KB_ROOT}")
    print(f"Date:  {DATE_STR}")

    KB_ROOT.mkdir(parents=True, exist_ok=True)
    (KB_ROOT / "Output" / PROJECT_SLUG).mkdir(parents=True, exist_ok=True)
    pdf_cache_dir = KB_ROOT / "Sources" / "Papers"
    pdf_cache_dir.mkdir(parents=True, exist_ok=True)

    # ---------------- Phase 1: search ----------------
    print("\n[1] Searching seeds via ResearchClient...")
    client = ResearchClient()
    raw_seeds = client.search(TOPIC, max_results=MAX_SEEDS)
    seeds = [s for s in raw_seeds if s.doi][:MAX_SEEDS]
    print(f"    Got {len(raw_seeds)} raw, {len(seeds)} with DOI")
    for i, s in enumerate(seeds, 1):
        print(f"      {i}. {(s.title or '')[:80]} ({s.year}) — {s.doi}")

    # ---------------- Phase 2: search log ----------------
    print("\n[2] Writing search log...")
    log_path = _write_search_log(kb_root=KB_ROOT, topic=TOPIC, seeds=seeds, date_str=DATE_STR)
    print(f"    {log_path}")

    # ---------------- Phase 3: article stubs ----------------
    print("\n[3] Writing article stubs...")
    article_stubs: list[Path] = []
    for seed in seeds:
        p = _write_article_stub(KB_ROOT, seed)
        if p is not None:
            article_stubs.append(p)
    print(f"    Wrote {len(article_stubs)} stubs")

    # ---------------- Phase 4: corpus + metrics ----------------
    print("\n[4] Building corpus (walking 1 layer of CrossRef refs)...")
    corpus = build_corpus_from_seeds(seeds, topic=TOPIC)
    compute_metrics(corpus)
    print(f"    Corpus: {corpus.n_papers} papers, {corpus.n_edges} edges")

    # ---------------- Phase 5: PDF acquisition ----------------
    print("\n[5] Acquiring PDFs via waterfall (Unpaywall/PMC/...)")
    acq_results = acquire_pdfs_for_corpus(
        corpus,
        pdf_cache_dir,
        skip_paywalled=True,
    )
    pdfs_acquired = sum(
        1 for r in acq_results.values() if getattr(r, "pdf_path", None) is not None
    )
    print(f"    PDFs acquired: {pdfs_acquired} / {corpus.n_papers}")

    # ---------------- Save state ----------------
    state = {
        "topic": TOPIC,
        "date_str": DATE_STR,
        "kb_root": str(KB_ROOT),
        "project_slug": PROJECT_SLUG,
        "max_seeds": MAX_SEEDS,
        "seeds": seeds,
        "corpus": corpus,
        "acq_results": acq_results,
        "pdf_cache_dir": str(pdf_cache_dir),
        "log_path": str(log_path),
        "article_stubs": [str(p) for p in article_stubs],
        "pdfs_acquired": pdfs_acquired,
    }
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_PATH, "wb") as f:
        pickle.dump(state, f)
    print(f"\nState saved to: {STATE_PATH}")

    # ---------------- Print top-OG-by-score for downstream use ----------------
    print("\nTop-10 by og_score + forward_influence:")
    metrics = corpus.metrics
    if metrics is not None:
        def _score(d):
            return float(metrics.og_score.get(d, 0.0)) + float(
                metrics.forward_influence.get(d, 0)
            )
        ranked = sorted(corpus.papers.keys(), key=_score, reverse=True)[:15]
        for i, doi in enumerate(ranked, 1):
            p = corpus.papers[doi]
            pdf = cache_path_for(doi, pdf_cache_dir)
            has_pdf = "[PDF]" if pdf.exists() else "[--]"
            title = (p.title or "")[:60]
            print(f"  {i:2}. {has_pdf} og={metrics.og_score.get(doi, 0):.2f} fi={metrics.forward_influence.get(doi, 0)} | {doi} — {title}")

    print(f"\nElapsed: {time.time()-started:.1f}s")
    print("Stage A complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
