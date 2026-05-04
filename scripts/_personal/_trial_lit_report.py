"""Dry-run of the ``/lit-report`` deep-research-mode pipeline.

Drives :func:`vaultlab.research.report.run_lit_report` with stub
callbacks (canned section text + canned crosstalk runner) over a
synthetic CODEX cellular-neighborhoods corpus. Verifies that the
resulting markdown has:

- proper frontmatter (topic / date / total_words / audit_status)
- 5 H2 section headers in canonical order
- a References section with cited DOIs
- a Rigor audit footer
- per-section drafts written under ``Wiki/Concepts/<topic>-report-<date>/``

Usage::

    python scripts/_trial_lit_report.py
"""

from __future__ import annotations

import json
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
os.environ.pop("ANTHROPIC_API_KEY", None)  # prove we don't need it

import yaml  # noqa: E402

from vaultlab.research.acquisition import AcquisitionResult, cache_path_for  # noqa: E402
from vaultlab.research.paper import Paper  # noqa: E402
from vaultlab.research.report import (  # noqa: E402
    SECTION_ORDER,
    run_lit_report,
)


# ---------------------------------------------------------------------------
# Stub fixtures (CODEX cellular-neighborhoods corpus)
# ---------------------------------------------------------------------------


def _codex_seeds() -> list[Paper]:
    return [
        Paper(
            title="histoCAT introduces tissue social networks",
            authors=["Schapiro D", "Bodenmiller B"],
            year=2017,
            journal="Nat Methods",
            doi="10.1038/nmeth.4391",
            citation_count=900,
            source_api="pubmed",
            abstract="histoCAT analytical vocabulary for tissue social networks.",
        ),
        Paper(
            title="CODEX deep profiling of mouse spleen",
            authors=["Goltsev Y", "Nolan GP"],
            year=2018,
            journal="Cell",
            doi="10.1016/j.cell.2018.07.010",
            citation_count=1500,
            source_api="pubmed",
            abstract="CODEX defines indexed niche (i-niche) cellular neighborhoods.",
        ),
        Paper(
            title="Cellular neighborhoods predict CRC outcomes",
            authors=["Schurch CM", "Nolan GP"],
            year=2020,
            journal="Cell",
            doi="10.1016/j.cell.2020.07.005",
            citation_count=800,
            source_api="pubmed",
            abstract="CN definition by k-means clustering of cell-type neighborhoods.",
        ),
        Paper(
            title="Spatial cell-cell interactions in tumors",
            authors=["Phillips D", "Angelo M"],
            year=2021,
            journal="Cell Rep",
            doi="10.1016/j.celrep.2021.108846",
            citation_count=300,
            source_api="pubmed",
            abstract="Multiplexed imaging reveals niche heterogeneity.",
        ),
        Paper(
            title="Graph-neural-network niches",
            authors=["Wu Z", "Saez-Rodriguez J"],
            year=2023,
            journal="Nat Methods",
            doi="10.1038/s41592-023-01778-2",
            citation_count=120,
            source_api="pubmed",
            abstract="GNN-derived neighborhoods improve over k-means.",
        ),
    ]


def _fake_fetch_refs(doi: str):
    from vaultlab.research.citation_lookup import Reference

    chain = {
        "10.1038/nmeth.4391": [],
        "10.1016/j.cell.2018.07.010": [Reference(doi="10.1038/nmeth.4391")],
        "10.1016/j.cell.2020.07.005": [
            Reference(doi="10.1038/nmeth.4391"),
            Reference(doi="10.1016/j.cell.2018.07.010"),
        ],
        "10.1016/j.celrep.2021.108846": [
            Reference(doi="10.1016/j.cell.2018.07.010"),
        ],
        "10.1038/s41592-023-01778-2": [
            Reference(doi="10.1016/j.cell.2020.07.005"),
            Reference(doi="10.1016/j.cell.2018.07.010"),
        ],
    }
    return chain.get(doi)


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
                doi=doi, pdf_path=target, source="unpaywall", license="cc-by",
            )
        else:
            out[doi] = AcquisitionResult(
                doi=doi, pdf_path=None, source="failed", license=None,
                error="ref-only",
            )
    return out


class _FakeClient:
    def __init__(self, seeds):
        self._seeds = seeds

    def search(self, query, max_results=20, sources=None):
        return list(self._seeds)


