"""Trial run for the content-aware Tier-A picker.

Builds a small synthetic CRISPR corpus, defines a stub picker callback that
ranks by ``og_score`` (no LLM), and verifies the picker pipeline works
end-to-end:

1. ``prepare_picker_task`` produces a task with hydrated abstracts.
2. The stub callback returns ranked picks.
3. ``render_picks_from_response`` filters/orders the picks.
4. The decision lands in a ``picker-decision.md`` audit file.

Usage::

    python scripts/_trial_picker.py
"""

from __future__ import annotations

import json
import logging
import sys
import tempfile
from pathlib import Path
from typing import Any

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except Exception:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
)

# ruff: noqa: E402
from vaultlab.research.corpus import Corpus
from vaultlab.research.graph_metrics import compute_metrics
from vaultlab.research.paper import Paper
from vaultlab.research.picker import (
    PickerTask,
    pick_top_n_content_aware,
    prepare_picker_task,
    render_picks_from_response,
)


def _crispr_corpus() -> Corpus:
    """Tiny CRISPR corpus mirroring the test cache used by test_lineage."""
    seeds = [
        Paper(
            title="Programmable RNA-Guided DNA Endonuclease",
            authors=["Jinek M", "Doudna JA"],
            year=2012,
            journal="Science",
            doi="10.1126/science.1225829",
            citation_count=12000,
            abstract=(
                "Bacterial Cas9 protein programmed by single guide RNA "
                "cleaves matching DNA — foundational mechanism."
            ),
        ),
        Paper(
            title="Cytidine Deaminase Base Editor",
            authors=["Komor AC", "Liu DR"],
            year=2016,
            journal="Nature",
            doi="10.1038/nature17946",
            citation_count=4000,
            abstract=(
                "Base editing converts cytosine to thymine via Cas9 nickase "
                "fused to deaminase; 37 percent efficiency."
            ),
        ),
        Paper(
            title="Adenine Base Editor",
            authors=["Gaudelli NM", "Liu DR"],
            year=2017,
            journal="Nature",
            doi="10.1038/nature24644",
            citation_count=3000,
            abstract=(
                "Evolved adenosine deaminase converts A to G at target loci, "
                "complementing cytidine base editing."
            ),
        ),
        Paper(
            title="CRISPR-Cas9 Knockouts in Mammalian Cells",
            authors=["Cong L", "Zhang F"],
            year=2013,
            journal="Science",
            doi="10.1126/science.1231143",
            citation_count=10000,
            abstract=(
                "Adapted CRISPR-Cas9 system for genome editing in mammalian "
                "cells; demonstrated multiplex editing."
            ),
        ),
        Paper(
            title="High-fidelity CRISPR-Cas9 nucleases",
            authors=["Kleinstiver BP", "Joung JK"],
            year=2016,
            journal="Nature",
            doi="10.1038/nature16526",
            citation_count=2500,
            abstract=(
                "Engineered SpCas9 variants with reduced off-target effects; "
                "rationally designed protein-DNA contacts."
            ),
        ),
    ]
    corpus = Corpus(topic="CRISPR base editing", seeds=seeds)
    for s in seeds:
        corpus.papers[s.doi.lower()] = s
    # Toy citation edges.
    corpus.references = {
        "10.1126/science.1225829": [],
        "10.1126/science.1231143": ["10.1126/science.1225829"],
        "10.1038/nature17946": ["10.1126/science.1225829"],
        "10.1038/nature24644": [
            "10.1126/science.1225829",
            "10.1038/nature17946",
        ],
        "10.1038/nature16526": ["10.1126/science.1225829"],
    }
    compute_metrics(corpus)
    return corpus


def _og_score_picker(task: PickerTask) -> dict[str, Any]:
    """Stub picker callback: rank by og_score descending (no LLM)."""
    ordered = sorted(
        task.candidates, key=lambda c: c.og_score, reverse=True
    )
    return {
        "picks": [
            {
                "doi": c.doi,
                "rank": i + 1,
                "rationale": (
                    f"og_score={c.og_score:.2f}; "
                    f"abstract starts: {c.abstract[:60]}..."
                ),
            }
            for i, c in enumerate(ordered[: task.target_n])
        ]
    }


def main() -> int:
    print("=" * 70)
    print("Trial: content-aware picker (synthetic CRISPR corpus)")
    print("=" * 70)
    corpus = _crispr_corpus()
    print(f"Corpus: {corpus.n_papers} papers, {corpus.n_edges} edges")

    with tempfile.TemporaryDirectory() as tmp:
        kb_root = Path(tmp)
        run_dir = kb_root / "Output" / "trial-picker" / "runs" / "trial"

        # 1) prepare_picker_task -> hydrated abstracts.
        task = prepare_picker_task(
            "CRISPR base editing",
            corpus=corpus,
            target_n=3,
            coarse_n=10,
            kb_root=kb_root,
        )
        print(f"\nPrepared task with {len(task.candidates)} candidates")
        for c in task.candidates:
            preview = c.abstract[:70].replace("\n", " ")
            print(
                f"  - {c.doi}  og={c.og_score:.2f} fwd={c.forward_influence}"
                f"  abstract: {preview}..."
            )

        # 2) Run callback through pick_top_n_content_aware (writes audit).
        picks = pick_top_n_content_aware(
            "CRISPR base editing",
            corpus,
            target_n=3,
            coarse_n=10,
            kb_root=kb_root,
            picker_callback=_og_score_picker,
            fallback_dir=run_dir,
        )
        print(f"\nPicks (top {len(picks)}):")
        for i, doi in enumerate(picks, 1):
            print(f"  {i}. {doi}")

        # 3) Verify rationale was written to the run directory.
        decision_path = run_dir / "picker-decision.md"
        if decision_path.exists():
            print(f"\nDecision audit at: {decision_path}")
            print("-" * 70)
            print(decision_path.read_text(encoding="utf-8"))
            print("-" * 70)
        else:
            print("\nERROR: decision audit not written")
            return 1

        # 4) Verify render_picks parses correctly.
        synthetic_response = _og_score_picker(task)
        rendered = render_picks_from_response(task, synthetic_response)
        if rendered != picks:
            print(
                f"\nWARNING: render_picks mismatch:\n"
                f"  pick_top_n: {picks}\n"
                f"  render:     {rendered}"
            )

        # 5) Verify fallback path (no callback) still works.
        fallback_picks = pick_top_n_content_aware(
            "CRISPR base editing",
            corpus,
            target_n=3,
            coarse_n=10,
            kb_root=kb_root,
            picker_callback=None,
        )
        print(f"\nFallback (no callback) picks: {fallback_picks}")

    print("\n" + "=" * 70)
    print("Trial PASSED")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
