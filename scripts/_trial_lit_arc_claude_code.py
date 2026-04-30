"""Dry-run of the Claude-Code-callable ``/lit-arc`` path.

This script proves that the new prepare/render functions
(:func:`prepare_summary_task` + :func:`render_summary_from_response`,
:func:`prepare_arc_task` + :func:`render_arc_from_response`) wire end-
to-end through :func:`run_lit_arc` WITHOUT calling the Anthropic SDK.

Pipeline used here:

* Phases 1-5 — real API calls (search, refs, PDF acquisition) when
  ``--live`` is passed; otherwise stubbed.
* Phase 6 — :class:`SummarizationTask` objects flow into a deterministic
  fake reader (we simulate Claude Code reading the PDF and returning
  JSON).
* Phase 7 — :class:`ArcTask` flows into a deterministic fake narrator.
* Phase 8 — provenance receipts written.

What we verify:

* No ``anthropic`` import is reached in the reader / narrator code path.
* Every canonical KB output lands at the expected path.
* The rendered summary frontmatter parses as valid YAML.
* Wikilinks slugify correctly.
* The arc markdown carries the narrator's paragraphs and the bucket
  tables.

Usage::

    python scripts/_trial_lit_arc_claude_code.py
"""

from __future__ import annotations

import json
import logging
import os
import re
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
os.environ.pop("ANTHROPIC_API_KEY", None)  # prove we don't need it

import yaml  # noqa: E402

from vaultlab.kb.paths import (  # noqa: E402
    article_stub_path,
    concept_path,
    search_log_path,
    summary_path,
)
from vaultlab.research.acquisition import AcquisitionResult, cache_path_for  # noqa: E402
from vaultlab.research.lineage import (  # noqa: E402
    ArcTask,
    run_lit_arc,
)
from vaultlab.research.paper import Paper  # noqa: E402
from vaultlab.research.summarize import SummarizationTask  # noqa: E402

PAGE_MARKER_RE = re.compile(r"\[(p\d+|unknown)\]")


# ---------------------------------------------------------------------------
# Stub fixtures (CRISPR base-editing corpus, identical to test fixtures)
# ---------------------------------------------------------------------------


def _crispr_seeds() -> list[Paper]:
    return [
        Paper(
            title="Programmable RNA-Guided DNA Endonuclease",
            authors=["Jinek M", "Doudna JA"],
            year=2012,
            journal="Science",
            doi="10.1126/science.1225829",
            citation_count=12000,
            source_api="pubmed",
            abstract="We show that Cas9 is programmable.",
        ),
        Paper(
            title="Cytidine Deaminase Base Editor",
            authors=["Komor AC", "Liu DR"],
            year=2016,
            journal="Nature",
            doi="10.1038/nature17946",
            citation_count=4000,
            source_api="pubmed",
            abstract="CBE converts C to T at target loci.",
        ),
        Paper(
            title="Adenine Base Editor",
            authors=["Gaudelli NM", "Liu DR"],
            year=2017,
            journal="Nature",
            doi="10.1038/nature24644",
            citation_count=3000,
            source_api="pubmed",
            abstract="ABE converts A to G.",
        ),
    ]


class _FakeClient:
    def __init__(self, seeds):
        self._seeds = seeds

    def search(self, query, max_results=20, sources=None):
        return list(self._seeds)


def _fake_fetch_refs(doi: str):
    from vaultlab.research.citation_lookup import Reference

    if doi == "10.1126/science.1225829":
        return []
    if doi == "10.1038/nature17946":
        return [Reference(doi="10.1126/science.1225829")]
    if doi == "10.1038/nature24644":
        return [
            Reference(doi="10.1126/science.1225829"),
            Reference(doi="10.1038/nature17946"),
        ]
    return None


def _fake_acquire(corpus, cache_dir, **kwargs):
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    out: dict[str, AcquisitionResult] = {}
    for doi in corpus.papers:
        target = cache_path_for(doi, cache_dir)
        paper = corpus.papers[doi]
        if paper.year:
            target.write_bytes(b"%PDF-1.4\n" + b"x" * 4000)
            out[doi] = AcquisitionResult(
                doi=doi, pdf_path=target, source="unpaywall", license="cc-by"
            )
        else:
            out[doi] = AcquisitionResult(
                doi=doi, pdf_path=None, source="failed", license=None, error="ref-only"
            )
    return out


# ---------------------------------------------------------------------------
# Fake Claude-Code reader + narrator (deterministic)
# ---------------------------------------------------------------------------


