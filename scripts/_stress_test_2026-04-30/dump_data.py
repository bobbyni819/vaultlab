"""Dump corpus abstracts + Tier-A PDF text snapshots so I (Claude) can
read them in-context, then make smart decisions baked into the callbacks.
"""
from __future__ import annotations

import json
import logging
import pickle
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore
except Exception:
    pass

logging.basicConfig(level=logging.WARNING)

from vaultlab.research.acquisition import cache_path_for
from vaultlab.research.picker import _build_candidates
from vaultlab.research.binning import _build_candidates as _binning_build_candidates
from vaultlab.kb.paths import slugify_doi

SCRATCH = Path(__file__).parent
STATE_FILE = SCRATCH / "state.pkl"
DUMP_FILE = SCRATCH / "dump.json"


def main() -> int:
    with STATE_FILE.open("rb") as fh:
        state = pickle.load(fh)
    corpus = state["corpus"]
    kb_root = Path(state["kb_root"])
    pdf_cache_dir = kb_root / "Sources" / "Papers"

    print(f"Corpus: {corpus.n_papers} papers, {corpus.n_edges} edges")
    print(f"Seeds: {len(corpus.seed_dois)}")
    print(f"PDFs cached: {state['pdfs_acquired']}")

    # 1. Picker candidates (top 30 by citation graph score)
    picker_candidates = _build_candidates(
        corpus,
        coarse_n=30,
        kb_root=kb_root,
        pdf_cache_dir=pdf_cache_dir,
    )
    print(f"Picker candidates: {len(picker_candidates)}")

    # 2. Binning candidates (cap 200)
    binning_candidates = _binning_build_candidates(corpus, max_candidates=200)
    print(f"Binning candidates: {len(binning_candidates)}")

    dump = {
        "topic": state["topic"],
        "seeds": [
            {
                "doi": d,
                "title": corpus.papers[d].title,
                "authors": list(corpus.papers[d].authors or []),
                "year": corpus.papers[d].year,
                "journal": corpus.papers[d].journal,
                "abstract": corpus.papers[d].abstract or "",
            }
            for d in corpus.seed_dois
        ],
        "picker_candidates": [
            {
                "doi": c.doi,
                "title": c.title,
                "authors": list(c.authors or []),
                "year": c.year,
                "journal": c.journal,
                "abstract": (c.abstract or "")[:1500],
                "og_score": c.og_score,
                "forward_influence": c.forward_influence,
                "has_pdf": c.has_pdf,
            }
            for c in picker_candidates
        ],
        "binning_candidates": [
            {
                "doi": c.doi,
                "title": c.title,
                "year": c.year,
                "abstract": (c.abstract or "")[:600],
                "og_score": c.og_score,
                "forward_influence": c.forward_influence,
                "deterministic_bucket": c.deterministic_bucket,
            }
            for c in binning_candidates
        ],
        "co_citation_pairs": [
            (a, b, n) for (a, b, n) in (corpus.metrics.co_citation_pairs[:15] if corpus.metrics else [])
        ],
        "year_buckets_deterministic": dict(corpus.metrics.year_buckets) if corpus.metrics else {},
        "top_og_papers": [
            {
                "doi": d,
                "score": s,
                "title": corpus.papers[d].title if d in corpus.papers else "",
                "year": corpus.papers[d].year if d in corpus.papers else 0,
            }
            for d, s in sorted(
                (corpus.metrics.og_score.items() if corpus.metrics else []),
                key=lambda kv: kv[1], reverse=True,
            )[:15]
        ],
        "all_papers_with_pdfs": [
            {
                "doi": doi,
                "title": corpus.papers[doi].title if doi in corpus.papers else "",
                "year": corpus.papers[doi].year if doi in corpus.papers else 0,
                "og_score": corpus.metrics.og_score.get(doi, 0.0) if corpus.metrics else 0.0,
                "fwd": corpus.metrics.forward_influence.get(doi, 0) if corpus.metrics else 0,
                "has_pdf": True,
            }
            for doi, info in state["acq_results"].items()
            if info["pdf_path"]
        ],
    }

    DUMP_FILE.write_text(json.dumps(dump, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {DUMP_FILE} ({DUMP_FILE.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
