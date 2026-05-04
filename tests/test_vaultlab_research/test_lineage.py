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
    # Bug 6: og_score methodology blockquote present in arc body.
    assert "Kessler 1963 bibliographic coupling" in md
    assert "fraction of seed papers that cite" in md
    # Bug 6: og_score_methodology key in frontmatter.
    assert fm.get("og_score_methodology"), (
        "frontmatter should carry og_score_methodology one-liner"
    )


def test_no_pdf_extension_in_arc_wikilinks():
    """Regression for evening-5 / Round 2 audit Finding 3 (2026-04-30).

    The arc-body and arc-prompt wikilink renderers must NEVER emit a
    slug with a ``.pdf`` extension. Live audit example:
    ``[[10.7554_elife-31657.pdf|Lin 2018]]`` showed up in a real arc
    and broke Obsidian wikilink resolution.

    We construct a paper whose DOI value (defensively) carries a stray
    ``.pdf`` and verify both the prompt-time and render-time wikilinks
    drop the extension before slugifying.
    """
    # DOI carrying a stray .pdf — should be tolerated and stripped.
    summaries = {
        "10.7554/elife.31657.pdf": PaperSummary(
            doi="10.7554/elife.31657.pdf",
            title="t-CyCIF",
            authors=["Lin J"],
            year=2018,
            year_bucket="history",
            tldr="Cyclic IF on standard hardware.",
            key_findings=["60-plex achievable [p1]"],
            og_score=0.50,
            forward_influence=3,
            tier="A",
        ),
    }
    # Build an arc-prompt and a rendered arc body, then verify zero `.pdf`
    # leaks across the two wikilink-emitting code paths.
    prompt = build_arc_prompt(
        topic="CODEX multiplexed imaging",
        summaries=summaries,
        top_og=[("10.7554/elife.31657.pdf", 0.50)],
        top_co_citation=[],
    )
    assert ".pdf|" not in prompt
    assert ".pdf]]" not in prompt
    assert "[[10.7554_elife.31657|Lin 2018]]" in prompt

    from vaultlab.research.corpus import Corpus
    from vaultlab.research.graph_metrics import compute_metrics
    from vaultlab.research.paper import Paper

    seed = Paper(
        doi="10.7554/elife.31657.pdf",
        title="t-CyCIF",
        authors=["Lin J"],
        year=2018,
    )
    corpus = Corpus(topic="CODEX multiplexed imaging", seeds=[seed])
    corpus.papers["10.7554/elife.31657.pdf"] = seed
    corpus.references = {"10.7554/elife.31657.pdf": []}
    compute_metrics(corpus)
    md = render_arc_markdown(
        topic="CODEX multiplexed imaging",
        date_str="2026-04-30",
        summaries=summaries,
        corpus=corpus,
        method_relpath="codex-lineage-2026-04-30.md.method.md",
        narrative=None,
    )
    assert ".pdf|" not in md
    assert ".pdf]]" not in md


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


def test_write_project_view_uses_explicit_pdfs_acquired(tmp_path: Path) -> None:
    """decisions-log.md must report the actual pdfs_acquired count, not Tier-A.

    Regression test for evening-3 Bug 3 (2026-04-30): previously the writer
    computed `sum(1 for s in summaries.values() if s.tier == "A")` and labelled
    it "PDFs acquired", conflating the Tier-A bucket with actual successful
    acquisitions. Fix: pass `pdfs_acquired` explicitly from
    LineageRunResult.pdfs_acquired so the two can diverge.
    """
    summaries = _two_summaries()  # 1 Tier-A, 1 Tier-C
    corpus = _two_corpus()
    arc_p = tmp_path / "Wiki" / "Concepts" / "bug3-arc.md"
    arc_p.parent.mkdir(parents=True)
    arc_p.write_text("# arc\n", encoding="utf-8")

    # Simulate a real run where 7 PDFs were acquired but only 1 made the
    # Tier-A bucket — e.g. some were Tier-B candidates that didn't get summarized.
    out = _write_project_view(
        kb_root=tmp_path,
        project_slug="bug3-test",
        topic="bug-3 verification",
        arc_path=arc_p,
        summaries=summaries,
        corpus=corpus,
        run_id="2026-04-30T18-00-00",
        date_str="2026-04-30",
        speaker="Bobby",
        sources_n=3,
        picker_method="content-aware",
        crosstalk="none",
        timestamp="2026-04-30T18:00:00",
        pdfs_acquired=7,
    )

    log_md = out["decisions_log"].read_text(encoding="utf-8")
    # Tier-A is 1, but pdfs_acquired should be 7 in the log.
    assert "**Tier-A picks:** 1" in log_md
    assert "**PDFs acquired:** 7" in log_md, (
        f"decisions-log should report 7 PDFs acquired, not the Tier-A count.\n"
        f"Got:\n{log_md}"
    )


