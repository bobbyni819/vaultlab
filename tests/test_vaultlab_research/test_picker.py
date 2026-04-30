"""Unit tests for vaultlab.research.picker.

The picker is content-aware: it asks Claude Code (or any callback) to read
candidate abstracts before ranking. These tests use synthetic callbacks
so they run offline and are fully deterministic.

Coverage
--------
* :func:`prepare_picker_task` produces a valid task without HTTP/LLM calls.
* :func:`render_picks_from_response` parses JSON correctly and handles
  missing / malformed fields gracefully.
* :func:`pick_top_n_content_aware` falls back to the citation graph when
  no callback is given.
* :func:`pick_top_n_content_aware` propagates a synthetic callback's
  picks deterministically.
* The picker writes its rationale to ``decisions-log.md`` (or the per-run
  fallback file) so the audit trail survives.
* The picker integrates with :func:`run_lit_arc` via the new
  ``picker_callback=`` parameter.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from vaultlab.kb.paths import (
    article_stub_path,
    project_decisions_path,
    slugify_doi,
)
from vaultlab.research.corpus import Corpus
from vaultlab.research.graph_metrics import compute_metrics
from vaultlab.research.paper import Paper
from vaultlab.research.picker import (
    CandidatePaper,
    PickerTask,
    build_picker_prompt,
    load_abstract_from_kb,
    pick_top_n_content_aware,
    picker_response_schema,
    prepare_picker_task,
    render_picks_from_response,
    write_picker_decision,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_seeds() -> list[Paper]:
    """Three seed papers covering history / development / SOTA buckets."""
    return [
        Paper(
            title="Programmable RNA-Guided DNA Endonuclease",
            authors=["Jinek M", "Doudna JA"],
            year=2012,
            journal="Science",
            doi="10.1126/science.1225829",
            citation_count=12000,
            source_api="pubmed",
            abstract=(
                "We show that the bacterial Cas9 protein can be programmed "
                "with a single guide RNA to cleave DNA at any matching "
                "sequence. This establishes the foundational mechanism "
                "for genome engineering."
            ),
        ),
        Paper(
            title="Cytidine Deaminase Base Editor",
            authors=["Komor AC", "Liu DR"],
            year=2016,
            journal="Nature",
            doi="10.1038/nature17946",
            citation_count=4000,
            source_api="pubmed",
            abstract=(
                "Base editing converts cytosine to thymine at programmed "
                "loci using a Cas9 nickase fused to a deaminase domain. "
                "We demonstrate 37 percent editing efficiency."
            ),
        ),
        Paper(
            title="Adenine Base Editor",
            authors=["Gaudelli NM", "Liu DR"],
            year=2017,
            journal="Nature",
            doi="10.1038/nature24644",
            citation_count=3000,
            source_api="pubmed",
            abstract=(
                "We describe an evolved adenosine deaminase that converts "
                "A to G at target loci, complementing cytidine base editing."
            ),
        ),
    ]


def _make_corpus_with_metrics() -> Corpus:
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


# ---------------------------------------------------------------------------
# picker_response_schema
# ---------------------------------------------------------------------------


def test_picker_response_schema_is_valid_json_schema():
    schema = picker_response_schema()
    assert schema["type"] == "object"
    assert schema["required"] == ["picks"]
    items = schema["properties"]["picks"]["items"]
    assert set(items["required"]) == {"doi", "rank", "rationale"}
    # Round-trip through JSON.
    assert json.loads(json.dumps(schema)) == schema


# ---------------------------------------------------------------------------
# prepare_picker_task
# ---------------------------------------------------------------------------


def test_prepare_picker_task_makes_no_http_calls(tmp_path, monkeypatch):
    """Building a task must not import or touch ``anthropic``."""

    class _Guard:
        def __getattr__(self, name):
            raise AssertionError(
                f"prepare_picker_task touched anthropic.{name}"
            )

    monkeypatch.setitem(sys.modules, "anthropic", _Guard())

    corpus = _make_corpus_with_metrics()
    task = prepare_picker_task(
        "CRISPR base editing",
        corpus=corpus,
        target_n=2,
        coarse_n=10,
        kb_root=tmp_path,
    )
    assert isinstance(task, PickerTask)
    assert task.topic == "CRISPR base editing"
    assert task.target_n == 2
    # 3 papers in corpus, coarse_n=10 -> all 3 candidates.
    assert len(task.candidates) == 3
    dois = {c.doi for c in task.candidates}
    assert dois == {
        "10.1126/science.1225829",
        "10.1038/nature17946",
        "10.1038/nature24644",
    }
    # Abstracts hydrate from Paper.abstract (no KB stub yet).
    jinek = next(c for c in task.candidates if c.year == 2012)
    assert "Cas9" in jinek.abstract
    # Prompt embeds topic + target_n.
    assert "CRISPR base editing" in task.prompt
    assert "Pick the 2 BEST papers" in task.prompt
    assert "Cas9" in task.prompt  # abstract content present
    assert task.system_prompt  # non-empty system guard rail
    assert task.response_schema == picker_response_schema()


def test_prepare_picker_task_prefers_kb_stub_abstract(tmp_path):
    """KB stub abstract takes priority over Paper.abstract field."""
    corpus = _make_corpus_with_metrics()
    # Write a stub for one paper with a custom abstract.
    target_doi = "10.1126/science.1225829"
    stub = article_stub_path(tmp_path, target_doi)
    stub.parent.mkdir(parents=True, exist_ok=True)
    stub.write_text(
        '---\ntitle: "stub"\n---\n\n# stub\n\n## Abstract\n\nKB-STUB-ABSTRACT-MARKER\n',
        encoding="utf-8",
    )
    task = prepare_picker_task(
        "CRISPR base editing",
        corpus=corpus,
        target_n=3,
        coarse_n=10,
        kb_root=tmp_path,
    )
    jinek = next(c for c in task.candidates if c.doi == target_doi)
    assert "KB-STUB-ABSTRACT-MARKER" in jinek.abstract


def test_prepare_picker_task_falls_back_to_no_abstract(tmp_path):
    """Papers without abstract metadata get the placeholder."""
    seeds = _make_seeds()
    seeds[0].abstract = ""  # strip
    corpus = Corpus(topic="t", seeds=seeds)
    for s in seeds:
        corpus.papers[s.doi.lower()] = s
    compute_metrics(corpus)
    task = prepare_picker_task(
        "t", corpus=corpus, target_n=3, coarse_n=10, kb_root=tmp_path
    )
    jinek = next(c for c in task.candidates if c.doi == seeds[0].doi.lower())
    assert jinek.abstract == "[no abstract]"


def test_prepare_picker_task_respects_coarse_n_cutoff(tmp_path):
    """``coarse_n`` truncates the candidate list."""
    corpus = _make_corpus_with_metrics()
    task = prepare_picker_task(
        "t", corpus=corpus, target_n=2, coarse_n=2, kb_root=tmp_path
    )
    assert len(task.candidates) == 2


def test_load_abstract_from_kb_returns_empty_when_missing(tmp_path):
    assert load_abstract_from_kb(tmp_path, "10.999/missing") == ""


# ---------------------------------------------------------------------------
# render_picks_from_response
# ---------------------------------------------------------------------------


def test_render_picks_from_response_returns_ordered_dois(tmp_path):
    corpus = _make_corpus_with_metrics()
    task = prepare_picker_task(
        "t", corpus=corpus, target_n=3, coarse_n=10, kb_root=tmp_path
    )
    response = {
        "picks": [
            {
                "doi": "10.1038/nature17946",
                "rank": 2,
                "rationale": "second",
            },
            {
                "doi": "10.1126/science.1225829",
                "rank": 1,
                "rationale": "first",
            },
            {
                "doi": "10.1038/nature24644",
                "rank": 3,
                "rationale": "third",
            },
        ]
    }
    picks = render_picks_from_response(task, response)
    assert picks == [
        "10.1126/science.1225829",
        "10.1038/nature17946",
        "10.1038/nature24644",
    ]


def test_render_picks_from_response_drops_unknown_dois(tmp_path):
    """Picks for DOIs that aren't in the candidate pool are silently dropped."""
    corpus = _make_corpus_with_metrics()
    task = prepare_picker_task(
        "t", corpus=corpus, target_n=3, coarse_n=10, kb_root=tmp_path
    )
    response = {
        "picks": [
            {
                "doi": "10.9999/invented",
                "rank": 1,
                "rationale": "made up",
            },
            {
                "doi": "10.1126/science.1225829",
                "rank": 2,
                "rationale": "real",
            },
        ]
    }
    picks = render_picks_from_response(task, response)
    assert picks == ["10.1126/science.1225829"]


