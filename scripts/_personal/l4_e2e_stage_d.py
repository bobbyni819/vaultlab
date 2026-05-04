"""L4 E2E Test - Stage D: figure acquisition + deck build.

Reuses the corpus.pkl from stage A and the lineage result from stage B.
We rebuild the LineageRunResult from the on-disk arc + summaries paths
because pickling the full result is overkill.
"""

from __future__ import annotations

import json
import pickle
import time
from pathlib import Path

from vaultlab.figures.acquisition import acquire_figures_for_corpus
from vaultlab.kb.paths import concept_path, summary_path
from vaultlab.research.lineage import LineageRunResult
from vaultlab.slides import build_deck_from_lineage_result

TOPIC = "CODEX cellular neighborhoods"
KB_ROOT = Path(r"G:/My Drive/Knowledge/vaultlab")
DATE_STR = "2026-04-29"
STATE_DIR = Path(r"C:/Users/bobby/Downloads/vaultlab/scripts/_l4_state")

# 8 forced Tier-A DOIs from stage B (used to scope the figure acquisition)
TIER_A = [
    "10.1016/j.cell.2018.07.010",
    "10.1126/sciadv.add1166",
    "10.1371/journal.pcbi.1012344",
    "10.1016/j.cell.2024.04.013",
    "10.1038/nmeth.4391",
    "10.1089/cmb.2019.0340",
    "10.1007/s00281-022-00974-0",
    "10.1038/s42003-022-04032-1",
]


def main():
    started = time.time()

    # Reload corpus from stage A.
    print("[1/3] Loading corpus from stage A pickle", flush=True)
    with open(STATE_DIR / "corpus.pkl", "rb") as f:
        corpus = pickle.load(f)
    print(f"      Corpus: {corpus.n_papers} papers", flush=True)

    # Acquire figures for the corpus (limit to subset to keep runtime sane).
    # Build a minimal corpus-like object containing only the Tier-A DOIs.
    print("[2/3] Acquiring figures for Tier-A picks", flush=True)
    pdf_cache_dir = KB_ROOT / "Sources" / "Papers"

    # Build a sub-corpus dict mapping tier-A DOIs to their Paper objects.
    class _MiniCorpus:
        pass

    mc = _MiniCorpus()
    mc.papers = {d: corpus.papers[d] for d in TIER_A if d in corpus.papers}
    mc.seeds = list(mc.papers.values())
    mc.seed_dois = set(mc.papers.keys())
    print(f"      Sub-corpus: {len(mc.papers)} Tier-A papers", flush=True)

    figure_results = acquire_figures_for_corpus(
        mc,
        pdf_cache_dir,
        parallel=2,
    )

    figure_assignments: dict[str, Path] = {}
    figs_per_paper = {}
    for doi, r in figure_results.items():
        if r.source != "unavailable" and r.figures:
            figure_assignments[doi] = Path(r.figures[0].file_path)
            figs_per_paper[doi] = (r.source, len(r.figures), r.figures[0].caption[:100])

    print(f"      Papers with figures: {len(figure_assignments)}/{len(TIER_A)}", flush=True)
    for doi, (src, n, cap) in figs_per_paper.items():
        print(f"        {doi}: src={src} n={n} cap={cap!r}", flush=True)

    # Reconstruct a minimal LineageRunResult from on-disk arc + summaries.
    print("[3/3] Building deck from lineage result", flush=True)
    arc_path = concept_path(KB_ROOT, TOPIC, "lineage", DATE_STR)
    summary_paths = {doi: summary_path(KB_ROOT, doi) for doi in TIER_A}

    result = LineageRunResult(
        topic=TOPIC,
        arc_path=arc_path,
        summary_paths=summary_paths,
        search_log_path=KB_ROOT / "Sources" / "Notes" / f"lit-search-codex-cellular-neighborhoods-{DATE_STR}.md",
        corpus_size=corpus.n_papers,
        pdfs_acquired=128,
        summaries_written=len(TIER_A),
    )

    deck_path_out = build_deck_from_lineage_result(
        lineage_result=result,
        speaker="Bobby Y.X. Ni",
        affiliation="Hickey Lab @ Duke BME",
        project_slug="codex-cn-test",
        figure_assignments=figure_assignments,
        kb_root=KB_ROOT,
    )

    elapsed = time.time() - started
    print(f"\n[DONE] Stage D complete in {elapsed:.1f}s", flush=True)
    print(f"  deck_path = {deck_path_out}", flush=True)
    print(f"  exists = {deck_path_out.exists()}", flush=True)
    print(f"  size = {deck_path_out.stat().st_size if deck_path_out.exists() else 0} bytes", flush=True)

    # Persist figure acquisition summary.
    fig_dump = {
        doi: {
            "source": r.source,
            "n_figures": len(r.figures),
            "first_caption": (r.figures[0].caption if r.figures else None),
            "first_path": str(r.figures[0].file_path) if r.figures else None,
            "error": r.error,
        }
        for doi, r in figure_results.items()
    }
    (STATE_DIR / "figure_results.json").write_text(json.dumps(fig_dump, indent=2), encoding="utf-8")
    print(f"  figure_results dumped to {STATE_DIR / 'figure_results.json'}", flush=True)


if __name__ == "__main__":
    main()