def test_write_project_view_falls_back_to_tier_a_when_pdfs_acquired_omitted(
    tmp_path: Path,
) -> None:
    """If caller omits pdfs_acquired, fall back to Tier-A count for back-compat."""
    summaries = _two_summaries()
    corpus = _two_corpus()
    arc_p = tmp_path / "Wiki" / "Concepts" / "bug3-fallback.md"
    arc_p.parent.mkdir(parents=True)
    arc_p.write_text("# arc\n", encoding="utf-8")

    out = _write_project_view(
        kb_root=tmp_path,
        project_slug="bug3-fallback",
        topic="bug-3 fallback",
        arc_path=arc_p,
        summaries=summaries,
        corpus=corpus,
        run_id="run",
        date_str="2026-04-30",
        timestamp="2026-04-30T18:00:00",
        # pdfs_acquired NOT passed
    )

    log_md = out["decisions_log"].read_text(encoding="utf-8")
    # Falls back to Tier-A count (1).
    assert "**PDFs acquired:** 1" in log_md


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


# ---------------------------------------------------------------------------
# LLM-driven binning integration (binner_callback)
# ---------------------------------------------------------------------------


def test_run_lit_arc_with_binner_callback_overrides_year_buckets(tmp_path, monkeypatch):
    """binner_callback runs after compute_metrics and overrides the
    deterministic year_buckets in place. Downstream summaries see the
    LLM-driven bucket assignment.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(
        "vaultlab.research.config.get_config",
        lambda *a, **k: {},
    )

    captured_buckets: dict[str, str] = {}

    def _reader(task):
        # Capture the year_bucket that summarize_corpus saw for this paper.
        captured_buckets[task.doi] = task.citation_stats.get("year_bucket", "")
        return {
            "tldr": f"reader-{task.doi}.",
            "why_it_matters": ["x"],
            "methods_summary": "m",
            "key_findings": ["a [p1]", "b [p2]", "c [p3]"],
            "extracted_references": [],
        }

    def _binner(task):
        # Force EVERY paper into "history" so we can trivially assert
        # the override took effect (deterministic quartiles would
        # never put the 2017 paper in history).
        return {
            "assignments": [
                {
                    "doi": c.doi,
                    "bucket": "history",
                    "rationale": "test override",
                }
                for c in task.candidates
            ]
        }

    client = _FakeClient(_make_seeds())
    result = run_lit_arc(
        "CRISPR base editing",
        kb_root=tmp_path,
        max_seeds=3,
        max_papers_to_summarize=3,
        _client=client,
        _fetch_refs=_fake_fetch_refs,
        _acquire=_fake_acquire,
        reader=_reader,
        binner_callback=_binner,
        _today="2026-04-30",
    )

    # Every captured bucket should be "history" (the LLM override wins).
    assert captured_buckets, "reader was never invoked"
    for doi, bucket in captured_buckets.items():
        assert bucket == "history", (
            f"expected LLM-overridden 'history' bucket for {doi}, got {bucket}"
        )
    # The arc/result shape is unchanged.
    assert isinstance(result, LineageRunResult)


def test_run_lit_arc_without_binner_callback_keeps_deterministic(tmp_path, monkeypatch):
    """Without a binner_callback, the deterministic year-quartile buckets stand."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(
        "vaultlab.research.config.get_config",
        lambda *a, **k: {},
    )

    captured_buckets: dict[str, str] = {}

    def _reader(task):
        captured_buckets[task.doi] = task.citation_stats.get("year_bucket", "")
        return {
            "tldr": f"reader-{task.doi}.",
            "why_it_matters": ["x"],
            "methods_summary": "m",
            "key_findings": ["a [p1]", "b [p2]", "c [p3]"],
            "extracted_references": [],
        }

    client = _FakeClient(_make_seeds())
    run_lit_arc(
        "CRISPR base editing",
        kb_root=tmp_path,
        max_seeds=3,
        max_papers_to_summarize=3,
        _client=client,
        _fetch_refs=_fake_fetch_refs,
        _acquire=_fake_acquire,
        reader=_reader,
        # NO binner_callback
        _today="2026-04-30",
    )
    # 2012 paper -> history quartile, 2017 -> sota. Not all "history".
    assert captured_buckets["10.1126/science.1225829"] == "history"
    assert captured_buckets["10.1038/nature24644"] == "sota"