def test_render_picks_from_response_handles_missing_fields(tmp_path):
    """Missing rank / rationale / picks key are tolerated."""
    corpus = _make_corpus_with_metrics()
    task = prepare_picker_task(
        "t", corpus=corpus, target_n=3, coarse_n=10, kb_root=tmp_path
    )
    # Empty / None response.
    assert render_picks_from_response(task, {}) == []
    assert render_picks_from_response(task, None) == []
    # picks key is not a list.
    assert render_picks_from_response(task, {"picks": "nope"}) == []
    # Pick missing rank: still kept (sorted last by huge rank), no rationale OK.
    response = {
        "picks": [
            {"doi": "10.1126/science.1225829"},  # no rank, no rationale
            {
                "doi": "10.1038/nature17946",
                "rank": 1,
                "rationale": "ok",
            },
        ]
    }
    picks = render_picks_from_response(task, response)
    # rank=1 wins over missing-rank fallback.
    assert picks[0] == "10.1038/nature17946"
    assert "10.1126/science.1225829" in picks


def test_render_picks_caps_at_target_n(tmp_path):
    corpus = _make_corpus_with_metrics()
    task = prepare_picker_task(
        "t", corpus=corpus, target_n=2, coarse_n=10, kb_root=tmp_path
    )
    response = {
        "picks": [
            {"doi": d, "rank": i + 1, "rationale": "x"}
            for i, d in enumerate(
                [
                    "10.1126/science.1225829",
                    "10.1038/nature17946",
                    "10.1038/nature24644",
                ]
            )
        ]
    }
    picks = render_picks_from_response(task, response)
    assert len(picks) == 2


