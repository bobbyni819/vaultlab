"""Unit tests for vaultlab.research.binning.

The binner is content-aware: it asks Claude Code (or any callback) to read
candidate abstracts and decide history / development / sota assignment.
These tests use synthetic callbacks so they run offline.

Coverage
--------
* :func:`prepare_binning_task` produces a task without HTTP/LLM calls;
  empty corpus and over-budget corpus both behave correctly.
* :func:`render_binning_from_response` parses JSON, falls back to the
  deterministic bucket on missing / invalid LLM output, and never
  invents DOIs.
* :func:`assign_buckets_with_llm` orchestrates callback / fallback /
  hard-error paths.
* The synthetic-corpus regression test that motivates this module —
  the deterministic buckets leave HISTORY empty (all 2019+ papers); the
  LLM moves the foundational 2019 paper into HISTORY.
"""

from __future__ import annotations

import json
import sys
from typing import Any

import pytest

from vaultlab.research.binning import (
    BinningResult,
    BinningTask,
    MissingBinningCallback,
    assign_buckets_with_llm,
    binning_response_schema,
    prepare_binning_task,
    render_binning_from_response,
)
from vaultlab.research.corpus import Corpus
from vaultlab.research.graph_metrics import compute_metrics
from vaultlab.research.paper import Paper

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_seeds() -> list[Paper]:
    """Three CRISPR base-editing seeds with abstracts."""
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
                "loci using a Cas9 nickase fused to a deaminase domain."
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
                "We describe an evolved adenosine deaminase that converts A to G at target loci."
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


def _make_synthetic_recent_corpus() -> Corpus:
    """Mimic Bobby's L4 CODEX scenario: all papers 2018+, deterministic
    quartiles label the 2018 foundational paper as 'history' (correctly)
    and 2024+ as 'sota'. Used to test the LLM-override path: even though
    the deterministic system might place the 2018 CODEX paper outside
    HISTORY (e.g. when there are only 2 distinct year groups), the LLM
    recognizes it as foundational and puts it in HISTORY.
    """
    # 6 papers, all 2024 except one 2018 foundational paper. Quartile
    # bucketing on rank-sorted years places the 2018 paper first ->
    # "history", but if we feed only 2024 papers the bucket goes empty.
    papers = [
        Paper(
            title="Highly multiplexed in situ tissue imaging (CODEX)",
            authors=["Goltsev Y"],
            year=2018,
            journal="Cell",
            doi="10.1016/j.cell.2018.07.010",
            abstract=(
                "We introduce CODEX, a co-detection by indexing method "
                "that enables highly multiplexed antibody-based imaging "
                "at single-cell resolution. The method establishes the "
                "foundational principle of cyclic indexing for spatial "
                "transcriptomics."
            ),
            citation_count=1500,
        ),
        Paper(
            title="CODEX application to colorectal cancer",
            authors=["Schurch C"],
            year=2024,
            journal="Cell",
            doi="10.1016/j.cell.2024.001",
            abstract=(
                "We apply CODEX to map colorectal cancer immune "
                "neighborhoods, an incremental application of the "
                "established CODEX protocol to a new disease context."
            ),
            citation_count=50,
        ),
        Paper(
            title="40-plex CODEX panel for tonsil",
            authors=["Black S"],
            year=2024,
            journal="Nat Biotech",
            doi="10.1038/s41587-024-002",
            abstract=(
                "Routine 40-plex CODEX panel application to tonsil "
                "tissue. Method follows established CODEX protocols."
            ),
            citation_count=20,
        ),
        Paper(
            title="Spatial proteomics deep learning analysis",
            authors=["Hickey J"],
            year=2025,
            journal="Cell Systems",
            doi="10.1016/j.cels.2025.001",
            abstract=(
                "State-of-the-art transformer-based analysis of CODEX "
                "spatial data. The most recent meaningful methodological "
                "advance: replaces hand-tuned segmentation with learned "
                "models."
            ),
            citation_count=5,
        ),
    ]
    corpus = Corpus(topic="spatial transcriptomics CODEX", seeds=papers)
    for p in papers:
        corpus.papers[p.doi.lower()] = p
    corpus.references = {p.doi.lower(): [] for p in papers}
    compute_metrics(corpus)
    return corpus


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