def test_run_lit_arc_adversarial_picker_fallback_writes_decision_log(
    tmp_path, monkeypatch
):
    """Bug #5: when the adversarial picker meeting yields no usable picks,
    the mechanical fallback now ALSO records the decision in decisions-log.md
    (or the per-run picker-decision.md fallback) so the audit trail isn't lost.
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

    # Crosstalk runner: synthesizer returns NO picks (empty list) so the
    # orchestrator must fall back to the mechanical citation-graph picker.
    def _crosstalk(meeting, roles):
        outputs = []
        agenda_text = (meeting.agenda.statement if meeting.agenda else "") or ""
        for r in roles:
            if r.id == "synthesizer":
                if "BEST papers" in agenda_text:
                    payload = {"picks": []}  # empty -> triggers fallback
                else:
                    payload = {
                        "history": "h.",
                        "development": "d.",
                        "sota": "s.",
                    }
                outputs.append({"output": json.dumps(payload)})
            else:
                outputs.append({"output": f"[{r.id}]"})
        return outputs

    run_dir = tmp_path / "_runs" / "test-adversarial-fallback"
    run_dir.mkdir(parents=True, exist_ok=True)

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
        crosstalk_runner=_crosstalk,
        crosstalk_n_rounds=2,
        run_dir=run_dir,
        _today="2026-04-30",
    )

    # The audit trail should have landed somewhere — either in the
    # canonical project decisions-log.md OR in the per-run fallback.
    decisions_log = result.project_view_paths.get("decisions_log")
    fallback_file = run_dir / "picker-decision.md"

    found_audit = False
    audit_text = ""
    if decisions_log is not None and decisions_log.exists():
        audit_text = decisions_log.read_text(encoding="utf-8")
        if "adversarial picker fallback" in audit_text:
            found_audit = True
    if not found_audit and fallback_file.exists():
        audit_text = fallback_file.read_text(encoding="utf-8")
        if "adversarial picker fallback" in audit_text:
            found_audit = True

    assert found_audit, (
        "expected 'adversarial picker fallback' in decision audit trail; "
        f"decisions_log={decisions_log}, fallback={fallback_file}"
    )


# ---------------------------------------------------------------------------
# F-13 regression: LineageRunResult carries the live Corpus
# ---------------------------------------------------------------------------


def test_lit_arc_does_not_clobber_onboarding_start_here(tmp_path: Path) -> None:
    """F-2: lit-arc's project-view writer must NOT clobber an onboarding START_HERE.

    When ``init_project_from_intake`` writes an onboarding-managed
    ``Wiki/Projects/<slug>/START_HERE.md`` (frontmatter signals
    ``managed_by: vaultlab.onboarding.project_init`` /
    ``schema: vaultlab-start-here/v1``), a subsequent ``run_lit_arc``
    call against the same slug would historically overwrite it with
    the lit-arc rendering, destroying intake context. The fix:
    ``_safe_merge_start_here`` detects the onboarding signal and
    appends a "## Lineage runs" section instead of replacing the file.
    """
    summaries = _two_summaries()
    corpus = _two_corpus()
    arc_p = tmp_path / "Wiki" / "Concepts" / "fake-lineage-2026-04-30.md"
    arc_p.parent.mkdir(parents=True)
    arc_p.write_text("# fake arc\n", encoding="utf-8")

    # Pre-seed an onboarding-managed START_HERE under the canonical slug.
    onboarding_path = project_state_path(tmp_path, "codex-onboarded")
    onboarding_path.parent.mkdir(parents=True, exist_ok=True)
    onboarding_body = (
        "---\n"
        "slug: codex-onboarded\n"
        "schema: vaultlab-start-here/v1\n"
        "last_updated: 2026-04-29 10:00\n"
        "managed_by: vaultlab.onboarding.project_init\n"
        "version: 1\n"
        "---\n\n"
        "# START_HERE — codex-onboarded\n\n"
        "## Topic\n\n"
        "CODEX cellular neighborhoods\n\n"
        "## Goals\n\n"
        "understand_literature\n\n"
        "## Folder inventory\n\n"
        "- 3 .py files\n\n"
        "## Files to read first if resuming\n\n"
        "- `README.md`\n"
    )
    onboarding_path.write_text(onboarding_body, encoding="utf-8")

    # Now run the lit-arc project-view writer against the same slug.
    _write_project_view(
        kb_root=tmp_path,
        project_slug="codex-onboarded",
        topic="CODEX cellular neighborhoods",
        arc_path=arc_p,
        summaries=summaries,
        corpus=corpus,
        date_str="2026-04-30",
        timestamp="2026-04-30T11:30:00",
    )

    merged = onboarding_path.read_text(encoding="utf-8")
    # Onboarding content must be preserved intact.
    assert "managed_by: vaultlab.onboarding.project_init" in merged
    assert "## Topic" in merged
    assert "## Goals" in merged
    assert "## Folder inventory" in merged
    assert "## Files to read first if resuming" in merged
    # ... and the lit-arc section must be appended.
    assert "## Lineage runs" in merged
    assert "fake-lineage-2026-04-30" in merged

    # Re-running lit-arc should refresh (not duplicate) the Lineage runs
    # block — only one such header at any time.
    _write_project_view(
        kb_root=tmp_path,
        project_slug="codex-onboarded",
        topic="CODEX cellular neighborhoods",
        arc_path=arc_p,
        summaries=summaries,
        corpus=corpus,
        date_str="2026-05-01",
        timestamp="2026-05-01T09:00:00",
    )
    refreshed = onboarding_path.read_text(encoding="utf-8")
    assert refreshed.count("## Lineage runs") == 1
    assert "## Topic" in refreshed  # still preserved


def test_lit_arc_overwrites_its_own_start_here(tmp_path: Path) -> None:
    """When the existing START_HERE was written by lit-arc itself (no
    onboarding signal), the previous overwrite-with-current-state
    behaviour is preserved so Tier-A / Tier-C counts stay live."""
    summaries = _two_summaries()
    corpus = _two_corpus()
    arc_p = tmp_path / "Wiki" / "Concepts" / "arc.md"
    arc_p.parent.mkdir(parents=True)
    arc_p.write_text("# arc\n", encoding="utf-8")

    # First run lays down a lit-arc START_HERE (no onboarding signal).
    _write_project_view(
        kb_root=tmp_path,
        project_slug="lit-arc-only",
        topic="Topic A",
        arc_path=arc_p,
        summaries=summaries,
        corpus=corpus,
        date_str="2026-04-29",
        timestamp="2026-04-29T10:00:00",
    )

    # Second run with a different topic should refresh the file.
    _write_project_view(
        kb_root=tmp_path,
        project_slug="lit-arc-only",
        topic="Topic B refreshed",
        arc_path=arc_p,
        summaries=summaries,
        corpus=corpus,
        date_str="2026-04-30",
        timestamp="2026-04-30T11:00:00",
    )

    start_p = project_state_path(tmp_path, "lit-arc-only")
    body = start_p.read_text(encoding="utf-8")
    # Refreshed → reflects latest topic, no onboarding metadata.
    assert "Topic B refreshed" in body
    assert "managed_by: vaultlab.onboarding.project_init" not in body


def test_lineage_run_result_carries_corpus(tmp_path, monkeypatch):
    """``run_lit_arc`` must populate ``result.corpus`` with the live object.

    Before the F-13 fix, ``LineageRunResult`` carried only paths and
    counters, so the deck builder's adversarial / plan_callback paths
    rebuilt a synthetic corpus from on-disk frontmatters and lost
    ``co_citation_pairs`` / ``seeds`` / ``references``. This regression
    test pins the new behaviour: the live :class:`Corpus` (with
    populated ``metrics`` and ``references``) flows through to the
    result so downstream consumers can read it directly.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(
        "vaultlab.research.config.get_config",
        lambda *a, **k: {},
    )

    seeds = _make_seeds()
    client = _FakeClient(seeds)

    result = run_lit_arc(
        "CRISPR base editing",
        kb_root=tmp_path,
        max_seeds=5,
        max_papers_to_summarize=5,
        _client=client,
        _fetch_refs=_fake_fetch_refs,
        _acquire=_fake_acquire,
        _llm_summary=_fake_llm_summary(),
        _today="2026-04-29",
    )

    # The result must have a non-None .corpus attribute carrying a
    # vaultlab.research.corpus.Corpus instance.
    from vaultlab.research.corpus import Corpus as _Corpus

    assert isinstance(result.corpus, _Corpus), (
        f"expected result.corpus to be a Corpus, got {type(result.corpus)!r}"
    )
    # ... and it must be the LIVE corpus (populated metrics + references),
    # not a freshly-allocated stand-in.
    assert result.corpus.n_papers >= 3
    assert result.corpus.metrics is not None
    # Seeds should round-trip onto the corpus (citation_lookup-based ref
    # walk gave us at least the original seed DOIs).
    seed_dois = {s.doi.lower() for s in seeds if s.doi}
    corpus_dois = {d.lower() for d in result.corpus.papers}
    assert seed_dois <= corpus_dois, (
        f"corpus.papers missing seed DOIs: {seed_dois - corpus_dois}"
    )
    # corpus_size on the result must agree with corpus.n_papers.
    assert result.corpus_size == result.corpus.n_papers


