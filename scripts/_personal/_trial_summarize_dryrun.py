"""Dry-run / pipeline-shape verification for ``_trial_summarize.py``.

This is the same pipeline as ``_trial_summarize.py`` but with a stub
LLM that returns deterministic output. It exists because the Claude Code
agent subprocess that ran the original implementation did not have an
``ANTHROPIC_API_KEY`` available, so the live-API trial could not be
executed in-band.

What this script proves:

* The real cached PDFs (from ``_trial_acquisition.py``) are picked up
  by ``cache_path_for`` correctly.
* Corpus metrics flow into the summary's frontmatter (og_score,
  forward_influence, year_bucket, role_in_set).
* ``write_summary_to_kb`` writes to ``Wiki/Summaries/<slug>.md`` via
  the canonical paths helper.
* The rendered markdown's YAML frontmatter parses.
* The connections wikilinks use slugified DOIs.

When ``ANTHROPIC_API_KEY`` is available, run ``_trial_summarize.py``
instead — it does the same thing but with the real Claude call.

Usage::

    python scripts/_trial_summarize_dryrun.py
"""

from __future__ import annotations

import logging
import os
import re
import sys
import tempfile
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except Exception:
    pass

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

import yaml  # noqa: E402

from vaultlab.kb.paths import summary_path  # noqa: E402
from vaultlab.research import (  # noqa: E402
    ResearchClient,
    build_corpus_from_seeds,
    compute_metrics,
    get_references_via_crossref,
    summarize_paper,
    write_summary_to_kb,
)
from vaultlab.research.acquisition import cache_path_for  # noqa: E402

CACHE_DIR = Path("scripts/_trial_acquisition_cache")
PAGE_MARKER_RE = re.compile(r"\[(p\d+|unknown)\]")


def _stub_llm():
    """Return a deterministic LLM caller that mimics Claude's response shape."""

    def _caller(*, pdf_bytes, prompt, api_key, model, **_):
        # Sanity: prompt must contain identifying metadata.
        assert "PAPER TO SUMMARIZE" in prompt
        assert "OUTPUT FORMAT" in prompt
        # PDF bytes must look like a PDF.
        assert pdf_bytes[:5] == b"%PDF-"
        # Echo back a reasonable structured response.
        return (
            {
                "tldr": (
                    "[STUB LLM] This paper presents results in CRISPR base editing. "
                    "It demonstrates editing of nucleotides at target loci. "
                    "The work advances the field of precision genome editing."
                ),
                "why_it_matters": [
                    "[STUB LLM] Advances base-editor specificity",
                    "[STUB LLM] Reduces off-target activity",
                ],
                "methods_summary": (
                    "[STUB LLM] Authors use a fusion construct of dCas9 and a "
                    "deaminase, transfect mammalian cells, and measure editing "
                    "efficiency by deep sequencing."
                ),
                "key_findings": [
                    "[STUB LLM] Editing efficiency reaches 30%+ at the target locus [p3]",
                    "[STUB LLM] Off-target rate is reduced relative to baseline [p5]",
                    "[STUB LLM] The construct is active in primary cells [p7]",
                ],
                "extracted_references": [],
            },
            14000,
            900,
        )

    return _caller


def _split_frontmatter(md: str) -> tuple[dict, str]:
    if not md.startswith("---\n"):
        return {}, md
    end = md.find("\n---\n", 4)
    if end < 0:
        return {}, md
    fm = yaml.safe_load(md[4:end])
    return fm or {}, md[end + 5 :]


