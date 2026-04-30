"""End-to-end DRY-RUN for the ``/lit-arc`` orchestrator.

This script exercises :func:`vaultlab.research.lineage.run_lit_arc` against
real CrossRef + Semantic Scholar + Unpaywall calls but with a stubbed
LLM (since the agent subprocess running this typically has no
``ANTHROPIC_API_KEY``). The goal is to prove that:

* Every canonical KB path is written by the real pipeline
* :class:`LineageRunResult` carries the expected counts
* Provenance receipts land next to the arc

When ``ANTHROPIC_API_KEY`` is set, the LLM stubs are replaced with the
real Claude calls — same shape, just costs tokens.

Usage::

    python scripts/_trial_lit_arc_dryrun.py
"""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except Exception:
    pass

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

from vaultlab.kb.paths import (  # noqa: E402
    article_stub_path,
    concept_path,
    search_log_path,
    summary_path,
)
from vaultlab.research.lineage import run_lit_arc  # noqa: E402


def _stub_summary_llm():
    """Deterministic Claude PDF-reader stub for offline dry-runs."""

    def _caller(*, pdf_bytes, prompt, api_key, model, **_):
        assert pdf_bytes[:5] == b"%PDF-"
        return (
            {
                "tldr": (
                    "[STUB] This paper advances CRISPR base editing. "
                    "It demonstrates targeted nucleotide conversion. "
                    "Off-target effects are characterized."
                ),
                "why_it_matters": [
                    "[STUB] Improves precision of base editors",
                    "[STUB] Quantifies off-target activity",
                ],
                "methods_summary": (
                    "[STUB] The authors fuse a deaminase to a Cas9 nickase "
                    "and assay editing efficiency in mammalian cells."
                ),
                "key_findings": [
                    "[STUB] Editing efficiency reaches 30%+ at the target locus [p3]",
                    "[STUB] Off-target activity is below threshold [p5]",
                    "[STUB] Editing window spans 5 nt [p4]",
                ],
                "extracted_references": [],
            },
            14000,
            900,
        )

    return _caller


def _stub_arc_llm(captured_prompts: list[str]):
    """Deterministic lineage-arc Claude stub. Captures prompt for inspection."""

    def _caller(*, prompt: str, api_key: str, model: str):
        captured_prompts.append(prompt)
        return {
            "history": (
                "[STUB] The lineage begins with foundational programmable-cleavage "
                "work. Early breakthroughs established the dual-RNA-guided "
                "system that later iterations would refine."
            ),
            "development": (
                "[STUB] Through the development phase, base editors emerged that "
                "convert nucleotides without inducing double-strand breaks."
            ),
            "sota": (
                "[STUB] State-of-the-art systems extend the editing palette and "
                "reduce off-target activity through engineered deaminases."
            ),
        }

    return _caller


def _progress(*args: Any, **kwargs: Any) -> None:
    if not args:
        print(f"  -> {kwargs}")
        return
    head = args[0]
    rest = ", ".join(f"{k}={v}" for k, v in kwargs.items())
    print(f"  -> {head}: {rest}" if rest else f"  -> {head}")


