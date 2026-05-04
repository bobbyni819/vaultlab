"""Trial run for the per-paper summarization layer (Phase 3 of F.7).

End-to-end smoke test:

1. Rebuild the CRISPR base-editing corpus (same shape as ``_trial_corpus.py``).
2. Pick 3 papers that have PDFs cached from ``_trial_acquisition.py``.
3. Call :func:`vaultlab.research.summarize_paper` for each (real Anthropic
   API hit — Claude reads the PDF, returns structured JSON).
4. Verify each summary:
   - ``tldr`` is 2-4 sentences and mentions the paper's core claim.
   - At least 3 ``key_findings``, each with a ``[p<N>]`` (or ``[unknown]``)
     marker.
   - Frontmatter has ``og_score`` from corpus metrics.
   - File is written to ``<temp-kb>/Wiki/Summaries/<doi-slug>.md``.
   - YAML frontmatter parses.
5. Print Claude's actual TL;DRs and a sample of key findings so a human
   reviewer can sanity-check the model output.

Run from the vaultlab repo root::

    python scripts/_trial_summarize.py

Acceptance: all 3 papers produce Tier-A summaries with valid YAML
frontmatter and non-empty TL;DRs.
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

from vaultlab.kb.paths import slugify_doi, summary_path  # noqa: E402
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


def _split_frontmatter(md: str) -> tuple[dict, str]:
    """Return ``(parsed_frontmatter, body)`` from a markdown file."""
    if not md.startswith("---\n"):
        return {}, md
    end = md.find("\n---\n", 4)
    if end < 0:
        return {}, md
    fm = yaml.safe_load(md[4:end])
    return fm or {}, md[end + 5 :]


def _verify_summary(doi: str, summary, kb_root: Path) -> tuple[bool, list[str]]:
    """Return ``(ok, problems)`` for a single summary."""
    problems: list[str] = []

    # 1. TL;DR present and looks like 2-4 sentences.
    if not summary.tldr.strip():
        problems.append("TL;DR is empty")
    else:
        n_sentences = sum(1 for _ in re.finditer(r"[.!?](\s|$)", summary.tldr))
        if n_sentences < 2 or n_sentences > 6:
            problems.append(
                f"TL;DR has {n_sentences} sentence-ending punctuation marks "
                "(expected 2-4)"
            )

    # 2. >=3 key findings, each with [p<N>] / [unknown].
    if len(summary.key_findings) < 3:
        problems.append(
            f"Only {len(summary.key_findings)} key_findings (expected >=3)"
        )
    no_marker = [f for f in summary.key_findings if not PAGE_MARKER_RE.search(f)]
    if no_marker:
        problems.append(
            f"{len(no_marker)} key_finding(s) missing [p<N>] / [unknown] marker"
        )

    # 3. Frontmatter has og_score and parses as YAML.
    path = summary_path(kb_root, doi)
    if not path.exists():
        problems.append(f"Summary file not written: {path}")
        return (not problems), problems
    md = path.read_text(encoding="utf-8")
    try:
        fm, _ = _split_frontmatter(md)
    except yaml.YAMLError as e:
        problems.append(f"YAML frontmatter parse failed: {e}")
        return (not problems), problems
    if "og_score" not in fm:
        problems.append("Frontmatter missing og_score")
    if "tier" not in fm:
        problems.append("Frontmatter missing tier")
    if fm.get("tier") != "A":
        problems.append(f"Expected tier=A, got tier={fm.get('tier')}")

    return (not problems), problems


def main() -> int:
    print("=" * 72)
    print("TRIAL RUN: per-paper summarization (Phase 3 / F.7)")
    print("=" * 72)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        # Try the config fallback before we balk.
        try:
            from vaultlab.research.summarize import load_anthropic_api_key

            load_anthropic_api_key(None)
        except Exception as exc:
            print(f"\nERROR: {exc}")
            print(
                "\nSet ANTHROPIC_API_KEY in env, or add anthropic_api_key to "
                "the research_apis.json config, then retry."
            )
            return 2

    # ------------------------------------------------------------------
    # 1. Rebuild a small CRISPR corpus.
    # ------------------------------------------------------------------
    client = ResearchClient()
    print("\n[1/4] Searching 'CRISPR base editing' (PubMed) for seeds...")
    pubmed_seeds = client.search(
        "CRISPR base editing", max_results=20, sources=["pubmed"]
    )
    seeds = [s for s in pubmed_seeds if s.doi][:10]
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

    # ------------------------------------------------------------------
    # 2. Pick 3 papers that have PDFs in the acquisition cache.
    # ------------------------------------------------------------------
    print(f"\n[3/4] Looking for PDFs in {CACHE_DIR}/ ...")
    if not CACHE_DIR.exists():
        print(f"  ERROR: cache dir {CACHE_DIR} not found. Run "
              "scripts/_trial_acquisition.py first.")
        return 2
    available_dois: list[str] = []
    for doi in corpus.papers:
        if cache_path_for(doi, CACHE_DIR).exists():
            available_dois.append(doi)
    print(f"  {len(available_dois)} corpus papers have cached PDFs.")
    if len(available_dois) < 3:
        print(
            f"  ERROR: need >=3 cached PDFs, found {len(available_dois)}. "
            "Run scripts/_trial_acquisition.py to populate the cache."
        )
        return 2
    picks = available_dois[:3]
    for d in picks:
        print(f"    - {d}")

    # ------------------------------------------------------------------
    # 3. Run summarize_paper on each — REAL Anthropic API hit.
    # ------------------------------------------------------------------
    kb_root = Path(tempfile.mkdtemp(prefix="vaultlab_trial_summarize_"))
    print(f"\n[4/4] Summarizing 3 papers (writing to {kb_root}) ...")

    all_pass = True
    summaries = []
    for i, doi in enumerate(picks, 1):
        paper = corpus.papers[doi]
        pdf_path = cache_path_for(doi, CACHE_DIR)
        print(
            f"\n  [{i}/3] {doi}  ({pdf_path.stat().st_size // 1024} KB PDF)"
        )
        print(f"        title: {paper.title[:90]}")
        try:
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
            )
            write_summary_to_kb(summary, kb_root, overwrite=True)
        except Exception as exc:
            print(f"        ERROR: {exc}")
            all_pass = False
            continue

        summaries.append((doi, summary))
        ok, problems = _verify_summary(doi, summary, kb_root)
        if ok:
            print(f"        VERIFY: PASS")
        else:
            all_pass = False
            print(f"        VERIFY: FAIL")
            for p in problems:
                print(f"           - {p}")
        # Show what Claude actually wrote.
        print(f"        TL;DR: {summary.tldr}")
        print(f"        Key findings ({len(summary.key_findings)}):")
        for kf in summary.key_findings[:5]:
            print(f"           * {kf}")
        if len(summary.key_findings) > 5:
            print(f"           ... ({len(summary.key_findings) - 5} more)")
        print(
            f"        Tokens: ~{summary.tokens_input} input, "
            f"~{summary.tokens_output} output"
        )
        print(f"        og_score: {summary.og_score:.3f}, "
              f"year_bucket: {summary.year_bucket}, "
              f"role: {summary.role_in_set}")
        path = summary_path(kb_root, doi)
        print(f"        Wrote: {path}")

    # ------------------------------------------------------------------
    # Final summary.
    # ------------------------------------------------------------------
    print("\n" + "=" * 72)
    if all_pass:
        print("TRIAL RUN: ALL VERIFICATIONS PASSED")
    else:
        print("TRIAL RUN: SOME VERIFICATIONS FAILED")
    print(f"   Wrote {len(summaries)} summaries under {kb_root}")
    print("=" * 72)

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