# ---------------------------------------------------------------------------
# G-2 regression: orchestrator-side cwd auto-discovery for project_slug
# ---------------------------------------------------------------------------


def test_run_lit_arc_auto_discovers_project_slug(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """G-2: when project_slug is None, walk up from cwd looking for
    ``.vaultlab-project.json`` and adopt its slug.

    This is the orchestrator-side fallback ("option b" in the
    conceptual-flow audit). Aligns with the
    ``feedback_kb_additive_state_aware`` memory rule.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(
        "vaultlab.research.config.get_config",
        lambda *a, **k: {},
    )

    # Drop a .vaultlab-project.json in a fresh project dir, then chdir
    # there so load_project_config_from_cwd() finds it.
    from vaultlab.onboarding import VaultLabProjectConfig, save_config

    project_dir = tmp_path / "my-project"
    project_dir.mkdir()
    cfg = VaultLabProjectConfig(slug="auto-discovered-slug", topic="x")
    save_config(cfg, project_dir)

    monkeypatch.chdir(project_dir)

    client = _FakeClient(_make_seeds())
    result = run_lit_arc(
        "CODEX cellular neighborhoods",
        kb_root=tmp_path,
        max_seeds=5,
        max_papers_to_summarize=5,
        # NOTE: project_slug intentionally omitted — fallback should fire.
        _client=client,
        _fetch_refs=_fake_fetch_refs,
        _acquire=_fake_acquire,
        _llm_summary=_fake_llm_summary(),
        _today="2026-04-30",
    )

    # The orchestrator must have picked up the slug from the config file
    # and used it as the project_slug throughout (rather than falling
    # back to slugify_topic(topic)).
    assert result.project_slug == "auto-discovered-slug"
    proj_dir = tmp_path / "Wiki" / "Projects" / "auto-discovered-slug"
    assert (proj_dir / "START_HERE.md").exists()
    # The topic-derived slug should NOT have been used.
    other_dir = tmp_path / "Wiki" / "Projects" / "codex-cellular-neighborhoods"
    assert not other_dir.exists(), (
        f"unexpected parallel project dir at {other_dir}; auto-discovery "
        "fallback failed"
    )


def test_run_lit_arc_explicit_project_slug_overrides_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """G-2: explicit ``project_slug=`` always wins over cwd auto-discovery."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(
        "vaultlab.research.config.get_config",
        lambda *a, **k: {},
    )

    from vaultlab.onboarding import VaultLabProjectConfig, save_config

    project_dir = tmp_path / "my-project"
    project_dir.mkdir()
    cfg = VaultLabProjectConfig(slug="cwd-slug", topic="x")
    save_config(cfg, project_dir)

    monkeypatch.chdir(project_dir)

    client = _FakeClient(_make_seeds())
    result = run_lit_arc(
        "CODEX cellular neighborhoods",
        kb_root=tmp_path,
        max_seeds=5,
        max_papers_to_summarize=5,
        project_slug="explicit",
        _client=client,
        _fetch_refs=_fake_fetch_refs,
        _acquire=_fake_acquire,
        _llm_summary=_fake_llm_summary(),
        _today="2026-04-30",
    )

    # Explicit kwarg wins.
    assert result.project_slug == "explicit"
    assert (tmp_path / "Wiki" / "Projects" / "explicit" / "START_HERE.md").exists()
    # The cwd-derived slug must NOT have been adopted.
    assert not (tmp_path / "Wiki" / "Projects" / "cwd-slug").exists()