# ---------------------------------------------------------------------------
# pick_top_n_content_aware — fallback + callback paths
# ---------------------------------------------------------------------------


def test_pick_top_n_content_aware_fallback(tmp_path):
    """No callback -> falls back to mechanical citation-graph pick."""
    corpus = _make_corpus_with_metrics()
    picks = pick_top_n_content_aware(
        "CRISPR base editing",
        corpus,
        target_n=3,
        coarse_n=10,
        kb_root=tmp_path,
        picker_callback=None,
    )
    assert len(picks) == 3
    assert set(picks) == {
        "10.1126/science.1225829",
        "10.1038/nature17946",
        "10.1038/nature24644",
    }


def test_pick_top_n_content_aware_callback_is_used(tmp_path):
    """Callback's picks are propagated; abstracts ARE inspected by the callback."""
    corpus = _make_corpus_with_metrics()

    seen_tasks: list[PickerTask] = []

    def _stub_callback(task: PickerTask) -> dict[str, Any]:
        seen_tasks.append(task)
        # Pick by year ascending (oldest first) to differ from citation rank.
        ordered = sorted(task.candidates, key=lambda c: c.year)
        return {
            "picks": [
                {
                    "doi": c.doi,
                    "rank": i + 1,
                    "rationale": f"year={c.year}",
                }
                for i, c in enumerate(ordered)
            ]
        }

    picks = pick_top_n_content_aware(
        "CRISPR base editing",
        corpus,
        target_n=3,
        coarse_n=10,
        kb_root=tmp_path,
        picker_callback=_stub_callback,
        log_decision=False,
    )
    assert len(seen_tasks) == 1
    # Callback received hydrated abstracts.
    abstracts = [c.abstract for c in seen_tasks[0].candidates]
    assert any("Cas9" in a for a in abstracts)
    # Picks ordered by year ascending (per the stub).
    assert picks == [
        "10.1126/science.1225829",  # 2012
        "10.1038/nature17946",  # 2016
        "10.1038/nature24644",  # 2017
    ]


def test_pick_top_n_content_aware_handles_callback_exception(tmp_path):
    """A raising callback falls back to the citation graph by default."""
    corpus = _make_corpus_with_metrics()

    def _bad(task: PickerTask) -> dict[str, Any]:
        raise RuntimeError("simulated picker failure")

    picks = pick_top_n_content_aware(
        "t",
        corpus,
        target_n=3,
        coarse_n=10,
        kb_root=tmp_path,
        picker_callback=_bad,
        fallback_to_citation_graph=True,
        log_decision=False,
    )
    assert len(picks) == 3


