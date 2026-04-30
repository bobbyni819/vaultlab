"""Unit tests for vaultlab.research.lineage.

Every external dependency (search, CrossRef ref-walk, PDF acquisition,
LLM calls) is stubbed via ``run_lit_arc``'s injection points so the
suite runs offline.

Coverage
--------
* Search log written to canonical ``Sources/Notes/`` path with frontmatter.
* Article stubs written under ``Sources/Articles/<doi>.md`` for every
  seed with a DOI; seeds without DOIs are skipped (not raised).
* Corpus + metrics built; PDFs acquired; summaries written.
* Lineage arc:
    - LLM invoked when ``_llm_arc`` injected; narrative paragraphs
      flow into the rendered markdown.
    - LLM skipped when neither ``_llm_arc`` nor ``ANTHROPIC_API_KEY``
      is available; structured tables still emit + a "narration skipped"
      note appears.
* Arc markdown contains canonical sections (History/Development/SOTA),
  top OG table, top co-citation pairs, and proper frontmatter.
* Provenance sidecars (``.provenance.json`` + ``.method.md``) appear
  next to the arc.
* :class:`LineageRunResult` carries the expected fields.
* ``build_arc_prompt`` includes wikilink slugs + bucketed summaries.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from vaultlab.kb.paths import (
    article_stub_path,
    concept_path,
    search_log_path,
    slugify_doi,
    summary_path,
)
from vaultlab.research.acquisition import AcquisitionResult
from vaultlab.research.lineage import (
    ArcTask,
    LineageRunResult,
    arc_response_schema,
    build_arc_prompt,
    prepare_arc_task,
    render_arc_from_response,
    render_arc_markdown,
    run_lit_arc,
)
from vaultlab.research.paper import Paper
from vaultlab.research.summarize import PaperSummary


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_seeds() -> list[Paper]:
    """Three CRISPR base-editing seeds — all with DOIs."""
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
    """Stub :class:`vaultlab.research.ResearchClient` for tests."""

    def __init__(self, seeds: list[Paper]):
        self._seeds = seeds
        self.last_query = ""
        self.last_max = 0

    def search(self, query: str, max_results: int = 20, sources=None):
        self.last_query = query
        self.last_max = max_results
        return list(self._seeds)


def _fake_fetch_refs(doi: str):
    """Tiny CrossRef-ref stub: B and C cite A; A cites nothing.

    Returns ``None`` (CrossRef doesn't know) for anything else.
    """
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
    """Simulate acquisition: write a fake PDF for every seed DOI.

    Returns a mapping with ``unpaywall``-tier results so the orchestrator
    sees ``pdf_path`` pointing at a real file in ``cache_dir``.
    """
    from vaultlab.research.acquisition import cache_path_for

    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    out: dict[str, AcquisitionResult] = {}
    for doi in corpus.papers:
        target = cache_path_for(doi, cache_dir)
        # Only "acquire" the seed papers (those with full metadata).
        paper = corpus.papers[doi]
        if paper.year:
            target.write_bytes(b"%PDF-1.4\n" + b"x" * 4000)
            out[doi] = AcquisitionResult(
                doi=doi,
                pdf_path=target,
                source="unpaywall",
                license="cc-by",
            )
        else:
            out[doi] = AcquisitionResult(
                doi=doi,
                pdf_path=None,
                source="failed",
                license=None,
                error="ref-only",
            )
    return out


def _fake_llm_summary():
    """Stub Claude PDF-reader returning deterministic JSON."""

    def _caller(*, pdf_bytes, prompt, api_key, model, **_):
        return (
            {
                "tldr": "[stub] Sentence one. Sentence two. Sentence three.",
                "why_it_matters": ["[stub] novelty bullet"],
                "methods_summary": "[stub] We did X with Y.",
                "key_findings": [
                    "[stub] finding alpha [p1]",
                    "[stub] finding beta [p2]",
                    "[stub] finding gamma [p3]",
                ],
                "extracted_references": [],
            },
            1234,
            56,
        )

    return _caller


def _fake_llm_arc(prompts_seen: list[str]):
    """Stub the lineage-arc Claude call. Captures the prompt for assertion."""

    def _caller(*, prompt: str, api_key: str, model: str):
        prompts_seen.append(prompt)
        return {
            "history": (
                "Foundational work [[10.1126_science.1225829|Jinek 2012]] "
                "defined programmable cleavage."
            ),
            "development": (
                "Base editing emerged with [[10.1038_nature17946|Komor 2016]]."
            ),
            "sota": (
                "Adenine base editing [[10.1038_nature24644|Gaudelli 2017]] "
                "extended the editing window."
            ),
        }

    return _caller


# ---------------------------------------------------------------------------
# build_arc_prompt
# ---------------------------------------------------------------------------


def test_build_arc_prompt_includes_wikilinks_and_buckets():
    summaries = {
        "10.1126/science.1225829": PaperSummary(
            doi="10.1126/science.1225829",
            title="Programmable cleavage",
            authors=["Jinek M"],
            year=2012,
            year_bucket="history",
            tldr="Founded programmable cleavage.",
            key_findings=["dual-RNA guide [p3]"],
            tier="A",
        ),
        "10.1038/nature17946": PaperSummary(
            doi="10.1038/nature17946",
            title="Cytidine base editor",
            authors=["Komor AC"],
            year=2016,
            year_bucket="development",
            tldr="C->T at target loci.",
            key_findings=["37% efficiency [p4]"],
            tier="A",
        ),
        "10.1038/nature24644": PaperSummary(
            doi="10.1038/nature24644",
            title="Adenine base editor",
            authors=["Gaudelli NM"],
            year=2017,
            year_bucket="sota",
            tldr="A->G transitions.",
            key_findings=["TadA evolved [p5]"],
            tier="A",
        ),
    }
    prompt = build_arc_prompt(
        topic="CRISPR base editing",
        summaries=summaries,
        top_og=[("10.1126/science.1225829", 0.66)],
        top_co_citation=[("10.1126/science.1225829", "10.1038/nature17946", 2)],
    )
    assert "CRISPR base editing" in prompt
    assert "history bucket" in prompt
    assert "development bucket" in prompt
    assert "sota bucket" in prompt
    # Wikilink slugs use the underscore-substituted DOI.
    assert "[[10.1126_science.1225829|Jinek 2012]]" in prompt
    assert "[[10.1038_nature17946|Komor 2016]]" in prompt
    assert "[[10.1038_nature24644|Gaudelli 2017]]" in prompt
    # Co-citation block present.
    assert "co-cited by 2" in prompt


# ---------------------------------------------------------------------------
# render_arc_markdown
# ---------------------------------------------------------------------------


def _three_summaries() -> dict[str, PaperSummary]:
    return {
        "10.1126/science.1225829": PaperSummary(
            doi="10.1126/science.1225829",
            title="Programmable cleavage",
            authors=["Jinek M"],
            year=2012,
            year_bucket="history",
            tldr="Founded programmable cleavage.",
            key_findings=["dual-RNA guide [p3]"],
            og_score=0.66,
            forward_influence=2,
            tier="A",
        ),
        "10.1038/nature17946": PaperSummary(
            doi="10.1038/nature17946",
            title="Cytidine base editor",
            authors=["Komor AC"],
            year=2016,
            year_bucket="development",
            tldr="C->T at target loci.",
            key_findings=["37% efficiency [p4]"],
            og_score=0.33,
            forward_influence=1,
            tier="A",
        ),
        "10.1038/nature24644": PaperSummary(
            doi="10.1038/nature24644",
            title="Adenine base editor",
            authors=["Gaudelli NM"],
            year=2017,
            year_bucket="sota",
            tldr="A->G transitions.",
            key_findings=["TadA evolved [p5]"],
            og_score=0.0,
            forward_influence=0,
            tier="A",
        ),
    }


def _three_corpus():
    from vaultlab.research.corpus import Corpus
    from vaultlab.research.graph_metrics import compute_metrics

    seeds = _make_seeds()
    corpus = Corpus(topic="CRISPR base editing", seeds=seeds)
    for s in seeds:
        corpus.papers[s.doi.lower()] = s
    corpus.references = {
        "10.1126/science.1225829": [],
        "10.1038/nature17946": ["10.1126/science.1225829"],
        "10.1038/nature24644": [
            "10.1126/science.1225829",
            "10.1038/nature17946",
        ],
    }
    compute_metrics(corpus)
    return corpus


def test_render_arc_with_narrative_paragraphs_present():
    summaries = _three_summaries()
    corpus = _three_corpus()
    md = render_arc_markdown(
        topic="CRISPR base editing",
        date_str="2026-04-29",
        summaries=summaries,
        corpus=corpus,
        method_relpath="crispr-base-editing-lineage-2026-04-29.md.method.md",
        narrative={
            "history": "History prose [[10.1126_science.1225829|Jinek 2012]].",
            "development": "Dev prose [[10.1038_nature17946|Komor 2016]].",
            "sota": "SOTA prose [[10.1038_nature24644|Gaudelli 2017]].",
        },
    )
    # Frontmatter parses.
    assert md.startswith("---\n")
    end = md.find("\n---\n", 4)
    fm = yaml.safe_load(md[4:end])
    assert fm["topic"] == "CRISPR base editing"
    assert fm["seeds"] == 3
    assert fm["corpus_size"] == 3
    assert fm["papers_with_full_text"] == 3
    assert fm["generated_by"] == "vaultlab.research.lineage.run_lit_arc"
    # Sections present.
    assert "## History" in md
    assert "## Development" in md
    assert "## State of the art" in md
    assert "History prose" in md
    assert "## Top OG papers" in md
    assert "## Top co-citation pairs" in md
    # Wikilinks.
    assert "[[10.1126_science.1225829|Jinek 2012]]" in md
    # No "narration skipped" note when narrative is present.
    assert "LLM narration was skipped" not in md


def test_render_arc_without_narrative_emits_skipped_note():
    summaries = _three_summaries()
    corpus = _three_corpus()
    md = render_arc_markdown(
        topic="CRISPR base editing",
        date_str="2026-04-29",
        summaries=summaries,
        corpus=corpus,
        method_relpath="crispr-base-editing-lineage-2026-04-29.md.method.md",
        narrative=None,
        narrative_skipped_reason="No Anthropic API key found.",
    )
    assert "LLM narration was skipped" in md
    assert "No Anthropic API key found." in md
    # Tables still rendered.
    assert "## Top OG papers" in md


# ---------------------------------------------------------------------------
# run_lit_arc — end-to-end with stubs
# ---------------------------------------------------------------------------


def test_run_lit_arc_full_pipeline_with_stubs(tmp_path, monkeypatch):
    """Stubbed end-to-end: every external call replaced.

    Verifies all canonical output paths are written.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    seeds = _make_seeds()
    client = _FakeClient(seeds)
    prompts: list[str] = []

    result = run_lit_arc(
        "CRISPR base editing",
        kb_root=tmp_path,
        max_seeds=5,
        max_papers_to_summarize=5,
        _client=client,
        _fetch_refs=_fake_fetch_refs,
        _acquire=_fake_acquire,
        _llm_summary=_fake_llm_summary(),
        _llm_arc=_fake_llm_arc(prompts),
        _today="2026-04-29",
    )

    # Result fields.
    assert isinstance(result, LineageRunResult)
    assert result.topic == "CRISPR base editing"
    assert result.corpus_size >= 3  # at least the 3 seeds (refs may add more)
    assert result.pdfs_acquired >= 3
    assert result.summaries_written >= 3
    assert result.duration_seconds >= 0.0

    # Search log written.
    expected_log = search_log_path(tmp_path, "CRISPR base editing", "2026-04-29")
    assert result.search_log_path == expected_log
    assert expected_log.exists()
    log_text = expected_log.read_text(encoding="utf-8")
    assert "CRISPR base editing" in log_text
    assert "n_seeds: 3" in log_text

    # Article stubs.
    for seed in seeds:
        stub = article_stub_path(tmp_path, seed.doi)
        assert stub.exists(), f"missing stub {stub}"
        body = stub.read_text(encoding="utf-8")
        assert seed.doi in body

    # Summaries.
    for seed in seeds:
        summary_p = summary_path(tmp_path, seed.doi)
        assert summary_p.exists(), f"missing summary {summary_p}"
        assert summary_p == result.summary_paths[seed.doi.lower()]

    # PDFs in cache (Sources/Papers/<doi-slug>.pdf shape from acquisition).
    papers_dir = tmp_path / "Sources" / "Papers"
    pdfs = list(papers_dir.glob("*.pdf"))
    assert len(pdfs) >= 3

    # Lineage arc.
    expected_arc = concept_path(tmp_path, "CRISPR base editing", "lineage", "2026-04-29")
    assert result.arc_path == expected_arc
    assert expected_arc.exists()
    arc_md = expected_arc.read_text(encoding="utf-8")
    assert "# Lineage: CRISPR base editing" in arc_md
    assert "## History" in arc_md
    assert "## Development" in arc_md
    assert "## State of the art" in arc_md
    assert "## Top OG papers" in arc_md
    # Narrative paragraphs from the stubbed LLM are present.
    assert "Foundational work" in arc_md
    assert "Base editing emerged" in arc_md
    # Provenance receipts.
    json_p = expected_arc.with_name(expected_arc.name + ".provenance.json")
    method_p = expected_arc.with_name(expected_arc.name + ".method.md")
    assert json_p.exists(), f"missing {json_p}"
    assert method_p.exists(), f"missing {method_p}"
    rec = json.loads(json_p.read_text(encoding="utf-8"))
    assert rec["generated_by"] == "vaultlab.research.lineage.run_lit_arc"
    assert rec["project"] == "lit-arc"
    assert rec["topic"] == "CRISPR base editing"
    assert rec["params"]["max_seeds"] == 5
    assert rec["params"]["narration"] == "claude"

    # Stubbed LLM was actually invoked once for the arc narrative.
    assert len(prompts) == 1
    assert "CRISPR base editing" in prompts[0]


def test_run_lit_arc_skips_llm_narrative_when_no_key(tmp_path, monkeypatch):
    """Without ``ANTHROPIC_API_KEY``, the arc still writes — without prose."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    # Force the lazy config lookup to return empty so summarize.load_anthropic_api_key
    # raises and the orchestrator falls back to "skipped".
    monkeypatch.setattr(
        "vaultlab.research.config.get_config",
        lambda *a, **k: {},
    )

    client = _FakeClient(_make_seeds())
    result = run_lit_arc(
        "CRISPR base editing",
        kb_root=tmp_path,
        max_seeds=5,
        max_papers_to_summarize=5,
        _client=client,
        _fetch_refs=_fake_fetch_refs,
        _acquire=_fake_acquire,
        _llm_summary=_fake_llm_summary(),
        # _llm_arc NOT passed -> falls through to load_anthropic_api_key,
        # which raises SummarizeAuthError -> narrative=None.
        _today="2026-04-29",
    )

    arc_md = result.arc_path.read_text(encoding="utf-8")
    assert "LLM narration was skipped" in arc_md
    # Provenance still written, with narration=skipped param.
    json_p = result.arc_path.with_name(result.arc_path.name + ".provenance.json")
    assert json_p.exists()
    rec = json.loads(json_p.read_text(encoding="utf-8"))
    assert rec["params"]["narration"] == "skipped"


def test_run_lit_arc_handles_seeds_without_doi(tmp_path, monkeypatch):
    """Seeds without DOIs are dropped from corpus + skipped from stubs."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(
        "vaultlab.research.config.get_config",
        lambda *a, **k: {},
    )
    seeds = _make_seeds()
    seeds.append(Paper(title="DOI-less seed", year=2020, doi=""))
    client = _FakeClient(seeds)
    result = run_lit_arc(
        "CRISPR base editing",
        kb_root=tmp_path,
        max_seeds=10,
        max_papers_to_summarize=10,
        _client=client,
        _fetch_refs=_fake_fetch_refs,
        _acquire=_fake_acquire,
        _llm_summary=_fake_llm_summary(),
        _today="2026-04-29",
    )
    # Three valid stubs, the DOI-less seed has no path to write.
    stubs_dir = tmp_path / "Sources" / "Articles"
    stubs = list(stubs_dir.glob("*.md"))
    assert len(stubs) == 3
    # The arc was still produced.
    assert result.arc_path.exists()