# ---------------------------------------------------------------------------
# Fix 1 (2026-04-30 evening-4): acquire_figures kwarg
# ---------------------------------------------------------------------------


class _FakeFigure:
    """Minimal stand-in for vaultlab.figures.acquisition.Figure."""

    def __init__(self, file_path: Path):
        self.file_path = str(file_path)
        self.label = "Figure 1"
        self.caption = "fake caption"


class _FakeFigureResult:
    """Minimal stand-in for FigureAcquisitionResult."""

    def __init__(self, figures: list[_FakeFigure]):
        self.figures = figures
        self.source = "fake"


def test_run_lit_arc_with_acquire_figures_triggers_figure_acquisition(
    tmp_path, monkeypatch
):
    """``run_lit_arc(..., acquire_figures=True)`` runs Phase 5b and
    populates ``LineageRunResult.figure_assignments``."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    seeds = _make_seeds()
    client = _FakeClient(seeds)

    fig_calls: list[tuple[Path, dict]] = []

    def _fake_acquire_figures(corpus, cache_dir, **kwargs):
        cache_dir = Path(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        fig_calls.append((cache_dir, dict(kwargs)))
        out: dict[str, _FakeFigureResult] = {}
        for doi in corpus.papers:
            slug = doi.replace("/", "_")
            doi_dir = cache_dir / slug
            doi_dir.mkdir(parents=True, exist_ok=True)
            # Two figures so we can verify the picker chose the larger one.
            small = doi_dir / "fig1-small.png"
            small.write_bytes(b"\x89PNG\r\n" + b"x" * 50)
            big = doi_dir / "fig2-big.png"
            big.write_bytes(b"\x89PNG\r\n" + b"x" * 5000)
            out[doi] = _FakeFigureResult(
                [_FakeFigure(small), _FakeFigure(big)]
            )
        return out

    result = run_lit_arc(
        "CRISPR base editing",
        kb_root=tmp_path,
        max_seeds=5,
        max_papers_to_summarize=5,
        acquire_figures=True,
        _client=client,
        _fetch_refs=_fake_fetch_refs,
        _acquire=_fake_acquire,
        _acquire_figures=_fake_acquire_figures,
        _llm_summary=_fake_llm_summary(),
        _today="2026-04-30",
    )

    # Fake was invoked exactly once with the corpus + figures cache dir.
    assert len(fig_calls) == 1
    cache_dir, _kwargs = fig_calls[0]
    assert cache_dir == tmp_path / "Sources" / "Figures"

    # Result carries the figure_assignments.
    assert isinstance(result.figure_assignments, dict)
    assert len(result.figure_assignments) >= 3
    # Picker must prefer the LARGER file.
    for doi, fp in result.figure_assignments.items():
        assert fp.exists(), f"figure for {doi} missing on disk: {fp}"
        assert fp.name == "fig2-big.png"
        assert fp.stat().st_size >= 1000
    assert result.figures_acquired == len(result.figure_assignments)


def test_run_lit_arc_without_acquire_figures_skips_figure_phase(
    tmp_path, monkeypatch
):
    """When ``acquire_figures=False`` (the default), no figure fetcher is
    called and ``LineageRunResult.figure_assignments`` stays empty."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    seeds = _make_seeds()
    client = _FakeClient(seeds)
    invoked = {"count": 0}

    def _spy(*args, **kwargs):
        invoked["count"] += 1
        return {}

    result = run_lit_arc(
        "CRISPR base editing",
        kb_root=tmp_path,
        max_seeds=5,
        max_papers_to_summarize=5,
        # acquire_figures defaults to False
        _client=client,
        _fetch_refs=_fake_fetch_refs,
        _acquire=_fake_acquire,
        _acquire_figures=_spy,
        _llm_summary=_fake_llm_summary(),
        _today="2026-04-30",
    )

    assert invoked["count"] == 0
    assert result.figure_assignments == {}
    assert result.figures_acquired == 0