def test_pick_top_n_content_aware_no_fallback_raises(tmp_path):
    """``fallback_to_citation_graph=False`` + no callback -> ValueError."""
    corpus = _make_corpus_with_metrics()
    with pytest.raises(ValueError):
        pick_top_n_content_aware(
            "t",
            corpus,
            target_n=3,
            coarse_n=10,
            kb_root=tmp_path,
            picker_callback=None,
            fallback_to_citation_graph=False,
        )


def test_pick_top_n_content_aware_empty_picks_falls_back(tmp_path):
    """Callback returning no valid picks -> citation-graph fallback."""
    corpus = _make_corpus_with_metrics()

    def _empty(task: PickerTask) -> dict[str, Any]:
        return {"picks": []}

    picks = pick_top_n_content_aware(
        "t",
        corpus,
        target_n=3,
        coarse_n=10,
        kb_root=tmp_path,
        picker_callback=_empty,
        log_decision=False,
    )
    assert len(picks) == 3


# ---------------------------------------------------------------------------
# write_picker_decision — audit-trail integration
# ---------------------------------------------------------------------------


def test_picker_records_rationale_in_decisions_log(tmp_path):
    """When a project decisions-log already exists, picks append there."""
    project = "lit-arc-test"
    log_path = project_decisions_path(tmp_path, project)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("# Decisions Log\n", encoding="utf-8")

    corpus = _make_corpus_with_metrics()

    def _cb(task: PickerTask) -> dict[str, Any]:
        return {
            "picks": [
                {
                    "doi": "10.1126/science.1225829",
                    "rank": 1,
                    "rationale": "Foundational programmable cleavage paper.",
                },
                {
                    "doi": "10.1038/nature17946",
                    "rank": 2,
                    "rationale": "Defines cytidine base editing.",
                },
            ]
        }

    picks = pick_top_n_content_aware(
        "CRISPR base editing",
        corpus,
        target_n=2,
        coarse_n=10,
        kb_root=tmp_path,
        picker_callback=_cb,
        project=project,
    )
    assert picks == [
        "10.1126/science.1225829",
        "10.1038/nature17946",
    ]
    body = log_path.read_text(encoding="utf-8")
    assert "Picker decision" in body
    assert "Topic: CRISPR base editing" in body
    assert "Foundational programmable cleavage paper." in body
    assert "Defines cytidine base editing." in body
    # Wikilink slug used.
    assert f"[[{slugify_doi('10.1126/science.1225829')}|" in body


def test_picker_records_rationale_in_run_dir_fallback(tmp_path):
    """When no project log exists, writes to ``<run_dir>/picker-decision.md``."""
    corpus = _make_corpus_with_metrics()
    fallback = tmp_path / "Output" / "topic" / "runs" / "2026-04-30T10-00-00"

    def _cb(task: PickerTask) -> dict[str, Any]:
        return {
            "picks": [
                {
                    "doi": "10.1038/nature24644",
                    "rank": 1,
                    "rationale": "Adenine base editor — SOTA representative.",
                }
            ]
        }

    picks = pick_top_n_content_aware(
        "CRISPR base editing",
        corpus,
        target_n=1,
        coarse_n=10,
        kb_root=tmp_path,
        picker_callback=_cb,
        project=None,
        fallback_dir=fallback,
    )
    assert picks == ["10.1038/nature24644"]
    out = fallback / "picker-decision.md"
    assert out.exists()
    body = out.read_text(encoding="utf-8")
    assert "Adenine base editor" in body
    assert "Picker decision" in body


def test_write_picker_decision_returns_none_without_destination(tmp_path):
    """No project + no fallback_dir -> returns None (no file written)."""
    corpus = _make_corpus_with_metrics()
    task = prepare_picker_task(
        "t", corpus=corpus, target_n=1, coarse_n=10, kb_root=tmp_path
    )
    out = write_picker_decision(
        kb_root=tmp_path,
        project=None,
        topic="t",
        task=task,
        picks=["10.1126/science.1225829"],
        rationales={"10.1126/science.1225829": "r"},
        method="content-aware",
        fallback_dir=None,
    )
    assert out is None


# ---------------------------------------------------------------------------
# build_picker_prompt — explicit content checks
# ---------------------------------------------------------------------------