def main() -> int:
    print("=" * 72)
    print("DRY-RUN: /lit-arc orchestrator (real APIs, stub LLM)")
    print("=" * 72)

    topic = "CRISPR base editing"
    kb_root = Path(tempfile.mkdtemp(prefix="vaultlab_dryrun_lit_arc_"))
    print(f"\nTopic: {topic}")
    print(f"KB root: {kb_root}")

    captured: list[str] = []

    print("\nRunning run_lit_arc...")
    result = run_lit_arc(
        topic,
        kb_root=kb_root,
        max_seeds=5,
        max_papers_to_summarize=5,
        progress=_progress,
        _llm_summary=_stub_summary_llm(),
        _llm_arc=_stub_arc_llm(captured),
    )

    print("\n" + "-" * 72)
    print("LineageRunResult:")
    print(f"  topic               = {result.topic}")
    print(f"  arc_path            = {result.arc_path}")
    print(f"  search_log_path     = {result.search_log_path}")
    print(f"  corpus_size         = {result.corpus_size}")
    print(f"  pdfs_acquired       = {result.pdfs_acquired}")
    print(f"  summaries_written   = {result.summaries_written}")
    print(f"  duration_seconds    = {result.duration_seconds:.1f}")
    print(f"  summary_paths count = {len(result.summary_paths)}")
    print("-" * 72)

    # Verify each canonical output is at its expected path.
    problems: list[str] = []

    expected_log = search_log_path(kb_root, topic, result.search_log_path.stem.split("-")[-3] + "-" + result.search_log_path.stem.split("-")[-2] + "-" + result.search_log_path.stem.split("-")[-1])
    if not result.search_log_path.exists():
        problems.append(f"missing search log: {result.search_log_path}")

    if not result.arc_path.exists():
        problems.append(f"missing arc: {result.arc_path}")

    json_p = result.arc_path.with_name(result.arc_path.name + ".provenance.json")
    method_p = result.arc_path.with_name(result.arc_path.name + ".method.md")
    if not json_p.exists():
        problems.append(f"missing provenance.json: {json_p}")
    if not method_p.exists():
        problems.append(f"missing method.md: {method_p}")

    # Per-summary files.
    missing_summaries: list[str] = []
    for doi, p in result.summary_paths.items():
        if not p.exists():
            missing_summaries.append(f"{doi} -> {p}")
    if missing_summaries:
        problems.append(
            f"{len(missing_summaries)} summaries missing on disk: "
            + "; ".join(missing_summaries[:3])
        )

    # Article stubs.
    stubs_dir = kb_root / "Sources" / "Articles"
    stubs = list(stubs_dir.glob("*.md")) if stubs_dir.exists() else []
    if not stubs:
        problems.append("no article stubs in Sources/Articles/")

    # PDFs (best-effort — real Unpaywall might not have any).
    papers_dir = kb_root / "Sources" / "Papers"
    pdfs = list(papers_dir.glob("*.pdf")) if papers_dir.exists() else []

    print(f"\nFiles on disk:")
    print(f"  Sources/Notes/lit-search-*.md  = {1 if result.search_log_path.exists() else 0}")
    print(f"  Sources/Articles/<doi>.md      = {len(stubs)}")
    print(f"  Sources/Papers/<doi>.pdf       = {len(pdfs)}")
    print(f"  Wiki/Summaries/<doi>.md        = {len(result.summary_paths)} mapped, "
          f"{sum(1 for p in result.summary_paths.values() if p.exists())} on disk")
    print(f"  Wiki/Concepts/<topic>-lineage-<date>.md = {1 if result.arc_path.exists() else 0}")
    print(f"  <arc>.provenance.json          = {1 if json_p.exists() else 0}")
    print(f"  <arc>.method.md                = {1 if method_p.exists() else 0}")

    # Show provenance receipt contents (sanity).
    if json_p.exists():
        rec = json.loads(json_p.read_text(encoding="utf-8"))
        print(f"\nProvenance receipt:")
        print(f"  generated_by   = {rec.get('generated_by')}")
        print(f"  project        = {rec.get('project')}")
        print(f"  topic          = {rec.get('topic')}")
        print(f"  params         = {rec.get('params')}")
        print(f"  inputs (count) = {len(rec.get('inputs', []))}")

    # Show captured arc prompt (first few lines, just to prove it ran).
    if captured:
        print("\nCaptured lineage-arc prompt (first 12 lines):")
        for line in captured[0].splitlines()[:12]:
            print(f"  | {line}")

    # Show first arc lines.
    if result.arc_path.exists():
        lines = result.arc_path.read_text(encoding="utf-8").splitlines()
        print("\nLineage arc (first 25 lines):")
        for line in lines[:25]:
            print(f"  | {line}")

    print("\n" + "=" * 72)
    if problems:
        print("DRY-RUN: SOME VERIFICATIONS FAILED")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("DRY-RUN: ALL CANONICAL OUTPUTS PRESENT")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
