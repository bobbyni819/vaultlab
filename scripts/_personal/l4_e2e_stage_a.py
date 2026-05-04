"""L4 E2E Test - Stage A: search -> corpus -> PDF acquisition.

Runs the deterministic Python parts of the lit-arc pipeline up through
PDF acquisition, then persists the corpus + the list of Tier-A
SummarizationTasks to disk so the Claude Code agent can read each PDF
and produce per-paper JSON in stage B.

Output: scripts/_l4_state/
    corpus.pkl          - pickled Corpus (with metrics)
    seeds.json          - search-result metadata
    acq_results.json    - PDF acquisition results
    tasks.json          - per-paper summarization tasks (DOI, pdf_path, prompt, schema)
"""

from __future__ import annotations

import json
import pickle
import time
from dataclasses import asdict
from pathlib import Path

from vaultlab.kb.paths import (
    article_stub_path,
    ensure_parent,
    search_log_path,
    summary_path,
)
from vaultlab.research import ResearchClient
from vaultlab.research.acquisition import (
    acquire_pdfs_for_corpus,
    cache_path_for,
)
from vaultlab.research.corpus import build_corpus_from_seeds
from vaultlab.research.graph_metrics import compute_metrics
from vaultlab.research.lineage import (
    _pick_top_n_for_summarization,
    _write_article_stub,
    _write_search_log,
)
from vaultlab.research.summarize import prepare_summary_task

TOPIC = "CODEX cellular neighborhoods"
KB_ROOT = Path(r"G:/My Drive/Knowledge/vaultlab")
MAX_SEEDS = 12
MAX_PAPERS_TO_SUMMARIZE = 8
DATE_STR = "2026-04-29"

STATE_DIR = Path(r"C:/Users/bobby/Downloads/vaultlab/scripts/_l4_state")
STATE_DIR.mkdir(parents=True, exist_ok=True)


