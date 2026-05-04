"""Phase 1D — prepare the picker task on the CODEX corpus.

Builds the corpus (Phase 1A + 1B inline), then calls prepare_picker_task
with the auto-cap kicking in (corpus > 500 → cap at 200). Prints the
prompt's overall shape (size, # candidates, # with abstracts) and saves
the full task to disk for the LLM-driven step.

Designed so the LLM step (responding with picker JSON) can be done
either in this conversation, in a fresh CC session, or by piping the
saved task to a different mechanism.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from vaultlab.research import ResearchClient
from vaultlab.research.query_expansion import expand_topic_deterministic
from vaultlab.research.corpus import build_corpus_from_seeds, expand_corpus_forward
from vaultlab.research.graph_metrics import compute_metrics
from vaultlab.research.picker import prepare_picker_task


TOPIC = (
    "CODEX multiplexed imaging — methods and applications "
    "across tissue types"
)
MAX_SEEDS = 30
KB_ROOT = Path("G:/My Drive/Knowledge/vaultlab")


def main() -> None:
    print(f"Topic: {TOPIC}")
    print()

    # 1A: search
    queries = expand_topic_deterministic(TOPIC, target_n=5)
    client = ResearchClient()
    print("Phase 1A: search...")
    t0 = time.time()
    papers, _ = client.search_with_trace(
        TOPIC, max_results=50, queries=queries
    )
    seeds = papers[:MAX_SEEDS]
    print(f"  {len(papers)} unique papers, top {len(seeds)} seeds ({time.time()-t0:.1f}s)")
    print()

    # 1B: corpus build
    print("Phase 1B: corpus + forward expansion...")
    t0 = time.time()
    corpus = build_corpus_from_seeds(seeds, topic=TOPIC)
    n_after_backward = corpus.n_papers
    s2 = client._semantic
    if s2 and hasattr(s2, "get_citations"):
        def _fetch_forward(doi, limit):
            return s2.get_citations(doi, limit=limit)
        try:
            expand_corpus_forward(
                corpus,
                fetch_citations=_fetch_forward,
                seed_only=True,
                max_per_paper=50,
            )
        except Exception as e:
            print(f"  forward expansion failed: {e}")
    compute_metrics(corpus)
    print(
        f"  corpus: {corpus.n_papers} papers "
        f"(backward {n_after_backward}, forward +{corpus.n_papers - n_after_backward})  "
        f"({time.time()-t0:.1f}s)"
    )
    print()

    # 1D: prepare picker task (auto-cap engages because corpus > 500)
    print("Phase 1D: prepare picker task...")
    t0 = time.time()
    task = prepare_picker_task(
        topic=TOPIC,
        corpus=corpus,
        target_n=10,
        # coarse_n=None → auto-cap kicks in (corpus has 2700+ papers)
        kb_root=KB_ROOT,
        pdf_cache_dir=KB_ROOT / "Sources" / "Papers",
    )
    print(f"  --> task built ({time.time()-t0:.1f}s)")
    print(f"  --> {len(task.candidates)} candidates in pool")
    print()

    # Stats on candidates
    has_abstract = sum(
        1 for c in task.candidates if c.abstract and c.abstract != "[no abstract]"
    )
    has_pdf = sum(1 for c in task.candidates if c.has_pdf)
    seed_dois = {s.doi.lower() for s in corpus.seeds if s.doi}
    n_seeds_in_pool = sum(1 for c in task.candidates if c.doi.lower() in seed_dois)
    print(f"  candidates with real abstracts: {has_abstract} / {len(task.candidates)}")
    print(f"  candidates with cached PDFs:    {has_pdf} / {len(task.candidates)}")
    print(f"  seeds in pool:                  {n_seeds_in_pool} / {MAX_SEEDS}")
    print()

    # Year distribution of the candidates
    year_counts: dict[int, int] = {}
    for c in task.candidates:
        if c.year:
            year_counts[c.year] = year_counts.get(c.year, 0) + 1
    print("Candidate-pool year distribution (top 10 most-recent):")
    for year in sorted(year_counts.keys(), reverse=True)[:10]:
        bar = "#" * min(40, year_counts[year])
        print(f"  {year}: {year_counts[year]:>4d} {bar}")
    print()

    # Prompt size
    prompt_len = len(task.prompt)
    rough_tokens = prompt_len // 4  # crude estimate
    print(f"Picker prompt size: {prompt_len:,} chars (~{rough_tokens:,} tokens)")
    print()

    # Save the task to disk for the LLM-driven step
    out_dir = Path("G:/My Drive/Knowledge/vaultlab/Output/_phase1d-codex-2026-05-01")
    out_dir.mkdir(exist_ok=True, parents=True)
    (out_dir / "picker-prompt.txt").write_text(task.prompt, encoding="utf-8")
    (out_dir / "picker-system-prompt.txt").write_text(
        task.system_prompt, encoding="utf-8"
    )
    (out_dir / "picker-response-schema.json").write_text(
        json.dumps(task.response_schema, indent=2), encoding="utf-8"
    )
    candidate_summary = [
        {
            "doi": c.doi,
            "title": c.title,
            "year": c.year,
            "og_score": c.og_score,
            "forward_influence": c.forward_influence,
            "has_pdf": c.has_pdf,
            "has_real_abstract": c.abstract not in ("", "[no abstract]"),
        }
        for c in task.candidates
    ]
    (out_dir / "candidates.json").write_text(
        json.dumps(candidate_summary, indent=2), encoding="utf-8"
    )
    print(f"Saved picker prompt + candidate summary to {out_dir}")


if __name__ == "__main__":
    main()