def test_binning_response_schema_is_valid_json_schema():
    schema = binning_response_schema()
    assert schema["type"] == "object"
    assert schema["required"] == ["assignments"]
    items = schema["properties"]["assignments"]["items"]
    assert {"doi", "bucket"} <= set(items["required"])
    assert set(items["properties"]["bucket"]["enum"]) == {
        "history",
        "development",
        "sota",
    }
    # Round-trip through JSON.
    assert json.loads(json.dumps(schema)) == schema


# ---------------------------------------------------------------------------
# prepare_binning_task
# ---------------------------------------------------------------------------


def test_prepare_binning_task_makes_no_http_calls(monkeypatch):
    """Building a task must not import or touch ``anthropic``."""

    class _Guard:
        def __getattr__(self, name):
            raise AssertionError(f"prepare_binning_task touched anthropic.{name}")

    monkeypatch.setitem(sys.modules, "anthropic", _Guard())

    corpus = _make_corpus_with_metrics()
    task = prepare_binning_task(corpus, "CRISPR base editing")
    assert isinstance(task, BinningTask)
    assert task.topic == "CRISPR base editing"
    assert len(task.candidates) == 3
    dois = {c.doi for c in task.candidates}
    assert dois == {
        "10.1126/science.1225829",
        "10.1038/nature17946",
        "10.1038/nature24644",
    }
    # Prompt embeds topic + candidate count.
    assert "CRISPR base editing" in task.prompt
    assert "3 candidates below" in task.prompt
    # System prompt is the binning guard rail.
    assert "HISTORY" in task.system
    assert "SOTA" in task.system
    assert task.response_schema == binning_response_schema()


def test_prepare_binning_task_empty_corpus_returns_empty():
    """An empty corpus produces a task with zero candidates."""
    corpus = Corpus(topic="empty", seeds=[])
    compute_metrics(corpus)
    task = prepare_binning_task(corpus, "empty")
    assert task.candidates == []
    # Prompt still mentions the topic.
    assert "empty" in task.prompt


def test_prepare_binning_task_includes_deterministic_hint():
    """Each candidate carries the deterministic_bucket hint."""
    corpus = _make_corpus_with_metrics()
    task = prepare_binning_task(corpus, "t")
    # Every candidate's deterministic_bucket is in the valid bucket set
    # or 'unknown'.
    for c in task.candidates:
        assert c.deterministic_bucket in {
            "history",
            "development",
            "sota",
            "unknown",
        }
    assert "deterministic_bucket=" in task.prompt


def test_prepare_binning_task_respects_max_candidates_ranking():
    """When max_candidates < corpus size, top-N by og_score+forward kept."""
    seeds = _make_seeds()
    # Add a low-score 4th paper.
    seeds.append(
        Paper(
            title="Tangential application paper",
            authors=["X"],
            year=2020,
            journal="Misc",
            doi="10.9999/tangent",
            citation_count=1,
            source_api="pubmed",
            abstract="A tangential paper with no in-corpus citations.",
        )
    )
    corpus = Corpus(topic="t", seeds=seeds)
    for s in seeds:
        corpus.papers[s.doi.lower()] = s
    corpus.references = {
        "10.1126/science.1225829": [],
        "10.1038/nature17946": ["10.1126/science.1225829"],
        "10.1038/nature24644": [
            "10.1126/science.1225829",
            "10.1038/nature17946",
        ],
        "10.9999/tangent": [],
    }
    compute_metrics(corpus)
    task = prepare_binning_task(corpus, "t", max_candidates=3)
    # Only 3 candidates, and the tangential one (lowest score) drops out.
    assert len(task.candidates) == 3
    dois = {c.doi for c in task.candidates}
    assert "10.9999/tangent" not in dois


