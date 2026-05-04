"""Trial run for the figure acquisition layer (PMC OA + Springer API).

Pulls a small CRISPR-base-editing seed pool, looks up which DOIs have a
PMCID, then calls :func:`vaultlab.figures.acquire_figures` against the
top ~5.  Reports per-paper outcomes plus one full caption to demonstrate
that the NXML parsing actually works end-to-end on a live response.

Run from the vaultlab repo root::

    python scripts/_trial_figure_acquisition.py
"""

from __future__ import annotations

import logging
import os
import sys
import time
from collections import Counter
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except Exception:
    pass

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

from vaultlab.figures import acquire_figures  # noqa: E402
from vaultlab.research import ResearchClient  # noqa: E402


def _truncate(text: str, n: int = 220) -> str:
    text = (text or "").replace("\n", " ").strip()
    return text if len(text) <= n else text[: n - 3] + "..."


def main() -> int:
    print("=" * 72)
    print("TRIAL RUN: figure acquisition (CRISPR base editing seeds)")
    print("=" * 72)

    cache_dir = Path("scripts/_trial_figure_acquisition_cache")
    cache_dir.mkdir(parents=True, exist_ok=True)

    client = ResearchClient()
    print("\n[1/3] Searching 'CRISPR base editing' (PubMed-biased pool)...")
    pubmed_seeds = client.search(
        "CRISPR base editing", max_results=20, sources=["pubmed"]
    )
    seen: set[str] = set()
    candidates = []
    for s in pubmed_seeds:
        if s.doi and s.doi.lower() not in seen:
            seen.add(s.doi.lower())
            candidates.append(s)
    print(f"  Got {len(candidates)} unique DOIs from PubMed.")

    # Take the first 5 papers — Phase 1 verification on real data.
    sample = candidates[:5]
    print(f"\n[2/3] Acquiring figures for {len(sample)} papers...")
    results = []
    t0 = time.time()
    for i, paper in enumerate(sample, 1):
        print(f"  [{i}/{len(sample)}] {paper.doi}")
        sys.stdout.flush()
        res = acquire_figures(paper.doi, cache_dir=cache_dir)
        results.append((paper, res))
        n_fig = len(res.figures)
        size_kb = sum(f.file_path.stat().st_size for f in res.figures) / 1024
        print(
            f"      -> source={res.source}  figures={n_fig}  "
            f"total_kb={size_kb:.0f}"
        )
        if res.error:
            print(f"      err: {res.error}")
    elapsed = time.time() - t0

    by_source = Counter(r.source for _, r in results)
    n_with_figures = sum(1 for _, r in results if r.figures)

    print("\n[3/3] Summary")
    print(f"  Wall time:          {elapsed:.1f}s")
    print(f"  Papers attempted:   {len(results)}")
    print(f"  With figures:       {n_with_figures}")
    print("  By source:")
    for src, n in by_source.most_common():
        print(f"    {src:<14} {n}")

    # Print one sample caption to prove NXML parsing works.
    sample_with_caption = next(
        (
            (paper, fig)
            for paper, res in results
            for fig in res.figures
            if fig.caption
        ),
        None,
    )
    if sample_with_caption is not None:
        paper, fig = sample_with_caption
        print("\n  Sample caption (proves NXML parsing reached the figures):")
        print(f"    DOI:      {paper.doi}")
        print(f"    fig_id:   {fig.figure_id}")
        print(f"    label:    {fig.label}")
        print(f"    panels:   {fig.panels}")
        print(f"    caption:  {_truncate(fig.caption, 280)}")
    else:
        print("\n  (no figure with a non-empty caption was acquired)")

    # Mark unavailable papers so the caller can skip them in figure-making.
    print("\n  figure_extraction status per paper:")
    for paper, res in results:
        status = "ok" if res.figures else "unavailable"
        print(f"    {status:<12} {paper.doi}")

    print("\n" + "=" * 72)
    if n_with_figures >= 1:
        print(f"PASS: {n_with_figures}/{len(results)} papers yielded real figures.")
        print("=" * 72)
        return 0
    else:
        print("FAIL: no figures pulled — investigate before claiming done.")
        print("=" * 72)
        return 1


if __name__ == "__main__":
    sys.exit(main())