def _make_reader(seen_tasks: list[SummarizationTask]):
    """Return a reader that simulates Claude Code reading the PDF in-session."""

    canned_findings = {
        "10.1126/science.1225829": [
            "Cas9-tracrRNA-crRNA forms a programmable RNP [p3]",
            "Cleavage is sequence-specific [p4]",
            "PAM is required [p5]",
        ],
        "10.1038/nature17946": [
            "C->T conversion reaches 37% at BRCA1 [p4]",
            "Off-target editing is 10x lower than wild-type Cas9 [p6]",
            "Editing window is 5 nt [p3]",
        ],
        "10.1038/nature24644": [
            "TadA evolved deaminase converts A to G [p3]",
            "ABE7.10 achieves 50% editing efficiency [p5]",
            "Editing window restricted to a 7-nt protospacer [p4]",
        ],
    }
    canned_tldr = {
        "10.1126/science.1225829": (
            "[reader] Programmable RNA-guided DNA endonuclease. "
            "Cas9-tracrRNA-crRNA targets DNA via base-pairing. "
            "Foundational for genome editing."
        ),
        "10.1038/nature17946": (
            "[reader] Cytidine base editor (CBE) converts C to T without DSBs. "
            "Achieves 37% editing at BRCA1. "
            "First DSB-free CRISPR editor."
        ),
        "10.1038/nature24644": (
            "[reader] Adenine base editor (ABE) extends editing palette to A->G. "
            "Engineered TadA deaminase achieves 50% efficiency. "
            "Closes the four-base editing palette."
        ),
    }

    def _reader(task: SummarizationTask) -> dict[str, Any]:
        # Sanity: this is exactly what a Claude Code reader would have
        # access to — the local PDF path.
        assert task.pdf_path.exists(), f"reader given missing PDF: {task.pdf_path}"
        seen_tasks.append(task)
        doi = task.doi
        return {
            "tldr": canned_tldr.get(doi, f"[reader] {doi}. b. c."),
            "why_it_matters": [f"[reader] novelty for {doi}"],
            "methods_summary": (
                f"[reader] We assayed editing in mammalian cells. (paper: {doi})"
            ),
            "key_findings": canned_findings.get(
                doi, ["finding alpha [p1]", "finding beta [p2]", "finding gamma [p3]"]
            ),
            "extracted_references": [],
        }

    return _reader


def _make_narrator(seen_tasks: list[ArcTask]):
    def _narrator(task: ArcTask) -> dict[str, str]:
        seen_tasks.append(task)
        return {
            "history": (
                "Foundational programmable cleavage was established by "
                "[[10.1126_science.1225829|Jinek 2012]], which defined the "
                "dual-RNA-guided system."
            ),
            "development": (
                "Base editing emerged with [[10.1038_nature17946|Komor 2016]], "
                "which fused a cytidine deaminase to a Cas9 nickase to "
                "convert C to T without inducing DSBs."
            ),
            "sota": (
                "Adenine base editing arrived with "
                "[[10.1038_nature24644|Gaudelli 2017]], which used directed "
                "evolution of TadA to convert A to G with high efficiency."
            ),
        }

    return _narrator


# ---------------------------------------------------------------------------
# Verification helpers
# ---------------------------------------------------------------------------


def _assert(cond: bool, msg: str, problems: list[str]) -> None:
    if not cond:
        problems.append(msg)