def test_prepare_binning_task_truncates_long_abstracts():
    """Very long abstracts are trimmed to fit the prompt budget."""
    seeds = _make_seeds()
    seeds[0].abstract = "X " * 2000  # 4000 chars of "X "
    corpus = Corpus(topic="t", seeds=seeds)
    for s in seeds:
        corpus.papers[s.doi.lower()] = s
    corpus.references = {
        "10.1126/science.1225829": [],
        "10.1038/nature17946": [],
        "10.1038/nature24644": [],
    }
    compute_metrics(corpus)
    task = prepare_binning_task(corpus, "t")
    # The truncation kicks in inside build_binning_prompt; we verify by
    # checking the prompt doesn't run the full 4000 chars verbatim.
    full_abstract = "X " * 2000
    assert full_abstract not in task.prompt


# ---------------------------------------------------------------------------
# render_binning_from_response
# ---------------------------------------------------------------------------


def test_render_binning_from_response_valid_json_populates_buckets():
    corpus = _make_corpus_with_metrics()
    task = prepare_binning_task(corpus, "t")
    response = {
        "assignments": [
            {
                "doi": "10.1126/science.1225829",
                "bucket": "history",
                "rationale": "Foundational Cas9 paper.",
            },
            {
                "doi": "10.1038/nature17946",
                "bucket": "development",
                "rationale": "Mid-arc CBE.",
            },
            {
                "doi": "10.1038/nature24644",
                "bucket": "sota",
                "rationale": "Recent ABE advance.",
            },
        ]
    }
    result = render_binning_from_response(response, task)
    assert isinstance(result, BinningResult)
    assert result.bucket_by_doi["10.1126/science.1225829"] == "history"
    assert result.bucket_by_doi["10.1038/nature17946"] == "development"
    assert result.bucket_by_doi["10.1038/nature24644"] == "sota"
    assert result.rationale_by_doi["10.1126/science.1225829"] == ("Foundational Cas9 paper.")
    assert result.coverage_summary["history"] == 1
    assert result.coverage_summary["development"] == 1
    assert result.coverage_summary["sota"] == 1


def test_render_binning_from_response_missing_doi_falls_back():
    """When the LLM omits a DOI, the deterministic bucket is preserved."""
    corpus = _make_corpus_with_metrics()
    task = prepare_binning_task(corpus, "t")
    response = {
        "assignments": [
            # Only assign one of the three; the other two fall back.
            {
                "doi": "10.1126/science.1225829",
                "bucket": "history",
                "rationale": "Foundational.",
            }
        ]
    }
    result = render_binning_from_response(response, task)
    # Foundational is set by LLM.
    assert result.bucket_by_doi["10.1126/science.1225829"] == "history"
    # Other two retain their deterministic bucket. We can look up the
    # deterministic bucket via the candidate list.
    cand_by_doi = {c.doi: c for c in task.candidates}
    for doi in ("10.1038/nature17946", "10.1038/nature24644"):
        assert result.bucket_by_doi[doi] == cand_by_doi[doi].deterministic_bucket


def test_render_binning_from_response_invalid_bucket_falls_back():
    """An invalid bucket value (e.g. 'foundational') falls back to det."""
    corpus = _make_corpus_with_metrics()
    task = prepare_binning_task(corpus, "t")
    response = {
        "assignments": [
            {
                "doi": "10.1126/science.1225829",
                "bucket": "foundational",  # NOT a valid bucket
                "rationale": "x",
            },
            {
                "doi": "10.1038/nature17946",
                "bucket": "development",
                "rationale": "ok",
            },
            {
                "doi": "10.1038/nature24644",
                "bucket": "sota",
                "rationale": "ok",
            },
        ]
    }
    result = render_binning_from_response(response, task)
    cand_by_doi = {c.doi: c for c in task.candidates}
    # Invalid bucket -> fall back to deterministic.
    assert (
        result.bucket_by_doi["10.1126/science.1225829"]
        == cand_by_doi["10.1126/science.1225829"].deterministic_bucket
    )
    assert result.bucket_by_doi["10.1038/nature17946"] == "development"


