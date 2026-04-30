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
    project_decisions_path,
    project_lineage_pointer_path,
    project_papers_path,
    project_state_path,
    search_log_path,
    slugify_doi,
    slugify_topic,
    summary_path,
)
from vaultlab.research.acquisition import AcquisitionResult
from vaultlab.research.lineage import (
    ArcTask,
    LineageRunResult,
    _derive_max_papers,
    _write_project_view,
    arc_response_schema,
    build_arc_prompt,
    prepare_arc_task,
    render_arc_from_response,
    render_arc_markdown,
    run_lit_arc,
)
from vaultlab.research.corpus import Corpus
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

    # Phase 9 also fired: Wiki/Projects/<slug>/ exists with all 4 files.
    assert result.project_slug == slugify_topic("CRISPR base editing")
    for kind in ("start_here", "papers", "lineage", "decisions_log"):
        assert kind in result.project_view_paths
        p = result.project_view_paths[kind]
        assert p.exists(), f"missing project-view file for {kind}: {p}"


# ---------------------------------------------------------------------------
# Phase 9: project view writer (Wiki/Projects/<slug>/)
# ---------------------------------------------------------------------------


def _two_summaries() -> dict[str, PaperSummary]:
    """Synthetic 2-paper summaries dict used to exercise project-view writes."""
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
            og_score=0.0,
            forward_influence=0,
            tier="C",
        ),
    }


def _two_corpus() -> Corpus:
    seeds = [
        Paper(title="t1", authors=["Jinek M"], year=2012, doi="10.1126/science.1225829"),
        Paper(title="t2", authors=["Komor AC"], year=2016, doi="10.1038/nature17946"),
    ]
    corpus = Corpus(topic="t", seeds=seeds)
    for s in seeds:
        corpus.papers[s.doi.lower()] = s
    return corpus


def test_write_project_view_writes_all_four_files(tmp_path: Path) -> None:
    summaries = _two_summaries()
    corpus = _two_corpus()
    arc_p = tmp_path / "Wiki" / "Concepts" / "fake-lineage-2026-04-29.md"
    arc_p.parent.mkdir(parents=True)
    arc_p.write_text("# fake arc\n", encoding="utf-8")

    out = _write_project_view(
        kb_root=tmp_path,
        project_slug="codex-cn-test",
        topic="CODEX cellular neighborhoods",
        arc_path=arc_p,
        summaries=summaries,
        corpus=corpus,
        deck_path=tmp_path / "Output" / "codex-cn-test" / "deck.pptx",
        run_id="2026-04-29T12-00-00",
        date_str="2026-04-29",
        speaker="Bobby Y.X. Ni",
        sources_n=6,
        picker_method="content-aware",
        crosstalk="picker+arc",
        timestamp="2026-04-29T12:00:00",
    )

    # All four files were written.
    assert set(out.keys()) == {"start_here", "papers", "lineage", "decisions_log"}
    for kind, p in out.items():
        assert p.exists(), f"{kind} not written"

    # Paths route through vaultlab.kb.paths.
    assert out["start_here"] == project_state_path(tmp_path, "codex-cn-test")
    assert out["papers"] == project_papers_path(tmp_path, "codex-cn-test")
    assert out["lineage"] == project_lineage_pointer_path(tmp_path, "codex-cn-test")
    assert out["decisions_log"] == project_decisions_path(tmp_path, "codex-cn-test")

    # papers.md content sanity-check.
    papers_md = out["papers"].read_text(encoding="utf-8")
    assert "# Papers — codex-cn-test" in papers_md
    assert "## Tier A — full text read by Claude Code" in papers_md
    assert "## Tier C — citation-stat-only stubs" in papers_md
    assert "[[10.1126_science.1225829\\|Jinek 2012]]" in papers_md
    assert "[[10.1038_nature17946\\|Komor 2016]]" in papers_md
    # Tier-A row should show the OG score.
    assert "0.66" in papers_md
    # No "Also in" project listed when this is the only project.
    assert "| — |" in papers_md or "—" in papers_md

    # lineage.md is a pointer.
    lineage_md = out["lineage"].read_text(encoding="utf-8")
    assert "kind: lineage-pointer" in lineage_md
    assert "[[fake-lineage-2026-04-29]]" in lineage_md

    # START_HERE.md has correct counts.
    start_md = out["start_here"].read_text(encoding="utf-8")
    assert "**2 papers** total" in start_md
    assert "**1 Tier-A**" in start_md
    assert "**1 Tier-C**" in start_md
    assert "kind: project-start-here" in start_md

    # decisions-log.md frontmatter + first entry present.
    log_md = out["decisions_log"].read_text(encoding="utf-8")
    assert "kind: decisions-log" in log_md
    assert "## 2026-04-29T12:00:00 — lit-arc run" in log_md
    assert "**Topic:** CODEX cellular neighborhoods" in log_md
    assert "**Speaker:** Bobby Y.X. Ni" in log_md
    assert "**Tier-A picks:** 1" in log_md
    assert "picker_method=`content-aware`" in log_md
    assert "**Multi-agent crosstalk:** picker+arc" in log_md
    assert "**Run ID:** 2026-04-29T12-00-00" in log_md


