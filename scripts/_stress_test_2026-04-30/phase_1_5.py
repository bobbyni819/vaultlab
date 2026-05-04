"""Stress test Phase 1-5: search → search log → article stubs → corpus → PDF acquire.

Deterministic phases — no LLM calls. Dumps a state file so subsequent
phases (picker / binner / summaries / arc) can resume with the same corpus.
"""
from __future__ import annotations

import json
import logging
import pickle
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore
except Exception:
    pass

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

from vaultlab.research import ResearchClient
from vaultlab.research.acquisition import acquire_pdfs_for_corpus
from vaultlab.research.corpus import build_corpus_from_seeds
from vaultlab.research.graph_metrics import compute_metrics
from vaultlab.kb.paths import (
    article_stub_path,
    search_log_path,
    slugify_topic,
    summary_path,
)

TOPIC = "CODEX multiplexed imaging — methods and applications across tissue types"
KB_ROOT = Path("G:/My Drive/Knowledge/vaultlab")
DATE_STR = "2026-04-30"
MAX_SEEDS = 8
SCRATCH = Path(__file__).parent
STATE_FILE = SCRATCH / "state.pkl"


def _write_search_log(kb_root: Path, topic: str, seeds, date_str: str) -> Path:
    # Reuse vaultlab's writer
    from vaultlab.research.lineage import _write_search_log
    return _write_search_log(kb_root=kb_root, topic=topic, seeds=seeds, date_str=date_str)


def _write_article_stub(kb_root: Path, paper) -> Path | None:
    from vaultlab.research.lineage import _write_article_stub
    return _write_article_stub(kb_root, paper)


def main() -> int:
    started = time.time()
    print("=" * 72)
    print(f"STRESS TEST  /lit-arc  Phase 1-5 (deterministic)")
    print(f"  topic   = {TOPIC}")
    print(f"  kb_root = {KB_ROOT}")
    print(f"  date    = {DATE_STR}")
    print(f"  max_seeds = {MAX_SEEDS}")
    print("=" * 72)

    # Phase 1: search
    print("\n[Phase 1] search ...")
    t0 = time.time()
    client = ResearchClient()
    raw_seeds = client.search(TOPIC, max_results=MAX_SEEDS)
    seeds = [s for s in raw_seeds if s.doi][:MAX_SEEDS]
    print(f"  {time.time() - t0:.1f}s — {len(seeds)} seeds with DOI (raw {len(raw_seeds)})")
    for i, s in enumerate(seeds, 1):
        print(f"    [{i}] {s.doi}  {s.year}  {(s.title or '')[:80]}")

    # Phase 2: search log
    print("\n[Phase 2] search log ...")
    t0 = time.time()
    log_path = _write_search_log(KB_ROOT, TOPIC, seeds, DATE_STR)
    print(f"  {time.time() - t0:.1f}s — {log_path}")

    # Phase 3: article stubs
    print("\n[Phase 3] article stubs ...")
    t0 = time.time()
    stubs: list[Path] = []
    for s in seeds:
        p = _write_article_stub(KB_ROOT, s)
        if p is not None:
            stubs.append(p)
    print(f"  {time.time() - t0:.1f}s — {len(stubs)} stubs")

    # Phase 4: corpus + metrics (CrossRef ref-walk)
    print("\n[Phase 4] corpus build (CrossRef ref-walk) ...")
    t0 = time.time()
    corpus = build_corpus_from_seeds(seeds, topic=TOPIC)
    compute_metrics(corpus)
    print(f"  {time.time() - t0:.1f}s — {corpus.n_papers} papers, {corpus.n_edges} edges")

    # Phase 5: PDF acquisition
    print("\n[Phase 5] PDF acquisition (waterfall) ...")
    t0 = time.time()
    pdf_cache_dir = KB_ROOT / "Sources" / "Papers"
    pdf_cache_dir.mkdir(parents=True, exist_ok=True)
    acq = acquire_pdfs_for_corpus(
        corpus, pdf_cache_dir, skip_paywalled=True, aggressive_retry=False
    )
    pdfs_acquired = sum(1 for r in acq.values() if getattr(r, "pdf_path", None) is not None)
    print(f"  {time.time() - t0:.1f}s — {pdfs_acquired} PDFs acquired (out of {len(acq)})")

    # Persist state
    state = {
        "topic": TOPIC,
        "kb_root": str(KB_ROOT),
        "date_str": DATE_STR,
        "max_seeds": MAX_SEEDS,
        "log_path": str(log_path),
        "stubs": [str(p) for p in stubs],
        "corpus": corpus,  # Corpus + metrics
        "acq_results": {doi: {
            "pdf_path": str(r.pdf_path) if r.pdf_path else None,
            "source": r.source,
            "license": getattr(r, "license", "") or "",
        } for doi, r in acq.items()},
        "pdfs_acquired": pdfs_acquired,
        "duration": time.time() - started,
    }
    with STATE_FILE.open("wb") as fh:
        pickle.dump(state, fh)
    print(f"\n[state] wrote {STATE_FILE} ({STATE_FILE.stat().st_size} bytes)")
    print(f"[state] total Phase 1-5 wall time: {time.time() - started:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