def test_render_binning_from_response_unknown_doi_dropped():
    """An LLM that invents a DOI gets it silently dropped."""
    corpus = _make_corpus_with_metrics()
    task = prepare_binning_task(corpus, "t")
    response = {
        "assignments": [
            {
                "doi": "10.9999/invented",
                "bucket": "history",
                "rationale": "Made up.",
            },
            {
                "doi": "10.1126/science.1225829",
                "bucket": "history",
                "rationale": "Real.",
            },
        ]
    }
    result = render_binning_from_response(response, task)
    # Only the real DOI is in the result.
    assert "10.9999/invented" not in result.bucket_by_doi
    assert result.bucket_by_doi["10.1126/science.1225829"] == "history"


def test_render_binning_from_response_none_returns_all_deterministic():
    """A None response returns a deterministic-only result."""
    corpus = _make_corpus_with_metrics()
    task = prepare_binning_task(corpus, "t")
    result = render_binning_from_response(None, task)
    cand_by_doi = {c.doi: c for c in task.candidates}
    for doi, cand in cand_by_doi.items():
        assert result.bucket_by_doi[doi] == cand.deterministic_bucket
    # No rationale for any DOI.
    assert result.rationale_by_doi == {}


def test_render_binning_from_response_malformed_response_falls_back():
    """A response missing 'assignments' or with a non-list value falls back."""
    corpus = _make_corpus_with_metrics()
    task = prepare_binning_task(corpus, "t")
    # 'assignments' is not a list.
    result = render_binning_from_response({"assignments": "oops"}, task)
    cand_by_doi = {c.doi: c for c in task.candidates}
    for doi, cand in cand_by_doi.items():
        assert result.bucket_by_doi[doi] == cand.deterministic_bucket


# ---------------------------------------------------------------------------
# assign_buckets_with_llm
# ---------------------------------------------------------------------------


def test_assign_buckets_with_llm_uses_callback():
    """When a callback is given, its output drives the result."""
    corpus = _make_corpus_with_metrics()

    captured: dict[str, Any] = {}

    def _callback(task: BinningTask) -> dict[str, Any]:
        captured["task"] = task
        return {
            "assignments": [
                {
                    "doi": c.doi,
                    "bucket": "history" if c.year and c.year < 2014 else "sota",
                    "rationale": "callback decision",
                }
                for c in task.candidates
            ]
        }

    result = assign_buckets_with_llm(corpus, "t", binner_callback=_callback)
    assert "task" in captured  # callback was invoked
    # The 2012 paper should be history; the 2016/2017 papers should be sota.
    assert result.bucket_by_doi["10.1126/science.1225829"] == "history"
    assert result.bucket_by_doi["10.1038/nature17946"] == "sota"
    assert result.bucket_by_doi["10.1038/nature24644"] == "sota"


def test_assign_buckets_with_llm_no_callback_returns_deterministic():
    """No callback + fallback=True returns deterministic-only buckets."""
    corpus = _make_corpus_with_metrics()
    result = assign_buckets_with_llm(corpus, "t", fallback_to_deterministic=True)
    metrics = corpus.metrics
    assert metrics is not None
    for doi in corpus.papers:
        assert result.bucket_by_doi[doi] == metrics.year_buckets[doi]


def test_assign_buckets_with_llm_no_callback_raises_when_disabled():
    """No callback + fallback=False raises MissingBinningCallback."""
    corpus = _make_corpus_with_metrics()
    with pytest.raises(MissingBinningCallback):
        assign_buckets_with_llm(corpus, "t", fallback_to_deterministic=False)


def test_assign_buckets_with_llm_callback_raises_falls_back_when_enabled():
    """A raising callback falls back to deterministic when allowed."""
    corpus = _make_corpus_with_metrics()

    def _bad(task: BinningTask) -> dict[str, Any]:
        raise RuntimeError("LLM exploded")

    result = assign_buckets_with_llm(
        corpus, "t", binner_callback=_bad, fallback_to_deterministic=True
    )
    metrics = corpus.metrics
    assert metrics is not None
    for doi in corpus.papers:
        assert result.bucket_by_doi[doi] == metrics.year_buckets[doi]