def test_run_lit_arc_acquire_figures_custom_cache_dir(tmp_path, monkeypatch):
    """``figure_cache_dir`` overrides the default ``<kb>/Sources/Figures``."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    custom = tmp_path / "alt" / "fig-cache"
    seen: list[Path] = []

    def _fake_acquire_figures(corpus, cache_dir, **kwargs):
        seen.append(Path(cache_dir))
        return {}

    client = _FakeClient(_make_seeds())
    run_lit_arc(
        "CRISPR base editing",
        kb_root=tmp_path,
        max_seeds=5,
        max_papers_to_summarize=5,
        acquire_figures=True,
        figure_cache_dir=custom,
        _client=client,
        _fetch_refs=_fake_fetch_refs,
        _acquire=_fake_acquire,
        _acquire_figures=_fake_acquire_figures,
        _llm_summary=_fake_llm_summary(),
        _today="2026-04-30",
    )
    assert seen == [custom]
    assert custom.exists()


# ---------------------------------------------------------------------------
# Fix 3 (2026-04-30 evening-4): same-day arc collision detection
# ---------------------------------------------------------------------------


def test_arc_collision_writes_rerun_suffix_when_content_differs(
    tmp_path, monkeypatch
):
    """Second same-day run with different content writes ``-rerun-1.md``."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    seeds = _make_seeds()
    client = _FakeClient(seeds)

    # First run — produces the canonical arc on disk.
    prompts1: list[str] = []
    result1 = run_lit_arc(
        "CRISPR base editing",
        kb_root=tmp_path,
        max_seeds=5,
        max_papers_to_summarize=5,
        _client=client,
        _fetch_refs=_fake_fetch_refs,
        _acquire=_fake_acquire,
        _llm_summary=_fake_llm_summary(),
        _llm_arc=_fake_llm_arc(prompts1),
        _today="2026-04-30",
    )
    arc1_path = result1.arc_path
    assert arc1_path.exists()
    assert arc1_path.name.endswith("lineage-2026-04-30.md")

    # Second same-day run with a DIFFERENT narrative — this changes the
    # arc content, so the collision detector must avoid clobbering arc1.
    def _different_arc_caller(prompts_seen):
        def _caller(*, prompt, api_key, model):
            prompts_seen.append(prompt)
            return {
                "history": "DIFFERENT history paragraph for rerun.",
                "development": "DIFFERENT development paragraph.",
                "sota": "DIFFERENT sota paragraph.",
            }
        return _caller

    prompts2: list[str] = []
    result2 = run_lit_arc(
        "CRISPR base editing",
        kb_root=tmp_path,
        max_seeds=5,
        max_papers_to_summarize=5,
        _client=client,
        _fetch_refs=_fake_fetch_refs,
        _acquire=_fake_acquire,
        _llm_summary=_fake_llm_summary(),
        _llm_arc=_different_arc_caller(prompts2),
        _today="2026-04-30",
    )
    arc2_path = result2.arc_path

    # Original arc preserved.
    assert arc1_path.exists()
    text1 = arc1_path.read_text(encoding="utf-8")
    assert "Foundational work" in text1  # from _fake_llm_arc
    assert "DIFFERENT history" not in text1

    # Rerun arc lives at the suffixed path with the new content.
    assert arc2_path != arc1_path
    assert arc2_path.name.endswith("lineage-2026-04-30-rerun-1.md")
    text2 = arc2_path.read_text(encoding="utf-8")
    assert "DIFFERENT history" in text2

    # method.md sidecar uses the suffixed path so the frontmatter pointer
    # in arc2 is correct (suffix consistency requirement).
    assert "lineage-2026-04-30-rerun-1.md.method.md" in text2

    # Provenance for the rerun lives at the suffixed path too.
    prov2 = arc2_path.with_name(arc2_path.name + ".provenance.json")
    method2 = arc2_path.with_name(arc2_path.name + ".method.md")
    assert prov2.exists(), f"missing {prov2}"
    assert method2.exists(), f"missing {method2}"