def _stub_reader(task):
    return {
        "tldr": f"[reader] {task.doi}. Sentence two. Sentence three.",
        "why_it_matters": ["novelty bullet"],
        "methods_summary": "We did X using Y.",
        "key_findings": [
            "finding alpha [p1]",
            "finding beta [p2]",
            "finding gamma [p3]",
        ],
        "extracted_references": [],
    }


# ---------------------------------------------------------------------------
# Stub crosstalk runner — returns canned section + audit JSON
# ---------------------------------------------------------------------------


_SECTION_TEMPLATES: dict[str, str] = {
    "background": (
        "The cellular-neighborhood concept emerged from a confluence of "
        "multiplexed-imaging innovations between 2017 and 2018. "
        "[[10.1038_nmeth.4391|Schapiro 2017]] introduced histoCAT, "
        "establishing the analytical vocabulary for tissue 'social networks'. "
        "[[10.1016_j.cell.2018.07.010|Goltsev 2018]] then operationalized the "
        "term *indexed niche* (i-niche) in the seminal CODEX paper. "
        "By 2020, [[10.1016_j.cell.2020.07.005|Schurch 2020]] generalized the "
        "concept across colorectal-cancer microenvironments. "
    ),
    "methods_landscape": (
        "Methods for defining cellular neighborhoods broadly fall into two "
        "camps: density-based clustering of cell-type frequencies in "
        "fixed-radius windows, and graph-based approaches over Delaunay "
        "or Voronoi tessellations. The histoCAT pipeline "
        "[[10.1038_nmeth.4391|Schapiro 2017]] originated the windowing "
        "approach. CODEX [[10.1016_j.cell.2018.07.010|Goltsev 2018]] "
        "later layered i-niche clustering on top. Recent GNN methods "
        "[[10.1038_s41592-023-01778-2|Wu 2023]] outperform k-means by "
        "learning continuous embeddings. "
    ),
    "findings": (
        "Three patterns emerge across the corpus. First, neighborhood "
        "composition predicts clinical outcomes more reliably than "
        "individual cell-type frequencies "
        "[[10.1016_j.cell.2020.07.005|Schurch 2020]]. Second, the choice "
        "of clustering algorithm meaningfully shifts which 'neighborhoods' "
        "appear "
        "[[10.1016_j.celrep.2021.108846|Phillips 2021]]. Third, "
        "graph-based methods recover finer substructure than density-based "
        "approaches [[10.1038_s41592-023-01778-2|Wu 2023]]. "
    ),
    "contradictions": (
        "Two contested points stand out. "
        "[[10.1016_j.cell.2020.07.005|Schurch 2020]] and "
        "[[10.1016_j.cell.2018.07.010|Goltsev 2018]] differ on whether "
        "9 or ~30 distinct cellular neighborhoods exist in normal tissue. "
        "Cluster-count sensitivity remains underdetermined. "
    ),
    "future_directions": (
        "Three directions look productive. First, a benchmark dataset "
        "comparing density-based vs graph-based methods on the same "
        "tissues [[10.1038_s41592-023-01778-2|Wu 2023]]. Second, "
        "biologically-grounded validation of clusters via spatial "
        "transcriptomics. Third, transfer of CN definitions across "
        "diseases [[10.1016_j.cell.2020.07.005|Schurch 2020]]. "
    ),
}