def test_write_project_view_appends_to_existing_decisions_log(tmp_path: Path) -> None:
    summaries = _two_summaries()
    corpus = _two_corpus()
    arc_p = tmp_path / "Wiki" / "Concepts" / "fake.md"
    arc_p.parent.mkdir(parents=True)
    arc_p.write_text("# arc\n", encoding="utf-8")

    # First run.
    _write_project_view(
        kb_root=tmp_path,
        project_slug="proj",
        topic="proj topic",
        arc_path=arc_p,
        summaries=summaries,
        corpus=corpus,
        date_str="2026-04-29",
        timestamp="2026-04-29T10:00:00",
    )
    # Second run with a later timestamp.
    _write_project_view(
        kb_root=tmp_path,
        project_slug="proj",
        topic="proj topic",
        arc_path=arc_p,
        summaries=summaries,
        corpus=corpus,
        date_str="2026-04-30",
        timestamp="2026-04-30T11:30:00",
    )

    log_md = project_decisions_path(tmp_path, "proj").read_text(encoding="utf-8")
    # Both timestamps appear, and the header appears exactly once.
    assert log_md.count("# Decisions log — proj") == 1
    assert "## 2026-04-29T10:00:00 — lit-arc run" in log_md
    assert "## 2026-04-30T11:30:00 — lit-arc run" in log_md
    # Order: earlier entry should come first (pure append).
    idx_first = log_md.find("2026-04-29T10:00:00")
    idx_second = log_md.find("2026-04-30T11:30:00")
    assert 0 < idx_first < idx_second


def test_write_project_view_overwrites_papers_and_lineage(tmp_path: Path) -> None:
    """papers.md and lineage.md reflect current state — they don't append."""
    summaries = _two_summaries()
    corpus = _two_corpus()
    arc_p = tmp_path / "Wiki" / "Concepts" / "arc1.md"
    arc_p.parent.mkdir(parents=True)
    arc_p.write_text("# arc\n", encoding="utf-8")

    _write_project_view(
        kb_root=tmp_path,
        project_slug="proj",
        topic="topic v1",
        arc_path=arc_p,
        summaries=summaries,
        corpus=corpus,
        date_str="2026-04-29",
        timestamp="2026-04-29T10:00:00",
    )
    # Second run with only one paper.
    smaller = {"10.1126/science.1225829": summaries["10.1126/science.1225829"]}
    arc2 = tmp_path / "Wiki" / "Concepts" / "arc2.md"
    arc2.write_text("# arc2\n", encoding="utf-8")
    _write_project_view(
        kb_root=tmp_path,
        project_slug="proj",
        topic="topic v2",
        arc_path=arc2,
        summaries=smaller,
        corpus=corpus,
        date_str="2026-04-30",
        timestamp="2026-04-30T11:30:00",
    )

    papers_md = project_papers_path(tmp_path, "proj").read_text(encoding="utf-8")
    # The dropped Tier-C paper no longer appears.
    assert "[[10.1038_nature17946" not in papers_md
    # The kept Tier-A paper still does.
    assert "[[10.1126_science.1225829" in papers_md
    # Frontmatter shows v2 topic.
    assert "topic: topic v2" in papers_md
    assert "total_corpus: 1" in papers_md

    # lineage.md points at arc2.
    lineage_md = project_lineage_pointer_path(tmp_path, "proj").read_text(encoding="utf-8")
    assert "[[arc2]]" in lineage_md
    assert "[[arc1]]" not in lineage_md