def test_run_lit_arc_arc_path_routes_via_kb_paths(tmp_path, monkeypatch):
    """The arc lands at the canonical concept_path target — no hand-rolled paths."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(
        "vaultlab.research.config.get_config",
        lambda *a, **k: {},
    )
    client = _FakeClient(_make_seeds())
    result = run_lit_arc(
        "Galectin-4 sulfatide",
        kb_root=tmp_path,
        max_seeds=5,
        max_papers_to_summarize=5,
        _client=client,
        _fetch_refs=_fake_fetch_refs,
        _acquire=_fake_acquire,
        _llm_summary=_fake_llm_summary(),
        _today="2026-04-29",
    )
    expected = concept_path(tmp_path, "Galectin-4 sulfatide", "lineage", "2026-04-29")
    assert result.arc_path == expected
    # Slug used in filename.
    assert "galectin-4-sulfatide-lineage-2026-04-29.md" == expected.name


# ---------------------------------------------------------------------------
# Claude-Code-callable arc path: prepare_arc_task / render_arc_from_response
# ---------------------------------------------------------------------------


def test_arc_response_schema_is_valid_json_schema():
    schema = arc_response_schema()
    assert schema["type"] == "object"
    assert set(schema["required"]) == {"history", "development", "sota"}
    for key, spec in schema["properties"].items():
        assert spec["type"] == "string", f"{key} should be string"
    # Round-trip through JSON.
    assert json.loads(json.dumps(schema)) == schema


def test_prepare_arc_task_makes_no_http_calls(tmp_path, monkeypatch):
    import sys

    class _Guard:
        def __getattr__(self, name):
            raise AssertionError(
                f"prepare_arc_task touched anthropic.{name}"
            )

    monkeypatch.setitem(sys.modules, "anthropic", _Guard())

    summaries = _three_summaries()
    corpus = _three_corpus()
    task = prepare_arc_task(
        topic="CRISPR base editing",
        corpus=corpus,
        summaries=summaries,
        kb_root=tmp_path,
        date_str="2026-04-29",
    )
    assert isinstance(task, ArcTask)
    assert task.topic == "CRISPR base editing"
    assert task.date_str == "2026-04-29"
    assert task.summaries == summaries
    assert task.response_schema == arc_response_schema()
    # Prompt embeds the topic and bucketed wikilinks.
    assert "CRISPR base editing" in task.prompt
    assert "[[10.1126_science.1225829|Jinek 2012]]" in task.prompt
    # Output path lands at the canonical concept location.
    assert task.output_path == concept_path(
        tmp_path, "CRISPR base editing", "lineage", "2026-04-29"
    )
    # method_relpath is consistent with the file we'd write.
    assert task.method_relpath == task.output_path.name + ".method.md"


def test_prepare_arc_task_prompt_matches_sdk_prompt(tmp_path):
    """The arc prompt prepared for Claude Code must match what build_arc_prompt
    produces directly with the same metrics inputs."""
    summaries = _three_summaries()
    corpus = _three_corpus()
    metrics = corpus.metrics
    top_og = sorted(metrics.og_score.items(), key=lambda kv: kv[1], reverse=True)[:10]
    top_co = list(metrics.co_citation_pairs[:10])
    task = prepare_arc_task(
        topic="CRISPR base editing",
        corpus=corpus,
        summaries=summaries,
        kb_root=tmp_path,
        date_str="2026-04-29",
    )
    expected_prompt = build_arc_prompt(
        topic="CRISPR base editing",
        summaries=summaries,
        top_og=top_og,
        top_co_citation=top_co,
    )
    assert task.prompt == expected_prompt


def test_render_arc_from_response_writes_arc_markdown(tmp_path):
    summaries = _three_summaries()
    corpus = _three_corpus()
    task = prepare_arc_task(
        topic="CRISPR base editing",
        corpus=corpus,
        summaries=summaries,
        kb_root=tmp_path,
        date_str="2026-04-29",
    )
    response = {
        "history": "History prose [[10.1126_science.1225829|Jinek 2012]].",
        "development": "Dev prose [[10.1038_nature17946|Komor 2016]].",
        "sota": "SOTA prose [[10.1038_nature24644|Gaudelli 2017]].",
    }
    written = render_arc_from_response(task, response, corpus=corpus)
    assert written == task.output_path
    assert written.exists()
    md = written.read_text(encoding="utf-8")
    assert "# Lineage: CRISPR base editing" in md
    assert "History prose" in md
    assert "Dev prose" in md
    assert "SOTA prose" in md
    # No "skipped" note when narrative present.
    assert "LLM narration was skipped" not in md
    # Frontmatter parses.
    assert md.startswith("---\n")
    end = md.find("\n---\n", 4)
    fm = yaml.safe_load(md[4:end])
    assert fm["topic"] == "CRISPR base editing"


def test_render_arc_from_response_empty_emits_skipped_note(tmp_path):
    summaries = _three_summaries()
    corpus = _three_corpus()
    task = prepare_arc_task(
        topic="CRISPR base editing",
        corpus=corpus,
        summaries=summaries,
        kb_root=tmp_path,
        date_str="2026-04-29",
    )
    written = render_arc_from_response(task, {}, corpus=corpus)
    md = written.read_text(encoding="utf-8")
    assert "LLM narration was skipped" in md
    # Tables still emitted.
    assert "## Top OG papers" in md


def test_run_lit_arc_with_reader_and_narrator(tmp_path, monkeypatch):
    """Claude-Code mode: reader + narrator replace SDK calls; no key required."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(
        "vaultlab.research.config.get_config",
        lambda *a, **k: {},
    )

    seen_summary_tasks = []
    seen_arc_tasks = []

    def _reader(task):
        seen_summary_tasks.append(task)
        return {
            "tldr": f"[reader] {task.doi}. b. c.",
            "why_it_matters": ["r1"],
            "methods_summary": "m",
            "key_findings": ["a [p1]", "b [p2]", "c [p3]"],
            "extracted_references": [],
        }

    def _narrator(task):
        seen_arc_tasks.append(task)
        return {
            "history": "[narrator] History prose.",
            "development": "[narrator] Dev prose.",
            "sota": "[narrator] SOTA prose.",
        }

    client = _FakeClient(_make_seeds())
    result = run_lit_arc(
        "CRISPR base editing",
        kb_root=tmp_path,
        max_seeds=5,
        max_papers_to_summarize=5,
        _client=client,
        _fetch_refs=_fake_fetch_refs,
        _acquire=_fake_acquire,
        reader=_reader,
        narrator=_narrator,
        _today="2026-04-29",
    )

    # Reader called once per Tier-A paper (3 seeds get PDFs in _fake_acquire).
    assert len(seen_summary_tasks) == 3
    # Narrator called exactly once.
    assert len(seen_arc_tasks) == 1
    arc_task = seen_arc_tasks[0]
    assert isinstance(arc_task, ArcTask)
    assert arc_task.topic == "CRISPR base editing"

    # Arc has the narrator's prose in it.
    md = result.arc_path.read_text(encoding="utf-8")
    assert "[narrator] History prose." in md
    assert "[narrator] Dev prose." in md
    assert "LLM narration was skipped" not in md

    # Per-paper summaries carry the reader's tldr.
    for doi, p in result.summary_paths.items():
        assert p.exists()
        if p.read_text(encoding="utf-8").startswith("---"):
            # Tier-A files have [reader] markers; the Tier-C stub note instead.
            body = p.read_text(encoding="utf-8")
            assert "[reader]" in body or "Tier C stub" in body

    # Provenance recorded.
    json_p = result.arc_path.with_name(result.arc_path.name + ".provenance.json")
    rec = json.loads(json_p.read_text(encoding="utf-8"))
    assert rec["params"]["narration"] == "claude"
