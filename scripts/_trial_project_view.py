"""Smoke test for Phase 9: project view writing in run_lit_arc.

Builds a tiny synthetic 5-paper corpus (2 Tier-A, 3 Tier-C), runs through
``run_lit_arc`` with stub callbacks (no network, no LLM), and verifies
the four ``Wiki/Projects/<slug>/`` files exist + parse as expected.

Usage::

    python scripts/_trial_project_view.py
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import yaml

from vaultlab.kb.paths import (
    project_decisions_path,
    project_lineage_pointer_path,
    project_papers_path,
    project_state_path,
    slugify_topic,
)
from vaultlab.research.acquisition import AcquisitionResult, cache_path_for
from vaultlab.research.lineage import run_lit_arc
from vaultlab.research.paper import Paper


# 5 synthetic seeds; 2 will get "PDFs" (Tier A), 3 stay metadata-only (Tier C).
_SEEDS = [
    Paper(
        title="Seminal CRISPR cleavage",
        authors=["Jinek M"],
        year=2012,
        journal="Science",
        doi="10.1126/science.1225829",
        citation_count=12000,
        source_api="pubmed",
        abstract="abstract a",
    ),
    Paper(
        title="Cytidine base editor",
        authors=["Komor AC"],
        year=2016,
        journal="Nature",
        doi="10.1038/nature17946",
        citation_count=4000,
        source_api="pubmed",
        abstract="abstract b",
    ),
    Paper(
        title="Adenine base editor",
        authors=["Gaudelli NM"],
        year=2017,
        journal="Nature",
        doi="10.1038/nature24644",
        citation_count=3000,
        source_api="pubmed",
        abstract="abstract c",
    ),
    Paper(
        title="Prime editing",
        authors=["Anzalone AV"],
        year=2019,
        journal="Nature",
        doi="10.1038/s41586-019-1711-4",
        citation_count=2000,
        source_api="pubmed",
        abstract="abstract d",
    ),
    Paper(
        title="Twin prime editing",
        authors=["Chen PJ"],
        year=2021,
        journal="Cell",
        doi="10.1016/j.cell.2021.10.022",
        citation_count=500,
        source_api="pubmed",
        abstract="abstract e",
    ),
]


class _FakeClient:
    def search(self, query: str, max_results: int = 20, sources=None):
        return list(_SEEDS)


def _fake_fetch_refs(doi: str):
    """Tiny CrossRef-ref stub."""
    from vaultlab.research.citation_lookup import Reference
    if doi == "10.1126/science.1225829":
        return []
    if doi == "10.1038/nature17946":
        return [Reference(doi="10.1126/science.1225829")]
    return None


def _fake_acquire(corpus, cache_dir, **kwargs):
    """Write 'PDFs' for only the first two seeds — they become Tier-A."""
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    out: dict[str, AcquisitionResult] = {}
    tier_a_dois = {"10.1126/science.1225829", "10.1038/nature17946"}
    for doi in corpus.papers:
        if doi in tier_a_dois:
            target = cache_path_for(doi, cache_dir)
            target.write_bytes(b"%PDF-1.4\n" + b"x" * 4000)
            out[doi] = AcquisitionResult(
                doi=doi,
                pdf_path=target,
                source="unpaywall",
                license="cc-by",
            )
        else:
            out[doi] = AcquisitionResult(
                doi=doi, pdf_path=None, source="failed", license=None,
                error="ref-only",
            )
    return out


def _fake_llm_summary():
    def _caller(*, pdf_bytes, prompt, api_key, model, **_):
        return (
            {
                "tldr": "[stub] One. Two. Three.",
                "why_it_matters": ["[stub] novelty"],
                "methods_summary": "[stub] X.",
                "key_findings": [
                    "[stub] alpha [p1]",
                    "[stub] beta [p2]",
                    "[stub] gamma [p3]",
                ],
                "extracted_references": [],
            },
            1234,
            56,
        )
    return _caller


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="vaultlab_trial_"))
    try:
        topic = "CRISPR editing trial"
        slug = "crispr-trial"
        result = run_lit_arc(
            topic,
            kb_root=tmp,
            max_seeds=5,
            max_papers_to_summarize=5,
            project_slug=slug,
            speaker="Trial Bot",
            _client=_FakeClient(),
            _fetch_refs=_fake_fetch_refs,
            _acquire=_fake_acquire,
            _llm_summary=_fake_llm_summary(),
            _today="2026-04-29",
            _now="2026-04-29T13:37:00",
        )
        print(f"Run finished in {result.duration_seconds:.2f}s")
        print(f"  topic        : {result.topic}")
        print(f"  project_slug : {result.project_slug}")
        print(f"  arc_path     : {result.arc_path.relative_to(tmp)}")
        print(f"  corpus_size  : {result.corpus_size}")
        print(f"  pdfs_acquired: {result.pdfs_acquired}")
        print(f"  summaries    : {result.summaries_written}")

        proj_dir = tmp / "Wiki" / "Projects" / slug
        files = ["START_HERE.md", "papers.md", "lineage.md", "decisions-log.md"]

        # Verify all four exist.
        print("\n=== Project view files ===")
        for f in files:
            p = proj_dir / f
            assert p.exists(), f"missing {p}"
            print(f"  {p.relative_to(tmp)}: {p.stat().st_size} bytes")

        # Path matches what the kb.paths helpers say.
        assert (proj_dir / "START_HERE.md") == project_state_path(tmp, slug)
        assert (proj_dir / "papers.md") == project_papers_path(tmp, slug)
        assert (proj_dir / "lineage.md") == project_lineage_pointer_path(tmp, slug)
        assert (proj_dir / "decisions-log.md") == project_decisions_path(tmp, slug)

        # Frontmatter on each must parse.
        for f in files:
            text = (proj_dir / f).read_text(encoding="utf-8")
            assert text.startswith("---\n"), f"{f}: no frontmatter"
            end = text.find("\n---\n", 4)
            fm = yaml.safe_load(text[4:end])
            assert fm["project"] == slug, f"{f}: project mismatch -> {fm}"
            print(f"  {f}: frontmatter ok ({sorted(fm.keys())})")

        # papers.md preview
        papers_md = (proj_dir / "papers.md").read_text(encoding="utf-8")
        print("\n=== papers.md preview ===")
        for line in papers_md.splitlines()[:25]:
            print(f"  | {line}")

        # decisions-log.md preview
        log_md = (proj_dir / "decisions-log.md").read_text(encoding="utf-8")
        print("\n=== decisions-log.md preview ===")
        for line in log_md.splitlines()[:18]:
            print(f"  | {line}")

        # Idempotency check: run AGAIN with the same slug, log should append.
        result2 = run_lit_arc(
            topic,
            kb_root=tmp,
            max_seeds=5,
            max_papers_to_summarize=5,
            project_slug=slug,
            speaker="Trial Bot",
            _client=_FakeClient(),
            _fetch_refs=_fake_fetch_refs,
            _acquire=_fake_acquire,
            _llm_summary=_fake_llm_summary(),
            _today="2026-04-30",
            _now="2026-04-30T09:00:00",
        )
        log_md2 = (proj_dir / "decisions-log.md").read_text(encoding="utf-8")
        assert log_md2.count("# Decisions log") == 1, (
            "header must appear only once after re-run"
        )
        assert "2026-04-29T13:37:00" in log_md2 and "2026-04-30T09:00:00" in log_md2
        print("\n=== Idempotency check ===")
        print("  decisions-log entries after 2 runs:")
        for line in log_md2.splitlines():
            if line.startswith("## "):
                print(f"    {line}")

        print("\nALL CHECKS PASSED.")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