def test_build_picker_prompt_lists_candidates_with_metadata():
    candidates = [
        CandidatePaper(
            doi="10.1/a",
            title="Alpha paper",
            authors=["Smith J", "Jones K"],
            year=2020,
            journal="Cell",
            abstract="Alpha abstract content.",
            og_score=0.4,
            forward_influence=2,
            has_pdf=True,
        ),
        CandidatePaper(
            doi="10.1/b",
            title="Beta paper",
            authors=["Doe A"],
            year=2024,
            journal="Nature",
            abstract="Beta abstract content.",
            og_score=0.1,
            forward_influence=0,
            has_pdf=False,
        ),
    ]
    prompt = build_picker_prompt(
        topic="my topic", candidates=candidates, target_n=2
    )
    assert "TOPIC: my topic" in prompt
    assert "Pick the 2 BEST papers" in prompt
    assert "Alpha paper" in prompt
    assert "Beta paper" in prompt
    assert "Smith J et al." in prompt
    assert "Doe A" in prompt
    assert "Alpha abstract content." in prompt
    assert "og_score=0.40" in prompt
    assert "forward_influence=2" in prompt
    assert "has_pdf=True" in prompt
    # Must remind the picker to use only listed DOIs.
    assert "Do NOT invent new DOIs" in prompt


# ---------------------------------------------------------------------------
# run_lit_arc integration — picker_callback parameter
# ---------------------------------------------------------------------------


def _fake_acquire(corpus, cache_dir, **kwargs):
    """Acquire fake PDFs for every paper (matches test_lineage helper)."""
    from vaultlab.research.acquisition import (
        AcquisitionResult,
        cache_path_for,
    )

    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    out: dict[str, AcquisitionResult] = {}
    for doi in corpus.papers:
        target = cache_path_for(doi, cache_dir)
        target.write_bytes(b"%PDF-1.4\n" + b"x" * 4000)
        out[doi] = AcquisitionResult(
            doi=doi,
            pdf_path=target,
            source="unpaywall",
            license="cc-by",
        )
    return out


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


class _FakeClient:
    def __init__(self, seeds):
        self._seeds = seeds

    def search(self, query: str, max_results: int = 20, sources=None):
        return list(self._seeds)


def test_run_lit_arc_uses_picker_callback(tmp_path, monkeypatch):
    """``picker_callback`` is invoked when ``max_papers_to_summarize < n_papers``.

    The callback's picks become the Tier-A set.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(
        "vaultlab.research.config.get_config", lambda *a, **k: {}
    )
    from vaultlab.research.lineage import run_lit_arc

    seeds = _make_seeds()
    seen_picker_tasks: list[PickerTask] = []

    def _picker(task: PickerTask) -> dict[str, Any]:
        seen_picker_tasks.append(task)
        # Return picks ordered by year ascending.
        ordered = sorted(task.candidates, key=lambda c: c.year)
        return {
            "picks": [
                {"doi": c.doi, "rank": i + 1, "rationale": f"y{c.year}"}
                for i, c in enumerate(ordered)
            ]
        }

    def _stub_summary_llm(*, pdf_bytes, prompt, api_key, model, **_):
        return (
            {
                "tldr": "[stub] s1. s2. s3.",
                "why_it_matters": ["x"],
                "methods_summary": "m",
                "key_findings": ["a [p1]", "b [p2]", "c [p3]"],
                "extracted_references": [],
            },
            1,
            1,
        )

    result = run_lit_arc(
        "CRISPR base editing",
        kb_root=tmp_path,
        max_seeds=5,
        max_papers_to_summarize=2,  # < 3 papers in corpus -> picker runs
        picker_callback=_picker,
        picker_coarse_n=10,
        _client=_FakeClient(seeds),
        _fetch_refs=_fake_fetch_refs,
        _acquire=_fake_acquire,
        _llm_summary=_stub_summary_llm,
        _today="2026-04-30",
    )

    # Picker was invoked exactly once.
    assert len(seen_picker_tasks) == 1
    task = seen_picker_tasks[0]
    assert task.topic == "CRISPR base editing"
    assert task.target_n == 2
    # Run completed and arc was written.
    assert result.arc_path.exists()


def test_run_lit_arc_without_picker_callback_uses_citation_graph(
    tmp_path, monkeypatch
):
    """No ``picker_callback`` -> previous mechanical behaviour preserved."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(
        "vaultlab.research.config.get_config", lambda *a, **k: {}
    )
    from vaultlab.research.lineage import run_lit_arc

    seeds = _make_seeds()

    def _stub_summary_llm(*, pdf_bytes, prompt, api_key, model, **_):
        return (
            {
                "tldr": "[stub] s1. s2. s3.",
                "why_it_matters": ["x"],
                "methods_summary": "m",
                "key_findings": ["a [p1]", "b [p2]", "c [p3]"],
                "extracted_references": [],
            },
            1,
            1,
        )

    # Should run without error and produce the arc.
    result = run_lit_arc(
        "CRISPR base editing",
        kb_root=tmp_path,
        max_seeds=5,
        max_papers_to_summarize=2,
        # picker_callback NOT given
        _client=_FakeClient(seeds),
        _fetch_refs=_fake_fetch_refs,
        _acquire=_fake_acquire,
        _llm_summary=_stub_summary_llm,
        _today="2026-04-30",
    )
    assert result.arc_path.exists()