def _make_runner():
    """Return a runner that fans out canned section + audit JSON."""

    def _runner(meeting, roles):
        outputs = []
        agenda_text = (meeting.agenda.statement if meeting.agenda else "") or ""
        is_audit = meeting.topic.startswith("rigor audit")

        # Resolve which section is active (for the section meetings).
        section_id = "background"
        for sec in SECTION_ORDER:
            if sec.replace("_", " ") in agenda_text:
                section_id = sec
                break

        for r in roles:
            if r.id == "synthesizer" and not is_audit:
                base = _SECTION_TEMPLATES[section_id]
                # Pad to ~ target word count by repeating the template.
                target_words = {
                    "background": 650,
                    "methods_landscape": 1000,
                    "findings": 1250,
                    "contradictions": 400,
                    "future_directions": 300,
                }[section_id]
                # Each template is ~80 words → repeat enough to hit target.
                base_words = base.split()
                full_words: list[str] = []
                while len(full_words) < target_words:
                    full_words.extend(base_words)
                full_text = " ".join(full_words[:target_words])
                payload = {
                    "section_text": full_text,
                    "claims_with_evidence": [
                        {
                            "claim": f"{section_id} canonical claim 1",
                            "doi_slugs": ["10.1038_nmeth.4391"],
                        },
                        {
                            "claim": f"{section_id} canonical claim 2",
                            "doi_slugs": ["10.1016_j.cell.2018.07.010"],
                        },
                    ],
                }
                outputs.append({"output": json.dumps(payload)})
            elif r.id == "rigor_auditor":
                # Pass clean — single minor issue for realism.
                payload = {
                    "passed": True,
                    "issues": [
                        {
                            "loc": "References",
                            "severity": "minor",
                            "kind": "stylistic",
                            "fix": "Consider grouping refs by year.",
                        }
                    ],
                }
                outputs.append({"output": json.dumps(payload)})
            else:
                outputs.append({"output": f"[{r.id} placeholder]"})
        return outputs

    return _runner


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    print("=" * 72)
    print("Trial: /lit-report deep-research-mode dry run")
    print("=" * 72)

    with tempfile.TemporaryDirectory() as td:
        kb_root = Path(td)
        topic = "CODEX cellular neighborhoods"
        client = _FakeClient(_codex_seeds())
        runner = _make_runner()

        result = run_lit_report(
            topic,
            kb_root=kb_root,
            max_seeds=5,
            max_papers_to_summarize=5,
            depth="thorough",
            audience="graduate-student",
            _client=client,
            _fetch_refs=_fake_fetch_refs,
            _acquire=_fake_acquire,
            reader=_stub_reader,
            crosstalk_runner=runner,
            crosstalk_n_rounds=2,
            _today="2026-04-30",
        )

        print()
        print(f"Topic:           {result.topic}")
        print(f"Report path:     {result.report_path}")
        print(f"Audit path:      {result.audit_report_path}")
        print(f"Audit status:    {result.audit_status}")
        print(f"Corpus size:     {result.corpus_size}")
        print(f"PDFs acquired:   {result.pdfs_acquired}")
        print(f"Summaries used:  {result.summaries_used}")
        print(f"Total words:     {result.word_count}")
        print(f"Duration:        {result.duration_seconds:.2f}s")
        print()
        print("Per-section word counts:")
        for sec in SECTION_ORDER:
            wc = result.section_word_counts.get(sec, 0)
            tgt = {
                "background": 650, "methods_landscape": 1000, "findings": 1250,
                "contradictions": 400, "future_directions": 300,
            }[sec]
            print(f"  {sec:<22} {wc:>4} words (target ~{tgt})")
        print()

        # Verify structure.
        md = result.report_path.read_text(encoding="utf-8")
        assert md.startswith("---\n"), "report missing frontmatter"
        end = md.find("\n---\n", 4)
        fm = yaml.safe_load(md[4:end])
        print("Frontmatter keys:")
        for k in sorted(fm.keys()):
            print(f"  {k}: {fm[k]!r}")
        print()

        # Check H2 sections + word range.
        for sec in SECTION_ORDER:
            label = {
                "background": "Background",
                "methods_landscape": "Methods landscape",
                "findings": "Key findings",
                "contradictions": "Contradictions & open questions",
                "future_directions": "Future directions",
            }[sec]
            assert f"## {label}" in md, f"missing H2 for {sec}"
        assert "## References" in md, "missing References section"
        assert "## Rigor audit" in md, "missing Rigor audit footer"

        # Check per-section drafts.
        for sec in SECTION_ORDER:
            p = result.section_paths[sec]
            assert p.exists(), f"missing draft for {sec}"

        # Spec band check.
        if 3000 <= result.word_count <= 5000:
            print(f"OK Word count {result.word_count} is in spec band 3000-5000.")
        else:
            print(f"WARN Word count {result.word_count} is OUTSIDE spec band 3000-5000.")

        # Show first 600 chars of the assembled report.
        print()
        print("--- First 600 chars of report body ---")
        body_start = end + len("\n---\n")
        body_preview = md[body_start:body_start + 600]
        print(body_preview)
        print("...")

        print()
        print("OK Trial complete.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