def test_write_project_view_also_in_populated_when_siblings_share_doi(
    tmp_path: Path,
) -> None:
    """Cross-project 'Also in' col populated when sibling project has same DOI."""
    summaries = _two_summaries()
    corpus = _two_corpus()
    arc_a = tmp_path / "Wiki" / "Concepts" / "arc-a.md"
    arc_a.parent.mkdir(parents=True)
    arc_a.write_text("# a\n", encoding="utf-8")
    arc_b = tmp_path / "Wiki" / "Concepts" / "arc-b.md"
    arc_b.write_text("# b\n", encoding="utf-8")

    # Project A first — written in isolation.
    _write_project_view(
        kb_root=tmp_path,
        project_slug="project-a",
        topic="A topic",
        arc_path=arc_a,
        summaries=summaries,
        corpus=corpus,
        date_str="2026-04-29",
        timestamp="2026-04-29T10:00:00",
    )
    # Project B with overlap — should detect project-a as a sibling.
    _write_project_view(
        kb_root=tmp_path,
        project_slug="project-b",
        topic="B topic",
        arc_path=arc_b,
        summaries=summaries,
        corpus=corpus,
        date_str="2026-04-29",
        timestamp="2026-04-29T11:00:00",
    )

    papers_b = project_papers_path(tmp_path, "project-b").read_text(encoding="utf-8")
    # Tier-A row for Jinek 2012 should now have project-a in "Also in".
    assert "`project-a`" in papers_b
    # Tier-C stub for Komor 2016 doesn't have an Also-in column (not a table).
    # Still: project-a is a sibling and should appear in the membership somewhere.

    # And project-a's papers.md should NOT be auto-updated by writing project-b.
    # (Run project-a's writer again — *now* it should pick up project-b.)
    _write_project_view(
        kb_root=tmp_path,
        project_slug="project-a",
        topic="A topic",
        arc_path=arc_a,
        summaries=summaries,
        corpus=corpus,
        date_str="2026-04-29",
        timestamp="2026-04-29T12:00:00",
    )
    papers_a = project_papers_path(tmp_path, "project-a").read_text(encoding="utf-8")
    assert "`project-b`" in papers_a


def test_write_project_view_excludes_self_from_also_in(tmp_path: Path) -> None:
    """A project never lists itself in its own 'Also in' column."""
    summaries = _two_summaries()
    corpus = _two_corpus()
    arc_p = tmp_path / "Wiki" / "Concepts" / "arc.md"
    arc_p.parent.mkdir(parents=True)
    arc_p.write_text("# arc\n", encoding="utf-8")

    # First write a papers.md — second run should not list "solo" in its own Also-in.
    _write_project_view(
        kb_root=tmp_path,
        project_slug="solo",
        topic="topic",
        arc_path=arc_p,
        summaries=summaries,
        corpus=corpus,
        date_str="2026-04-29",
        timestamp="2026-04-29T10:00:00",
    )
    _write_project_view(
        kb_root=tmp_path,
        project_slug="solo",
        topic="topic",
        arc_path=arc_p,
        summaries=summaries,
        corpus=corpus,
        date_str="2026-04-29",
        timestamp="2026-04-29T11:00:00",
    )
    papers_md = project_papers_path(tmp_path, "solo").read_text(encoding="utf-8")
    assert "`solo`" not in papers_md


# ---------------------------------------------------------------------------
# project_slug parameter on run_lit_arc
# ---------------------------------------------------------------------------


def test_run_lit_arc_uses_topic_derived_slug_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When project_slug is None, the slug is slugify_topic(topic)."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(
        "vaultlab.research.config.get_config",
        lambda *a, **k: {},
    )

    client = _FakeClient(_make_seeds())
    result = run_lit_arc(
        "CODEX cellular neighborhoods",
        kb_root=tmp_path,
        max_seeds=5,
        max_papers_to_summarize=5,
        _client=client,
        _fetch_refs=_fake_fetch_refs,
        _acquire=_fake_acquire,
        _llm_summary=_fake_llm_summary(),
        _today="2026-04-29",
    )
    assert result.project_slug == "codex-cellular-neighborhoods"
    proj_dir = tmp_path / "Wiki" / "Projects" / "codex-cellular-neighborhoods"
    for fname in ("START_HERE.md", "papers.md", "lineage.md", "decisions-log.md"):
        assert (proj_dir / fname).exists(), f"missing {fname}"