# ---------------------------------------------------------------------------
# Regression: seed DOIs survive coarse_n cutoff (Bug 2, evening 3 — 2026-04-30)
# ---------------------------------------------------------------------------


def test_seed_doi_with_zero_og_score_survives_coarse_n_cutoff(tmp_path):
    """A seed DOI with og_score=0 must NOT be silently dropped by coarse_n.

    Regression test: previously _build_candidates sorted by og_score+forward_influence
    only, so a freshly-seeded paper that wasn't yet cited within the corpus could be
    truncated out before it ever reached the LLM picker. Fix: sort by
    (is_seed, has_pdf, og_score+forward_influence) so seeds always rank first.
    """
    # Seed paper that nobody cites (og_score=0).
    seed = Paper(
        title="Brand New Seed Paper",
        authors=["Newauthor A"],
        year=2026,
        journal="Preprint",
        doi="10.1234/seed.zero.og",
        citation_count=0,
        source_api="manual",
        abstract="Seed paper with zero og_score because nothing cites it yet.",
    )
    # An existing well-cited seed that DOES cite the popular papers, giving them og_score > 0.
    citing_seed = Paper(
        title="Citing Seed Paper",
        authors=["Citer S"],
        year=2024,
        journal="Hot Journal",
        doi="10.5555/citing.seed",
        citation_count=50,
        source_api="pubmed",
        abstract="A second seed that cites all the popular papers.",
    )
    seeds = [seed, citing_seed]
    corpus = Corpus(topic="seed-survival", seeds=seeds)
    corpus.papers[seed.doi.lower()] = seed
    corpus.papers[citing_seed.doi.lower()] = citing_seed
    # Add many highly-cited non-seed papers that crowd out coarse_n.
    pop_dois: list[str] = []
    for i in range(20):
        doi = f"10.9999/popular.paper.{i:03d}"
        pop_dois.append(doi)
        p = Paper(
            title=f"Popular Paper {i}",
            authors=[f"Author{i} A"],
            year=2024,
            journal="Hot Journal",
            doi=doi,
            citation_count=1000,
            source_api="pubmed",
            abstract=f"Popular paper number {i} with lots of citations.",
        )
        corpus.papers[doi] = p
    # citing_seed cites every popular paper -> og_score > 0 for popular dois.
    corpus.references = {
        seed.doi.lower(): [],
        citing_seed.doi.lower(): list(pop_dois),
    }
    for d in pop_dois:
        corpus.references[d] = []
    compute_metrics(corpus)

    # Sanity check: seed has og_score=0
    assert corpus.metrics is not None
    assert corpus.metrics.og_score.get(seed.doi.lower(), 0.0) == 0.0
    # Sanity check: at least one popular paper has og_score > 0
    assert any(corpus.metrics.og_score.get(d, 0.0) > 0 for d in pop_dois)

    # Run with coarse_n=5 — without the fix, the og_score=0 seed gets cut.
    task = prepare_picker_task(
        "seed-survival",
        corpus=corpus,
        target_n=3,
        coarse_n=5,
        kb_root=tmp_path,
    )
    candidate_dois = {c.doi for c in task.candidates}
    assert seed.doi.lower() in candidate_dois, (
        f"Seed DOI with og_score=0 was dropped by coarse_n=5 cutoff. "
        f"Got candidates: {candidate_dois}"
    )
    assert citing_seed.doi.lower() in candidate_dois, (
        "Citing seed should also survive."
    )