def main() -> None:
    started = time.time()
    pdf_cache_dir = KB_ROOT / "Sources" / "Papers"
    pdf_cache_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1/5] Searching for {TOPIC!r} (max_seeds={MAX_SEEDS})")
    client = ResearchClient()
    raw_seeds = client.search(TOPIC, max_results=MAX_SEEDS)
    seeds = [s for s in raw_seeds if s.doi][:MAX_SEEDS]
    print(f"      Got {len(seeds)} seed papers with DOIs")

    seeds_dump = [
        {
            "doi": s.doi,
            "title": s.title,
            "year": s.year,
            "journal": s.journal,
            "authors": list(s.authors or []),
            "citation_count": s.citation_count,
            "source_api": s.source_api,
        }
        for s in seeds
    ]
    (STATE_DIR / "seeds.json").write_text(
        json.dumps(seeds_dump, indent=2), encoding="utf-8"
    )

    print("[2/5] Writing search log + article stubs")
    log_path = _write_search_log(
        kb_root=KB_ROOT, topic=TOPIC, seeds=seeds, date_str=DATE_STR
    )
    print(f"      Search log: {log_path}")
    article_stubs = []
    for s in seeds:
        p = _write_article_stub(KB_ROOT, s)
        if p is not None:
            article_stubs.append(p)
    print(f"      Article stubs: {len(article_stubs)}")

    print("[3/5] Building corpus + computing metrics")
    corpus = build_corpus_from_seeds(seeds, topic=TOPIC)
    compute_metrics(corpus)
    print(f"      Corpus: {corpus.n_papers} papers, {corpus.n_edges} edges")

    print("[4/5] Acquiring PDFs (waterfall)")
    acq_results = acquire_pdfs_for_corpus(
        corpus,
        pdf_cache_dir,
        skip_paywalled=True,
    )
    pdfs_acquired = sum(
        1 for r in acq_results.values() if getattr(r, "pdf_path", None) is not None
    )
    print(f"      PDFs acquired: {pdfs_acquired}/{corpus.n_papers}")

    acq_dump = {
        doi: {
            "pdf_path": str(r.pdf_path) if getattr(r, "pdf_path", None) else None,
            "source": getattr(r, "source", ""),
            "license": getattr(r, "license", ""),
        }
        for doi, r in acq_results.items()
    }
    (STATE_DIR / "acq_results.json").write_text(
        json.dumps(acq_dump, indent=2), encoding="utf-8"
    )

    print("[5/5] Building per-paper SummarizationTask list (Tier-A picks)")
    keep = set(_pick_top_n_for_summarization(corpus, n=MAX_PAPERS_TO_SUMMARIZE))
    tasks_dump = []
    for doi in corpus.papers:
        paper = corpus.papers[doi]
        is_kept = doi in keep
        pdf = cache_path_for(doi, pdf_cache_dir)
        has_pdf = pdf.exists()
        tier = "A" if (is_kept and has_pdf) else "C"

        if tier == "A":
            refs_missing = (
                doi in corpus.references and not corpus.references.get(doi)
            )
            task = prepare_summary_task(
                doi=doi,
                pdf_path=pdf,
                paper_metadata={
                    "title": paper.title,
                    "authors": list(paper.authors or []),
                    "year": paper.year,
                    "journal": paper.journal,
                    "doi": paper.doi,
                    "citation_count": paper.citation_count,
                },
                corpus_metrics=corpus.metrics,
                corpus=corpus,
                crossref_refs_missing=refs_missing,
                kb_root=KB_ROOT,
            )
            tasks_dump.append(
                {
                    "doi": task.doi,
                    "tier": "A",
                    "pdf_path": str(task.pdf_path),
                    "title": paper.title,
                    "authors": list(paper.authors or []),
                    "year": paper.year,
                    "journal": paper.journal,
                    "crossref_refs_missing": task.crossref_refs_missing,
                    "output_path": str(task.output_path),
                    "summary_path": str(summary_path(KB_ROOT, doi)),
                    "system_prompt": task.system_prompt,
                    "prompt": task.prompt,
                    "response_schema": task.response_schema,
                }
            )
        else:
            tasks_dump.append(
                {
                    "doi": doi,
                    "tier": "C",
                    "pdf_path": None,
                    "title": paper.title,
                    "authors": list(paper.authors or []),
                    "year": paper.year,
                    "journal": paper.journal,
                    "summary_path": str(summary_path(KB_ROOT, doi)),
                }
            )

    (STATE_DIR / "tasks.json").write_text(
        json.dumps(tasks_dump, indent=2), encoding="utf-8"
    )
    print(f"      Tier-A tasks: {sum(1 for t in tasks_dump if t['tier'] == 'A')}")
    print(f"      Tier-C tasks: {sum(1 for t in tasks_dump if t['tier'] == 'C')}")

    # Pickle the corpus so stage C can re-use it (with metrics).
    with (STATE_DIR / "corpus.pkl").open("wb") as f:
        pickle.dump(corpus, f)
    with (STATE_DIR / "acq_results.pkl").open("wb") as f:
        pickle.dump(acq_results, f)

    elapsed = time.time() - started
    print(f"\n[DONE] Stage A complete in {elapsed:.1f}s")
    print(f"State dir: {STATE_DIR}")
    print(f"  - corpus.pkl ({corpus.n_papers} papers)")
    print(f"  - seeds.json ({len(seeds)} seeds)")
    print(f"  - acq_results.json ({pdfs_acquired} PDFs)")
    print(f"  - tasks.json ({len(tasks_dump)} tasks)")

    # Quick verification
    print("\nTop-3 by og_score:")
    metrics = corpus.metrics
    if metrics:
        top_og = sorted(metrics.og_score.items(), key=lambda kv: kv[1], reverse=True)[:5]
        for doi, score in top_og:
            p = corpus.papers.get(doi)
            title = p.title[:80] if p else "?"
            year = p.year if p else "?"
            print(f"  og={score:.2f}  {year}  {title}  [{doi}]")

    print("\nTop-3 by forward_influence:")
    if metrics:
        top_fwd = sorted(
            metrics.forward_influence.items(), key=lambda kv: kv[1], reverse=True
        )[:5]
        for doi, score in top_fwd:
            p = corpus.papers.get(doi)
            title = p.title[:80] if p else "?"
            year = p.year if p else "?"
            print(f"  fwd={score}  {year}  {title}  [{doi}]")


if __name__ == "__main__":
    main()