def test_run_lit_arc_explicit_project_slug_overrides_topic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Explicit project_slug is used verbatim — even when it differs from topic."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(
        "vaultlab.research.config.get_config",
        lambda *a, **k: {},
    )

    client = _FakeClient(_make_seeds())
    result = run_lit_arc(
        "CODEX cellular neighborhoods",
        kb_root=tmp_path,
        max_seeds=5,
        max_papers_to_summarize=5,
        project_slug="codex-cn-test",
        _client=client,
        _fetch_refs=_fake_fetch_refs,
        _acquire=_fake_acquire,
        _llm_summary=_fake_llm_summary(),
        _today="2026-04-29",
    )
    assert result.project_slug == "codex-cn-test"
    proj_dir = tmp_path / "Wiki" / "Projects" / "codex-cn-test"
    assert (proj_dir / "START_HERE.md").exists()
    assert (proj_dir / "papers.md").exists()
    # The topic-derived slug should NOT have been used.
    other_dir = tmp_path / "Wiki" / "Projects" / "codex-cellular-neighborhoods"
    assert not other_dir.exists()


def test_run_lit_arc_decisions_log_appends_across_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Re-running run_lit_arc with the same project_slug appends to the log."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(
        "vaultlab.research.config.get_config",
        lambda *a, **k: {},
    )

    client = _FakeClient(_make_seeds())
    run_lit_arc(
        "CRISPR base editing",
        kb_root=tmp_path,
        max_seeds=5,
        max_papers_to_summarize=5,
        project_slug="crispr-test",
        _client=client,
        _fetch_refs=_fake_fetch_refs,
        _acquire=_fake_acquire,
        _llm_summary=_fake_llm_summary(),
        _today="2026-04-29",
        _now="2026-04-29T10:00:00",
    )
    run_lit_arc(
        "CRISPR base editing",
        kb_root=tmp_path,
        max_seeds=5,
        max_papers_to_summarize=5,
        project_slug="crispr-test",
        _client=client,
        _fetch_refs=_fake_fetch_refs,
        _acquire=_fake_acquire,
        _llm_summary=_fake_llm_summary(),
        _today="2026-04-30",
        _now="2026-04-30T11:00:00",
    )
    log_md = project_decisions_path(tmp_path, "crispr-test").read_text(encoding="utf-8")
    assert log_md.count("# Decisions log — crispr-test") == 1
    assert "## 2026-04-29T10:00:00 — lit-arc run" in log_md
    assert "## 2026-04-30T11:00:00 — lit-arc run" in log_md


# ---------------------------------------------------------------------------
# Task #63: depth flag (fast / balanced / thorough / complete)
# ---------------------------------------------------------------------------


def _synthetic_seeds(n: int) -> list[Paper]:
    """Build ``n`` synthetic seeds with unique DOIs / years for depth tests."""
    return [
        Paper(
            title=f"Synthetic paper {i}",
            authors=[f"Author{i} I"],
            year=2010 + (i % 15),
            journal="Synth J",
            doi=f"10.9999/synth.{i:03d}",
            citation_count=100 - i,
            source_api="synth",
            abstract=f"Abstract for paper {i}.",
        )
        for i in range(n)
    ]


def _make_fake_acquire(
    n_with_pdf: int | None = None,
    *,
    capture_kwargs: dict | None = None,
):
    """Build a fake acquisition function honouring an explicit PDF-cached count.

    If ``n_with_pdf`` is None, every seed gets a PDF (matches the original
    ``_fake_acquire`` behaviour). Otherwise the first ``n_with_pdf`` corpus
    DOIs (sorted) get PDFs and the rest are marked failed.
    """

    def _acq(corpus, cache_dir, **kwargs):
        if capture_kwargs is not None:
            capture_kwargs.update(kwargs)
        from vaultlab.research.acquisition import cache_path_for

        cache_dir = Path(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        out: dict[str, AcquisitionResult] = {}
        dois = sorted(corpus.papers.keys())
        cap = len(dois) if n_with_pdf is None else min(n_with_pdf, len(dois))
        for i, doi in enumerate(dois):
            target = cache_path_for(doi, cache_dir)
            if i < cap:
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
                    error="paywalled",
                )
        return out

    return _acq