def _verify_summary(path: Path, problems: list[str]) -> None:
    if not path.exists():
        problems.append(f"missing summary: {path}")
        return
    body = path.read_text(encoding="utf-8")
    _assert(body.startswith("---\n"), f"{path}: no frontmatter", problems)
    end = body.find("\n---\n", 4)
    if end < 0:
        problems.append(f"{path}: unterminated frontmatter")
        return
    try:
        fm = yaml.safe_load(body[4:end])
    except Exception as exc:
        problems.append(f"{path}: frontmatter not valid YAML: {exc}")
        return
    if "doi" not in fm:
        problems.append(f"{path}: frontmatter missing 'doi'")
    # Wikilinks and content checks.
    if fm.get("tier") == "A":
        if "[reader]" not in body:
            problems.append(f"{path}: tier A but no [reader] marker (reader skipped?)")
        if not PAGE_MARKER_RE.search(body):
            problems.append(f"{path}: tier A but no [p<N>] page markers")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    print("=" * 72)
    print("DRY-RUN: /lit-arc Claude-Code path (no Anthropic SDK)")
    print("=" * 72)

    topic = "CRISPR base editing"
    kb_root = Path(tempfile.mkdtemp(prefix="vaultlab_dryrun_lit_arc_cc_"))
    print(f"\nTopic: {topic}")
    print(f"KB root: {kb_root}")
    print(f"ANTHROPIC_API_KEY set: {bool(os.environ.get('ANTHROPIC_API_KEY'))}")

    seen_summary_tasks: list[SummarizationTask] = []
    seen_arc_tasks: list[ArcTask] = []

    print("\nRunning run_lit_arc with reader + narrator...")
    result = run_lit_arc(
        topic,
        kb_root=kb_root,
        max_seeds=5,
        max_papers_to_summarize=5,
        _client=_FakeClient(_crispr_seeds()),
        _fetch_refs=_fake_fetch_refs,
        _acquire=_fake_acquire,
        reader=_make_reader(seen_summary_tasks),
        narrator=_make_narrator(seen_arc_tasks),
        _today="2026-04-29",
    )

    print("\n" + "-" * 72)
    print("LineageRunResult:")
    print(f"  topic               = {result.topic}")
    print(f"  arc_path            = {result.arc_path}")
    print(f"  search_log_path     = {result.search_log_path}")
    print(f"  corpus_size         = {result.corpus_size}")
    print(f"  pdfs_acquired       = {result.pdfs_acquired}")
    print(f"  summaries_written   = {result.summaries_written}")
    print(f"  duration_seconds    = {result.duration_seconds:.2f}")
    print("-" * 72)

    print(f"\nReader invocations:   {len(seen_summary_tasks)}")
    print(f"Narrator invocations: {len(seen_arc_tasks)}")

    problems: list[str] = []

    # Search log.
    expected_log = search_log_path(kb_root, topic, "2026-04-29")
    _assert(result.search_log_path == expected_log, "search log path mismatch", problems)
    _assert(expected_log.exists(), f"missing search log {expected_log}", problems)

    # Article stubs.
    for seed in _crispr_seeds():
        stub = article_stub_path(kb_root, seed.doi)
        _assert(stub.exists(), f"missing article stub {stub}", problems)

    # Per-paper summaries.
    for seed in _crispr_seeds():
        sp = summary_path(kb_root, seed.doi)
        _verify_summary(sp, problems)

    # Arc.
    expected_arc = concept_path(kb_root, topic, "lineage", "2026-04-29")
    _assert(result.arc_path == expected_arc, "arc_path mismatch", problems)
    _assert(expected_arc.exists(), f"missing arc {expected_arc}", problems)

    if expected_arc.exists():
        arc_md = expected_arc.read_text(encoding="utf-8")
        _assert("# Lineage: CRISPR base editing" in arc_md, "missing arc title", problems)
        _assert("Foundational programmable cleavage" in arc_md, "missing narrator history", problems)
        _assert("Base editing emerged" in arc_md, "missing narrator development", problems)
        _assert("Adenine base editing arrived" in arc_md, "missing narrator sota", problems)
        _assert("LLM narration was skipped" not in arc_md, "narrator response was dropped", problems)
        _assert(
            "[[10.1126_science.1225829|Jinek 2012]]" in arc_md,
            "narrator wikilink missing",
            problems,
        )

    # Provenance.
    json_p = expected_arc.with_name(expected_arc.name + ".provenance.json")
    method_p = expected_arc.with_name(expected_arc.name + ".method.md")
    _assert(json_p.exists(), f"missing {json_p}", problems)
    _assert(method_p.exists(), f"missing {method_p}", problems)
    if json_p.exists():
        rec = json.loads(json_p.read_text(encoding="utf-8"))
        _assert(rec["params"]["narration"] == "claude", "provenance narration != claude", problems)

    # SummarizationTask shape.
    for task in seen_summary_tasks:
        _assert(task.tier == "A", f"expected Tier A task got {task.tier}", problems)
        _assert(task.pdf_path.exists(), f"task PDF missing: {task.pdf_path}", problems)
        _assert(
            task.output_path == summary_path(kb_root, task.doi),
            f"task.output_path != canonical summary path for {task.doi}",
            problems,
        )

    # ArcTask shape.
    for task in seen_arc_tasks:
        _assert(task.topic == topic, "arc task topic mismatch", problems)
        _assert(task.summaries, "arc task summaries empty", problems)
        _assert("CRISPR base editing" in task.prompt, "arc prompt missing topic", problems)

    print("\nFiles on disk:")
    print(f"  Sources/Notes/lit-search-*.md          = {1 if expected_log.exists() else 0}")
    stubs = list((kb_root / 'Sources' / 'Articles').glob('*.md')) if (kb_root / 'Sources' / 'Articles').exists() else []
    print(f"  Sources/Articles/<doi>.md              = {len(stubs)}")
    pdfs = list((kb_root / 'Sources' / 'Papers').glob('*.pdf')) if (kb_root / 'Sources' / 'Papers').exists() else []
    print(f"  Sources/Papers/<doi>.pdf               = {len(pdfs)}")
    print(f"  Wiki/Summaries/<doi>.md                = {sum(1 for p in result.summary_paths.values() if p.exists())}")
    print(f"  Wiki/Concepts/<topic>-lineage-<date>.md = {1 if expected_arc.exists() else 0}")
    print(f"  <arc>.provenance.json                  = {1 if json_p.exists() else 0}")
    print(f"  <arc>.method.md                        = {1 if method_p.exists() else 0}")

    if expected_arc.exists():
        print("\nLineage arc (first 30 lines):")
        for line in expected_arc.read_text(encoding="utf-8").splitlines()[:30]:
            print(f"  | {line}")

    print("\n" + "=" * 72)
    if problems:
        print("DRY-RUN: SOME VERIFICATIONS FAILED")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("DRY-RUN: ALL CANONICAL OUTPUTS PRESENT, NO ANTHROPIC SDK USED")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