def main() -> int:
    print("=" * 72)
    print("DRY-RUN: per-paper summarization pipeline (stub LLM)")
    print("=" * 72)

    client = ResearchClient()
    print("\n[1/4] Searching 'CRISPR base editing' (PubMed)...")
    seeds = [
        s
        for s in client.search(
            "CRISPR base editing", max_results=20, sources=["pubmed"]
        )
        if s.doi
    ][:10]
    print(f"  Got {len(seeds)} seeds with DOIs.")

    print("\n[2/4] Building corpus + metrics...")
    corpus = build_corpus_from_seeds(
        seeds,
        topic="CRISPR base editing",
        fetch_refs=get_references_via_crossref,
    )
    compute_metrics(corpus)
    print(
        f"  Corpus: {corpus.n_papers} papers, {corpus.n_edges} edges, "
        f"{len(corpus.metrics.og_score)} papers with og_score."
    )

    print(f"\n[3/4] Looking for cached PDFs in {CACHE_DIR}/...")
    available = [d for d in corpus.papers if cache_path_for(d, CACHE_DIR).exists()]
    print(f"  {len(available)} corpus papers have cached PDFs.")
    if len(available) < 3:
        print(
            f"  ERROR: need >=3 cached PDFs, found {len(available)}. "
            "Run scripts/_trial_acquisition.py first."
        )
        return 2
    picks = available[:3]
    for d in picks:
        print(f"    - {d}")

    kb_root = Path(tempfile.mkdtemp(prefix="vaultlab_dryrun_summarize_"))
    print(f"\n[4/4] Summarizing 3 papers (stub LLM, kb_root={kb_root})...")

    all_pass = True
    for i, doi in enumerate(picks, 1):
        paper = corpus.papers[doi]
        pdf_path = cache_path_for(doi, CACHE_DIR)
        print(f"\n  [{i}/3] {doi}")
        print(f"        title: {paper.title[:90]}")
        summary = summarize_paper(
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
            corpus_metrics=corpus.metrics,
            corpus=corpus,
            acquisition_source="cache",
            _llm=_stub_llm(),
        )
        write_summary_to_kb(summary, kb_root, overwrite=True)
        path = summary_path(kb_root, doi)
        print(f"        wrote: {path}")

        # Verify.
        problems: list[str] = []
        if summary.tier != "A":
            problems.append(f"expected tier=A, got {summary.tier}")
        if not summary.tldr:
            problems.append("empty tldr")
        if len(summary.key_findings) < 3:
            problems.append(f"too few key_findings ({len(summary.key_findings)})")
        if not all(PAGE_MARKER_RE.search(f) for f in summary.key_findings):
            problems.append("missing page markers")
        md = path.read_text(encoding="utf-8")
        try:
            fm, _ = _split_frontmatter(md)
        except yaml.YAMLError as e:
            problems.append(f"YAML parse failed: {e}")
            fm = {}
        if "og_score" not in fm:
            problems.append("frontmatter missing og_score")
        if "tier" not in fm:
            problems.append("frontmatter missing tier")
        for slug in (
            summary.connections_references + summary.connections_cited_by_in_set
        ):
            if "/" in slug:
                problems.append(f"unslugified connection: {slug}")
        if problems:
            all_pass = False
            print("        VERIFY: FAIL")
            for p in problems:
                print(f"          - {p}")
        else:
            print("        VERIFY: PASS")
        print(f"        TL;DR: {summary.tldr}")
        print(
            f"        og_score={summary.og_score:.3f}, "
            f"forward_influence={summary.forward_influence}, "
            f"year_bucket={summary.year_bucket}, role={summary.role_in_set}"
        )
        print(f"        Key findings ({len(summary.key_findings)}):")
        for kf in summary.key_findings:
            print(f"           * {kf}")
        if summary.connections_references:
            print(
                f"        connections_references: "
                f"{summary.connections_references[:3]}"
            )
        if summary.connections_cited_by_in_set:
            print(
                f"        connections_cited_by_in_set: "
                f"{summary.connections_cited_by_in_set[:3]}"
            )

    print("\n" + "=" * 72)
    if all_pass:
        print("DRY-RUN: ALL VERIFICATIONS PASSED")
    else:
        print("DRY-RUN: SOME VERIFICATIONS FAILED")
    print("=" * 72)
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