# ---- _derive_max_papers (pure helper) ------------------------------------


def test_derive_max_papers_fast_caps_at_20() -> None:
    assert _derive_max_papers("fast", n_pdfs_cached=80, corpus_size=100) == 20
    assert _derive_max_papers("fast", n_pdfs_cached=10, corpus_size=100) == 10


def test_derive_max_papers_balanced_caps_at_50() -> None:
    assert _derive_max_papers("balanced", n_pdfs_cached=80, corpus_size=100) == 50
    assert _derive_max_papers("balanced", n_pdfs_cached=30, corpus_size=100) == 30


def test_derive_max_papers_thorough_uses_all_pdfs() -> None:
    assert _derive_max_papers("thorough", n_pdfs_cached=25, corpus_size=30) == 25
    assert _derive_max_papers("thorough", n_pdfs_cached=200, corpus_size=378) == 200


def test_derive_max_papers_complete_uses_all_pdfs() -> None:
    # ``complete`` uses cached count post-retry; the retry happens at
    # acquisition time, so by the time _derive_max_papers is called the
    # input already reflects retried PDFs.
    assert _derive_max_papers("complete", n_pdfs_cached=42, corpus_size=378) == 42


def test_derive_max_papers_rejects_unknown_depth() -> None:
    with pytest.raises(ValueError, match="unknown depth"):
        _derive_max_papers("aggressive", n_pdfs_cached=10, corpus_size=10)  # type: ignore[arg-type]


# ---- run_lit_arc end-to-end (depth flag wiring) --------------------------


def test_run_lit_arc_depth_fast_caps_at_20(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Synthetic 100-paper corpus, depth=fast → 20-paper Tier-A budget."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(
        "vaultlab.research.config.get_config", lambda *a, **k: {}
    )
    seeds = _synthetic_seeds(100)
    client = _FakeClient(seeds)
    events: list[tuple[str, dict]] = []

    def _progress(*args, **kwargs):
        events.append((args[0] if args else "", dict(kwargs)))

    result = run_lit_arc(
        "synthetic-fast",
        kb_root=tmp_path,
        depth="fast",
        max_seeds=100,
        _client=client,
        _fetch_refs=lambda doi: [],  # no refs walk
        _acquire=_make_fake_acquire(),  # all 100 get PDFs
        _llm_summary=_fake_llm_summary(),
        progress=_progress,
        _today="2026-04-30",
    )
    # The orchestrator emitted the depth_budget event with budget=20.
    budget_events = [
        kw for tag, kw in events if tag == "depth_budget"
    ]
    assert budget_events, "depth_budget event was not emitted"
    assert budget_events[0]["depth"] == "fast"
    assert budget_events[0]["budget"] == 20
    # Provenance reflects the resolved budget.
    json_p = result.arc_path.with_name(
        result.arc_path.name + ".provenance.json"
    )
    rec = json.loads(json_p.read_text(encoding="utf-8"))
    assert rec["params"]["depth"] == "fast"
    assert rec["params"]["max_papers_to_summarize"] == 20
    assert rec["params"]["max_papers_to_summarize_explicit"] is None


def test_run_lit_arc_depth_balanced_caps_at_50(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Synthetic 100-paper corpus, depth=balanced → 50-paper Tier-A budget."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(
        "vaultlab.research.config.get_config", lambda *a, **k: {}
    )
    seeds = _synthetic_seeds(100)
    client = _FakeClient(seeds)
    events: list[tuple[str, dict]] = []

    def _progress(*args, **kwargs):
        events.append((args[0] if args else "", dict(kwargs)))

    result = run_lit_arc(
        "synthetic-balanced",
        kb_root=tmp_path,
        depth="balanced",
        max_seeds=100,
        _client=client,
        _fetch_refs=lambda doi: [],
        _acquire=_make_fake_acquire(),
        _llm_summary=_fake_llm_summary(),
        progress=_progress,
        _today="2026-04-30",
    )
    budget_events = [kw for tag, kw in events if tag == "depth_budget"]
    assert budget_events
    assert budget_events[0]["depth"] == "balanced"
    assert budget_events[0]["budget"] == 50
    json_p = result.arc_path.with_name(
        result.arc_path.name + ".provenance.json"
    )
    rec = json.loads(json_p.read_text(encoding="utf-8"))
    assert rec["params"]["max_papers_to_summarize"] == 50