def test_assign_buckets_with_llm_callback_raises_propagates_when_disabled():
    """A raising callback propagates when fallback=False."""
    corpus = _make_corpus_with_metrics()

    def _bad(task: BinningTask) -> dict[str, Any]:
        raise RuntimeError("LLM exploded")

    with pytest.raises(RuntimeError, match="LLM exploded"):
        assign_buckets_with_llm(
            corpus,
            "t",
            binner_callback=_bad,
            fallback_to_deterministic=False,
        )


def test_assign_buckets_with_llm_empty_corpus_returns_empty():
    """An empty corpus returns an empty BinningResult — no LLM call."""
    corpus = Corpus(topic="empty", seeds=[])
    compute_metrics(corpus)

    def _callback(task: BinningTask) -> dict[str, Any]:
        raise AssertionError("callback should not be invoked for empty corpus")

    result = assign_buckets_with_llm(corpus, "empty", binner_callback=_callback)
    assert result.bucket_by_doi == {}
    assert result.rationale_by_doi == {}


def test_assign_buckets_with_llm_recovers_empty_history_bin():
    """The headline regression test: deterministic system might leave
    HISTORY underpopulated; the LLM moves the foundational paper there.
    """
    corpus = _make_synthetic_recent_corpus()
    foundational_doi = "10.1016/j.cell.2018.07.010"

    def _llm(task: BinningTask) -> dict[str, Any]:
        # The LLM reads the abstract, recognizes "foundational" and
        # "establishes the foundational principle", and returns history.
        assignments = []
        for c in task.candidates:
            if "foundational" in c.abstract.lower():
                assignments.append(
                    {
                        "doi": c.doi,
                        "bucket": "history",
                        "rationale": "Introduces CODEX (foundational).",
                    }
                )
            elif "state-of-the-art" in c.abstract.lower() or "most recent" in c.abstract.lower():
                assignments.append(
                    {
                        "doi": c.doi,
                        "bucket": "sota",
                        "rationale": "Most recent meaningful advance.",
                    }
                )
            else:
                assignments.append(
                    {
                        "doi": c.doi,
                        "bucket": "development",
                        "rationale": "Application or refinement.",
                    }
                )
        return {"assignments": assignments}

    result = assign_buckets_with_llm(corpus, "spatial transcriptomics CODEX", binner_callback=_llm)
    # The foundational paper lands in history.
    assert result.bucket_by_doi[foundational_doi] == "history"
    # History bucket is non-empty.
    assert result.coverage_summary["history"] >= 1
    assert result.coverage_summary["sota"] >= 1


def test_assign_buckets_with_llm_callback_returns_non_dict_falls_back():
    """A callback that returns a non-dict (e.g. None) falls back."""
    corpus = _make_corpus_with_metrics()

    def _callback(task: BinningTask) -> Any:
        return None  # type: ignore[return-value]

    result = assign_buckets_with_llm(
        corpus, "t", binner_callback=_callback, fallback_to_deterministic=True
    )
    metrics = corpus.metrics
    assert metrics is not None
    for doi in corpus.papers:
        assert result.bucket_by_doi[doi] == metrics.year_buckets[doi]


def test_coverage_summary_counts_correctly():
    """coverage_summary is a histogram over bucket_by_doi values."""
    corpus = _make_corpus_with_metrics()

    def _callback(task: BinningTask) -> dict[str, Any]:
        return {
            "assignments": [
                {"doi": c.doi, "bucket": "history", "rationale": "x"} for c in task.candidates
            ]
        }

    result = assign_buckets_with_llm(corpus, "t", binner_callback=_callback)
    # All three papers are in history.
    assert result.coverage_summary["history"] == 3
    assert result.coverage_summary["development"] == 0
    assert result.coverage_summary["sota"] == 0