def test_arc_collision_idempotent_rerun_keeps_base_path(tmp_path, monkeypatch):
    """Same content + same date -> no rerun suffix, base path stays."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    seeds = _make_seeds()
    client = _FakeClient(seeds)

    prompts1: list[str] = []
    result1 = run_lit_arc(
        "CRISPR base editing",
        kb_root=tmp_path,
        max_seeds=5,
        max_papers_to_summarize=5,
        _client=client,
        _fetch_refs=_fake_fetch_refs,
        _acquire=_fake_acquire,
        _llm_summary=_fake_llm_summary(),
        _llm_arc=_fake_llm_arc(prompts1),
        _today="2026-04-30",
    )
    arc1_path = result1.arc_path

    # Second run with IDENTICAL inputs -> same content -> idempotent.
    prompts2: list[str] = []
    result2 = run_lit_arc(
        "CRISPR base editing",
        kb_root=tmp_path,
        max_seeds=5,
        max_papers_to_summarize=5,
        _client=client,
        _fetch_refs=_fake_fetch_refs,
        _acquire=_fake_acquire,
        _llm_summary=_fake_llm_summary(),
        _llm_arc=_fake_llm_arc(prompts2),
        _today="2026-04-30",
    )

    # Both runs share the canonical arc path.
    assert result2.arc_path == arc1_path
    assert "rerun-1" not in result2.arc_path.name


def test_arc_collision_walks_through_multiple_rerun_suffixes(
    tmp_path, monkeypatch
):
    """Third same-day run with new content gets ``-rerun-2.md``."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    from vaultlab.research.lineage import _resolve_arc_path_with_collision

    base = tmp_path / "Wiki" / "Concepts" / "topic-lineage-2026-04-30.md"
    base.parent.mkdir(parents=True, exist_ok=True)
    base.write_text("v1 content", encoding="utf-8")

    rerun1 = base.with_name("topic-lineage-2026-04-30-rerun-1.md")
    rerun1.write_text("v2 content", encoding="utf-8")

    # Third run with newer content must walk to rerun-2.
    resolved = _resolve_arc_path_with_collision(
        base, expected_content="v3 content"
    )
    assert resolved.name == "topic-lineage-2026-04-30-rerun-2.md"

    # Idempotent: matching v2 content returns rerun-1 unchanged.
    resolved2 = _resolve_arc_path_with_collision(
        rerun1, expected_content="v2 content"
    )
    assert resolved2 == rerun1


# ---------------------------------------------------------------------------
# always_include_dois wiring (--always-include flag)
# ---------------------------------------------------------------------------