def test_run_lit_arc_depth_thorough_uses_all_cached_pdfs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """30-paper corpus with 25 PDFs cached, depth=thorough → budget=25."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(
        "vaultlab.research.config.get_config", lambda *a, **k: {}
    )
    seeds = _synthetic_seeds(30)
    client = _FakeClient(seeds)
    events: list[tuple[str, dict]] = []

    def _progress(*args, **kwargs):
        events.append((args[0] if args else "", dict(kwargs)))

    result = run_lit_arc(
        "synthetic-thorough",
        kb_root=tmp_path,
        depth="thorough",
        max_seeds=30,
        _client=client,
        _fetch_refs=lambda doi: [],
        _acquire=_make_fake_acquire(n_with_pdf=25),
        _llm_summary=_fake_llm_summary(),
        progress=_progress,
        _today="2026-04-30",
    )
    budget_events = [kw for tag, kw in events if tag == "depth_budget"]
    assert budget_events
    assert budget_events[0]["depth"] == "thorough"
    assert budget_events[0]["budget"] == 25
    assert budget_events[0]["n_pdfs_cached"] == 25
    assert result.pdfs_acquired == 25


def test_run_lit_arc_explicit_max_papers_overrides_depth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """depth=fast + explicit max_papers_to_summarize=100 → uses 100, not 20."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(
        "vaultlab.research.config.get_config", lambda *a, **k: {}
    )
    seeds = _synthetic_seeds(100)
    client = _FakeClient(seeds)
    events: list[tuple[str, dict]] = []

    def _progress(*args, **kwargs):
        events.append((args[0] if args else "", dict(kwargs)))

    result = run_lit_arc(
        "synthetic-explicit",
        kb_root=tmp_path,
        depth="fast",
        max_seeds=100,
        max_papers_to_summarize=100,  # explicit override beats depth=fast cap
        _client=client,
        _fetch_refs=lambda doi: [],
        _acquire=_make_fake_acquire(),
        _llm_summary=_fake_llm_summary(),
        progress=_progress,
        _today="2026-04-30",
    )
    # Explicit override -> no depth_budget event (we skip the derivation).
    assert not any(tag == "depth_budget" for tag, _ in events)
    json_p = result.arc_path.with_name(
        result.arc_path.name + ".provenance.json"
    )
    rec = json.loads(json_p.read_text(encoding="utf-8"))
    assert rec["params"]["max_papers_to_summarize"] == 100
    assert rec["params"]["max_papers_to_summarize_explicit"] == 100


def test_run_lit_arc_complete_passes_aggressive_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """depth=complete forwards aggressive_retry=True to acquisition."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(
        "vaultlab.research.config.get_config", lambda *a, **k: {}
    )
    seeds = _synthetic_seeds(10)
    client = _FakeClient(seeds)
    captured: dict = {}
    fake_acq = _make_fake_acquire(capture_kwargs=captured)

    run_lit_arc(
        "synthetic-complete",
        kb_root=tmp_path,
        depth="complete",
        max_seeds=10,
        _client=client,
        _fetch_refs=lambda doi: [],
        _acquire=fake_acq,
        _llm_summary=_fake_llm_summary(),
        _today="2026-04-30",
    )
    # complete -> aggressive_retry=True AND skip_paywalled=False
    assert captured.get("aggressive_retry") is True
    assert captured.get("skip_paywalled") is False


def test_run_lit_arc_balanced_does_not_set_aggressive_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Default depth keeps the OA-only fast path (aggressive_retry=False)."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(
        "vaultlab.research.config.get_config", lambda *a, **k: {}
    )
    seeds = _synthetic_seeds(5)
    client = _FakeClient(seeds)
    captured: dict = {}
    fake_acq = _make_fake_acquire(capture_kwargs=captured)

    run_lit_arc(
        "synthetic-balanced-default",
        kb_root=tmp_path,
        max_seeds=5,
        _client=client,
        _fetch_refs=lambda doi: [],
        _acquire=fake_acq,
        _llm_summary=_fake_llm_summary(),
        _today="2026-04-30",
    )
    assert captured.get("aggressive_retry") is False
    assert captured.get("skip_paywalled") is True


def test_run_lit_arc_rejects_unknown_depth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bad depth string fails fast with a clear error."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(
        "vaultlab.research.config.get_config", lambda *a, **k: {}
    )
    client = _FakeClient(_make_seeds())
    with pytest.raises(ValueError, match="unknown depth"):
        run_lit_arc(
            "CRISPR base editing",
            kb_root=tmp_path,
            depth="aggressive",  # type: ignore[arg-type]
            max_seeds=5,
            _client=client,
            _fetch_refs=_fake_fetch_refs,
            _acquire=_fake_acquire,
            _llm_summary=_fake_llm_summary(),
            _today="2026-04-30",
        )


def test_run_lit_arc_thorough_warns_on_large_corpus(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """thorough on a >200 paper corpus emits a wall-time warning + progress event."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(
        "vaultlab.research.config.get_config", lambda *a, **k: {}
    )
    # 250-paper synthetic corpus crosses the 200-paper threshold.
    seeds = _synthetic_seeds(250)
    client = _FakeClient(seeds)
    events: list[tuple[str, dict]] = []

    def _progress(*args, **kwargs):
        events.append((args[0] if args else "", dict(kwargs)))

    with caplog.at_level("WARNING"):
        run_lit_arc(
            "synthetic-thorough-big",
            kb_root=tmp_path,
            depth="thorough",
            max_seeds=250,
            _client=client,
            _fetch_refs=lambda doi: [],
            _acquire=_make_fake_acquire(),
            _llm_summary=_fake_llm_summary(),
            progress=_progress,
            _today="2026-04-30",
        )
    # Warning logged + event emitted.
    assert any(
        "depth=thorough" in r.message and "250-paper" in r.message
        for r in caplog.records
    )
    assert any(tag == "large_corpus_warning" for tag, _ in events)


