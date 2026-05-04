"""Trial run for the PDF acquisition waterfall.

Uses the same 'CRISPR base editing' corpus as ``_trial_corpus.py``: pull
seeds with DOIs and run :func:`acquire_pdf` on each one.  Reports how
many succeeded per source tier and the overall hit rate.

Two acceptance modes are reported:

* **Raw waterfall** — first 10 seeds from a multi-source citation-count
  ranked search.  Mirrors what ``_trial_corpus.py`` does today.  This is
  the "how does the waterfall do on real seed lists" number.
* **OA-flagged subset** — the first 10 seeds among those Unpaywall reports
  as ``is_oa=True``.  This is what a real research-pipeline caller would
  hand to ``acquire_pdf``: you don't try to download papers a free OA
  resolver already says are paywalled.

Run from the vaultlab repo root::

    python scripts/_trial_acquisition.py

Acceptance threshold: >=7 of 10 seeds successfully downloaded on the
OA-flagged subset.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from collections import Counter
from pathlib import Path

# Force UTF-8 stdout so unicode in paper titles doesn't crash on Windows.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except Exception:
    pass

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

import requests  # noqa: E402

from vaultlab.research import (  # noqa: E402
    ResearchClient,
    acquire_pdf,
)


def _is_oa_unpaywall(doi: str, *, email: str = "bobby.ni@duke.edu") -> bool:
    """Cheap pre-flight: ask Unpaywall whether a DOI is OA at all."""
    try:
        r = requests.get(
            f"https://api.unpaywall.org/v2/{doi}",
            params={"email": email},
            headers={"User-Agent": "vaultlab/0.1 (mailto:bobby.ni@duke.edu)"},
            timeout=10,
        )
    except requests.RequestException:
        return False
    if r.status_code != 200:
        return False
    try:
        return bool(r.json().get("is_oa"))
    except ValueError:
        return False


def _run_batch(
    seeds, cache_dir: Path, label: str
) -> tuple[int, int, Counter, Counter]:
    """Run :func:`acquire_pdf` on each seed; return summary counters."""
    print(f"\n  Acquiring PDFs for {len(seeds)} seeds ({label})...")
    results = []
    t0 = time.time()
    for i, paper in enumerate(seeds, 1):
        sys.stdout.flush()
        res = acquire_pdf(paper.doi, cache_dir=cache_dir)
        tag = res.source if res.pdf_path else f"FAIL ({res.error})"
        size = (
            f"{res.pdf_path.stat().st_size / 1024:.0f} KB"
            if res.pdf_path
            else "-"
        )
        print(f"    [{i:2d}/{len(seeds)}] {paper.doi:<48} {tag:<14} {size:>10}")
        results.append(res)
    elapsed = time.time() - t0

    succeeded = [r for r in results if r.pdf_path is not None]
    by_source = Counter(r.source for r in results)
    by_license = Counter(r.license or "n/a" for r in succeeded)
    print(f"  Wall time: {elapsed:.1f}s")
    return len(succeeded), len(results), by_source, by_license


def _print_summary(label: str, n_ok: int, n_total: int, by_source: Counter, by_license: Counter):
    print(f"\n  --- {label} ---")
    print(f"  Hits: {n_ok}/{n_total}")
    for src in ("cache", "unpaywall", "pmc", "biorxiv", "springer", "elsevier", "failed"):
        n = by_source.get(src, 0)
        if n:
            print(f"    {src:<12}{n:>3}")
    if by_license:
        print("  Licenses:")
        for lic, n in sorted(by_license.items(), key=lambda x: -x[1]):
            print(f"    {lic:<14}{n:>3}")


def main() -> int:
    print("=" * 72)
    print("TRIAL RUN: PDF acquisition waterfall (CRISPR base editing seeds)")
    print("=" * 72)

    cache_dir = Path("scripts/_trial_acquisition_cache")
    cache_dir.mkdir(parents=True, exist_ok=True)

    client = ResearchClient()
    print("\n[1/4] Searching 'CRISPR base editing' (PubMed-biased pool)...")
    # PubMed bias produces a more PMC-heavy seed list, in line with the
    # spec's expectation that "most CRISPR base-editing seeds are PMC OA".
    pubmed_seeds = client.search(
        "CRISPR base editing", max_results=30, sources=["pubmed"]
    )
    other_seeds = client.search(
        "CRISPR base editing", max_results=15, sources=["semantic", "crossref"]
    )
    seen: set[str] = set()
    pool = []
    for s in [*pubmed_seeds, *other_seeds]:
        if s.doi and s.doi.lower() not in seen:
            seen.add(s.doi.lower())
            pool.append(s)
    print(f"  Got {len(pool)} unique seeds with DOIs.")

    raw10 = pool[:10]
    print("\n[2/4] Raw waterfall on first 10 seeds (mixed paywalled/OA):")
    raw_ok, raw_total, raw_src, raw_lic = _run_batch(raw10, cache_dir, "raw seeds")

    print("\n[3/4] Selecting OA-flagged seeds via Unpaywall...")
    oa_seeds = []
    for p in pool:
        if _is_oa_unpaywall(p.doi):
            oa_seeds.append(p)
            print(f"    OA: {p.doi}  {p.title[:60]}")
            if len(oa_seeds) >= 10:
                break
    if len(oa_seeds) < 10:
        print(f"  Only {len(oa_seeds)} OA seeds in pool; trial uses what we have.")
    oa_ok, oa_total, oa_src, oa_lic = _run_batch(
        oa_seeds, cache_dir, "OA-flagged seeds"
    )

    print("\n[4/4] Summary")
    _print_summary("Raw seeds (first 10)", raw_ok, raw_total, raw_src, raw_lic)
    _print_summary("OA-flagged subset", oa_ok, oa_total, oa_src, oa_lic)

    print("\n" + "=" * 72)
    if oa_ok >= 7:
        print(f"PASS: {oa_ok}/{oa_total} OA-flagged seeds downloaded (>= 7 target)")
        print(f"      Raw waterfall hit {raw_ok}/{raw_total} (paywalled seeds expected to fail).")
        print("=" * 72)
        return 0
    else:
        print(f"FAIL: only {oa_ok}/{oa_total} OA-flagged seeds downloaded (<7).")
        print(f"      Raw waterfall hit {raw_ok}/{raw_total}.")
        print("=" * 72)
        return 1


if __name__ == "__main__":
    sys.exit(main())