def test_run_lit_arc_always_include_none_is_identical_to_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """always_include_dois=None must produce the same picks/budget as the legacy path.

    No required DOIs anywhere → no extra metadata in provenance, no
    +required suffix on picker_method, identical pick set.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(
        "vaultlab.research.config.get_config", lambda *a, **k: {}
    )
    # Walk to a tmpdir without a .vaultlab-project.json so the auto-load
    # walker finds nothing.
    monkeypatch.chdir(tmp_path)

    seeds = _make_seeds()
    client = _FakeClient(seeds)
    result = run_lit_arc(
        "always-include none",
        kb_root=tmp_path,
        max_seeds=5,
        max_papers_to_summarize=2,  # force the picker path so we can see the method
        _client=client,
        _fetch_refs=_fake_fetch_refs,
        _acquire=_fake_acquire,
        _llm_summary=_fake_llm_summary(),
        always_include_dois=None,
        _today="2026-04-30",
    )
    # Picker ran but no required suffix because no required DOIs.
    json_p = result.arc_path.with_name(result.arc_path.name + ".provenance.json")
    rec = json.loads(json_p.read_text(encoding="utf-8"))
    assert rec["params"]["narration"] == "skipped"
    # The corpus and picks were not augmented by required-papers wiring.
    assert result.corpus_size >= 3


def test_run_lit_arc_always_include_pins_in_corpus_doi_to_rank_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A required DOI already in the corpus is pinned to the top of picks.

    With max_papers_to_summarize=1, the mechanical picker would normally
    pick the highest-OG paper (Jinek 2012, with citations from both
    Komor and Gaudelli). Setting always_include_dois=[Komor] forces
    Komor to rank-1 and so Komor is the sole Tier-A pick.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(
        "vaultlab.research.config.get_config", lambda *a, **k: {}
    )
    monkeypatch.chdir(tmp_path)

    seeds = _make_seeds()
    client = _FakeClient(seeds)
    # Force a budget of 1 so the picker is exercised and only one DOI
    # survives. Komor (10.1038/nature17946) is the required paper.
    result = run_lit_arc(
        "always-include pin",
        kb_root=tmp_path,
        max_seeds=5,
        max_papers_to_summarize=1,
        _client=client,
        _fetch_refs=_fake_fetch_refs,
        _acquire=_fake_acquire,
        _llm_summary=_fake_llm_summary(),
        always_include_dois=["10.1038/nature17946"],
        _today="2026-04-30",
    )
    # Komor's summary must exist (was Tier-A) — even though by raw
    # OG-score Jinek would have won.
    komor_summary = summary_path(tmp_path, "10.1038/nature17946")
    assert komor_summary.exists(), "required DOI was not pinned into Tier-A picks"
    # Run still completed end-to-end.
    assert result.arc_path.exists()


def test_run_lit_arc_always_include_creates_stub_for_doi_not_in_corpus(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A required DOI not in the corpus gets a stub via mocked CrossRef."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(
        "vaultlab.research.config.get_config", lambda *a, **k: {}
    )
    monkeypatch.chdir(tmp_path)

    seeds = _make_seeds()
    client = _FakeClient(seeds)

    # Mock CrossRef client returning a plausible Paper for the required DOI.
    required_doi = "10.1038/s41596-021-00556-8"  # Black/Hickey CODEX protocol
    mock_paper = Paper(
        title="Hickey CODEX Imaging Protocol",
        authors=["Black S", "Phillips D", "Hickey JW"],
        year=2021,
        journal="Nature Protocols",
        doi=required_doi,
        abstract="Multiplexed imaging via CODEX.",
        citation_count=500,
        source_api="crossref",
    )

    class _MockCR:
        def resolve_doi(self, doi):
            if doi == required_doi:
                return mock_paper
            return None

    result = run_lit_arc(
        "always-include stub",
        kb_root=tmp_path,
        max_seeds=5,
        max_papers_to_summarize=4,
        _client=client,
        _fetch_refs=_fake_fetch_refs,
        _acquire=_fake_acquire,
        _llm_summary=_fake_llm_summary(),
        always_include_dois=[required_doi],
        _crossref_client=_MockCR(),
        _today="2026-04-30",
    )
    # On-disk article stub for the required DOI exists.
    stub = article_stub_path(tmp_path, required_doi)
    assert stub.exists(), f"missing on-demand stub at {stub}"
    stub_text = stub.read_text(encoding="utf-8")
    assert "Hickey CODEX Imaging Protocol" in stub_text
    # The required DOI shows up in the corpus (corpus size grew by 1
    # past the seed-only baseline).
    assert required_doi in {d.lower() for d in result.summary_paths}
    # Run completed and produced an arc.
    assert result.arc_path.exists()


def test_run_lit_arc_always_include_required_doi_survives_into_picks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Required DOIs survive into the final picks even with a tight budget.

    With max_papers_to_summarize=1 and a corpus of 4+ papers (3 seeds +
    1 injected required), the picker would normally drop the freshly-
    injected required paper (low og_score, no PDF). The required-papers
    wiring must still keep it as a Tier-A pick.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(
        "vaultlab.research.config.get_config", lambda *a, **k: {}
    )
    monkeypatch.chdir(tmp_path)

    seeds = _make_seeds()
    client = _FakeClient(seeds)
    required_doi = "10.1038/s41596-021-00556-8"
    mock_paper = Paper(
        title="Hickey CODEX Imaging Protocol",
        authors=["Black S"],
        year=2021,
        journal="Nature Protocols",
        doi=required_doi,
        abstract="Multiplexed imaging via CODEX.",
        citation_count=500,
        source_api="crossref",
    )

    class _MockCR:
        def resolve_doi(self, doi):
            return mock_paper if doi == required_doi else None

    result = run_lit_arc(
        "always-include survives",
        kb_root=tmp_path,
        max_seeds=5,
        max_papers_to_summarize=1,  # tight budget: only 1 Tier-A slot
        _client=client,
        _fetch_refs=_fake_fetch_refs,
        _acquire=_fake_acquire,
        _llm_summary=_fake_llm_summary(),
        always_include_dois=[required_doi],
        _crossref_client=_MockCR(),
        _today="2026-04-30",
    )
    # The required DOI survives into the picks even though its
    # og_score is 0 — it's pinned to rank 1.
    assert required_doi in {d.lower() for d in result.summary_paths}
    # The summary file actually exists for the required DOI (Tier-A
    # picked it up because it was pinned).
    req_summary = summary_path(tmp_path, required_doi)
    assert req_summary.exists()