# ---------------------------------------------------------------------------
# Adversarial crosstalk integration (picker_mode / arc_mode = "adversarial")
# ---------------------------------------------------------------------------


def test_run_lit_arc_with_adversarial_picker_and_arc(tmp_path, monkeypatch):
    """When picker_mode=arc_mode='adversarial' + crosstalk_runner is set,
    the adversarial wrappers fire; the arc and project view reflect that.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(
        "vaultlab.research.config.get_config",
        lambda *a, **k: {},
    )

    def _reader(task):
        return {
            "tldr": f"reader-{task.doi}.",
            "why_it_matters": ["x"],
            "methods_summary": "m",
            "key_findings": ["a [p1]", "b [p2]", "c [p3]"],
            "extracted_references": [],
        }

    # Crosstalk runner that returns canned analyst/critic/synthesizer outputs.
    # Synthesizer payload differs depending on whether it's a picker or arc
    # meeting (we sniff via the agenda statement).
    seeds_dois = ["10.1126/science.1225829", "10.1038/nature17946"]

    def _crosstalk(meeting, roles):
        outputs = []
        agenda_text = (meeting.agenda.statement if meeting.agenda else "") or ""
        for r in roles:
            if r.id == "synthesizer":
                if "BEST papers" in agenda_text:
                    payload = {
                        "picks": [
                            {"doi": d, "rank": i + 1, "rationale": "x"}
                            for i, d in enumerate(seeds_dois)
                        ]
                    }
                else:
                    payload = {
                        "history": "Adversarial history.",
                        "development": "Adversarial dev.",
                        "sota": "Adversarial sota.",
                    }
                outputs.append({"output": json.dumps(payload)})
            else:
                outputs.append({"output": f"[{r.id}]"})
        return outputs

    client = _FakeClient(_make_seeds())
    result = run_lit_arc(
        "CRISPR base editing",
        kb_root=tmp_path,
        max_seeds=3,
        max_papers_to_summarize=2,
        _client=client,
        _fetch_refs=_fake_fetch_refs,
        _acquire=_fake_acquire,
        reader=_reader,
        picker_mode="adversarial",
        arc_mode="adversarial",
        crosstalk_runner=_crosstalk,
        crosstalk_n_rounds=2,
        _today="2026-04-30",
    )

    md = result.arc_path.read_text(encoding="utf-8")
    assert "Adversarial history." in md
    assert "Adversarial dev." in md
    # Decisions log should record the adversarial crosstalk descriptor.
    decisions = result.project_view_paths["decisions_log"].read_text(encoding="utf-8")
    assert "picker:adversarial" in decisions
    assert "arc:adversarial" in decisions
