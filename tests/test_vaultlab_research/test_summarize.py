"""Unit tests for vaultlab.research.summarize.

The Anthropic API is faked via the ``_llm`` injection point on
:func:`summarize_paper`/:func:`summarize_corpus` so tests run offline.

Coverage
--------
* Tier C (no PDF) -> stub with citation stats only, no LLM call.
* Tier A (PDF present) -> Claude call -> structured summary -> markdown.
* Frontmatter parses as valid YAML.
* Connections wikilinks are slugified DOIs.
* ``write_summary_to_kb`` routes through ``vaultlab.kb.paths.summary_path``.
* Existing files are preserved when ``overwrite=False``.
* ``_extract_json`` tolerates code-fence wrapping and preambles.
* Auth resolver order: explicit > env > config > raise.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
import yaml

from vaultlab.kb.paths import slugify_doi, summary_path
from vaultlab.research import summarize as summ
from vaultlab.research.corpus import Corpus
from vaultlab.research.graph_metrics import compute_metrics
from vaultlab.research.paper import Paper
from vaultlab.research.summarize import (
    PaperSummary,
    SummarizationTask,
    SummarizeAuthError,
    _extract_json,
    build_summary_prompt,
    load_anthropic_api_key,
    prepare_summary_task,
    render_summary_from_response,
    render_summary_markdown,
    summarize_corpus,
    summarize_paper,
    summary_response_schema,
    write_summary_to_kb,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


_FAKE_PDF_BYTES = b"%PDF-1.4\n" + (b"x" * 4000)


def _fake_llm_returning(payload: dict[str, Any]):
    """Build a fake LLM caller that always returns ``payload``."""

    def _caller(*, pdf_bytes, prompt, api_key, model, **_):
        return payload, 12345, 678

    return _caller


def _make_corpus_with_metrics() -> Corpus:
    """Three-paper toy corpus with one foundational seed citation."""
    seed_a = Paper(
        title="Seed A: Programmable RNA-Guided DNA Endonuclease",
        authors=["Jinek M", "Doudna JA"],
        year=2012,
        journal="Science",
        doi="10.1126/science.1225829",
    )
    seed_b = Paper(
        title="Seed B: Cytidine Deaminase Base Editor",
        authors=["Komor AC", "Liu DR"],
        year=2016,
        journal="Nature",
        doi="10.1038/nature17946",
    )
    seed_c = Paper(
        title="Seed C: Adenine Base Editor",
        authors=["Gaudelli NM", "Liu DR"],
        year=2017,
        journal="Nature",
        doi="10.1038/nature24644",
    )
    corpus = Corpus(topic="test", seeds=[seed_a, seed_b, seed_c])
    for s in (seed_a, seed_b, seed_c):
        corpus.papers[s.doi.lower()] = s

    # B and C both cite A. A cites nothing in the corpus. C also cites B.
    corpus.references["10.1126/science.1225829"] = []
    corpus.references["10.1038/nature17946"] = ["10.1126/science.1225829"]
    corpus.references["10.1038/nature24644"] = [
        "10.1126/science.1225829",
        "10.1038/nature17946",
    ]
    compute_metrics(corpus)
    return corpus


# ---------------------------------------------------------------------------
# Auth resolver
# ---------------------------------------------------------------------------


def test_load_anthropic_api_key_explicit_wins(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "from-env")
    assert load_anthropic_api_key("explicit-key") == "explicit-key"


def test_load_anthropic_api_key_env_when_no_explicit(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key")
    assert load_anthropic_api_key(None) == "env-key"


def test_load_anthropic_api_key_raises_when_unset(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    # Force config lookup to return empty so the error path triggers.
    monkeypatch.setattr(
        "vaultlab.research.config.get_config",
        lambda *a, **k: {},
    )
    with pytest.raises(SummarizeAuthError) as exc_info:
        load_anthropic_api_key(None)
    msg = str(exc_info.value)
    assert "ANTHROPIC_API_KEY" in msg
    assert "research_apis.json" in msg


def test_load_anthropic_api_key_falls_back_to_config(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(
        "vaultlab.research.config.get_config",
        lambda *a, **k: {"anthropic_api_key": "config-key"},
    )
    assert load_anthropic_api_key(None) == "config-key"


# ---------------------------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------------------------


def test_extract_json_plain():
    blob = '{"a": 1, "b": [2, 3]}'
    assert _extract_json(blob) == {"a": 1, "b": [2, 3]}


def test_extract_json_with_code_fence():
    blob = "```json\n" + '{"tldr": "x", "key_findings": []}' + "\n```"
    out = _extract_json(blob)
    assert out["tldr"] == "x"


def test_extract_json_with_preamble_and_braces_in_strings():
    blob = (
        "Here's the summary:\n\n"
        '{"tldr": "We use the {curly} pattern", "key_findings": ["finding [p2]"]}'
    )
    out = _extract_json(blob)
    assert out["tldr"] == "We use the {curly} pattern"
    assert out["key_findings"] == ["finding [p2]"]


def test_extract_json_raises_on_no_json():
    with pytest.raises(ValueError):
        _extract_json("Sorry, I can't help with that.")


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


def test_build_summary_prompt_embeds_metadata():
    prompt = build_summary_prompt(
        paper_metadata={
            "title": "My Title",
            "authors": ["Smith J", "Doe A"],
            "year": 2020,
            "journal": "Nature",
            "doi": "10.1/abc",
        },
        crossref_refs_missing=False,
    )
    assert "My Title" in prompt
    assert "Smith J" in prompt
    assert "10.1/abc" in prompt
    assert "CrossRef already provided" in prompt
    assert "extracted_references" in prompt


def test_build_summary_prompt_asks_for_refs_when_missing():
    prompt = build_summary_prompt(
        paper_metadata={"title": "X", "authors": [], "year": 2020, "doi": "10.1/y"},
        crossref_refs_missing=True,
    )
    assert "CrossRef did NOT provide" in prompt


# ---------------------------------------------------------------------------
# summarize_paper — Tier C (stub, no LLM)
# ---------------------------------------------------------------------------


def test_summarize_paper_tier_c_when_no_pdf(tmp_path):
    corpus = _make_corpus_with_metrics()
    metrics = corpus.metrics
    summary = summarize_paper(
        doi="10.1126/science.1225829",
        pdf_path=None,  # -> Tier C
        paper_metadata={
            "title": "Seed A",
            "authors": ["Jinek M"],
            "year": 2012,
            "journal": "Science",
        },
        corpus_metrics=metrics,
        corpus=corpus,
    )
    assert summary.tier == "C"
    assert summary.tldr == ""
    assert summary.key_findings == []
    # Citation stats still populated.
    assert summary.og_score > 0  # cited by 2 seeds out of 3
    # Year-bucket assignment populated.
    assert summary.year_bucket in ("history", "development", "sota", "unknown")
    # Connections still computed for Tier C.
    assert all(
        "/" not in s
        for s in summary.connections_cited_by_in_set + summary.connections_references
    )


def test_summarize_paper_tier_c_when_pdf_missing_on_disk(tmp_path):
    """A path argument that doesn't exist also means Tier C."""
    summary = summarize_paper(
        doi="10.1/nope",
        pdf_path=tmp_path / "missing.pdf",
        paper_metadata={"title": "Missing", "authors": [], "year": 0, "journal": ""},
    )
    assert summary.tier == "C"
    assert summary.source_pdf == ""


# ---------------------------------------------------------------------------
# summarize_paper — Tier A with mocked LLM
# ---------------------------------------------------------------------------


def test_summarize_paper_tier_a_uses_llm(tmp_path):
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(_FAKE_PDF_BYTES)

    corpus = _make_corpus_with_metrics()

    fake_response = {
        "tldr": (
            "We discover programmable cleavage. The system is dual-RNA guided. "
            "It enables genome editing."
        ),
        "why_it_matters": [
            "Founded the CRISPR-Cas9 era",
            "Demonstrated programmable nucleases",
        ],
        "methods_summary": "We purified Cas9 and tested cleavage in vitro.",
        "key_findings": [
            "Cas9-tracrRNA-crRNA forms a programmable RNP [p3]",
            "Cleavage is sequence-specific [p4]",
            "PAM is required [p5]",
        ],
        "extracted_references": [],
    }

    summary = summarize_paper(
        doi="10.1126/science.1225829",
        pdf_path=pdf,
        paper_metadata={
            "title": "Seed A",
            "authors": ["Jinek M", "Doudna JA"],
            "year": 2012,
            "journal": "Science",
        },
        corpus_metrics=corpus.metrics,
        corpus=corpus,
        acquisition_source="unpaywall",
        acquisition_license="cc-by",
        _llm=_fake_llm_returning(fake_response),
    )
    assert summary.tier == "A"
    assert "programmable" in summary.tldr.lower()
    assert len(summary.key_findings) == 3
    assert all("[p" in f or "[unknown]" in f for f in summary.key_findings)
    assert summary.tokens_input == 12345
    assert summary.tokens_output == 678
    assert summary.acquisition_source == "unpaywall"
    assert summary.acquisition_license == "cc-by"
    assert summary.source_pdf == "Sources/Papers/10.1126_science.1225829.pdf"


def test_summarize_paper_passes_refs_missing_flag_to_prompt(tmp_path):
    pdf = tmp_path / "p.pdf"
    pdf.write_bytes(_FAKE_PDF_BYTES)

    seen_prompts: list[str] = []

    def _capture(*, pdf_bytes, prompt, api_key, model, **_):
        seen_prompts.append(prompt)
        return {
            "tldr": "x. y. z.",
            "why_it_matters": [],
            "methods_summary": "",
            "key_findings": ["a [p1]", "b [p2]", "c [p3]"],
            "extracted_references": ["10.1/aa", "10.1/bb"],
        }, 1, 1

    summary = summarize_paper(
        doi="10.1/foo",
        pdf_path=pdf,
        paper_metadata={"title": "T", "authors": [], "year": 2024, "journal": ""},
        crossref_refs_missing=True,
        _llm=_capture,
    )
    assert summary.extracted_references == ["10.1/aa", "10.1/bb"]
    assert "CrossRef did NOT provide" in seen_prompts[0]


# ---------------------------------------------------------------------------
# Markdown rendering + frontmatter validity
# ---------------------------------------------------------------------------


def test_render_markdown_frontmatter_is_valid_yaml(tmp_path):
    summary = PaperSummary(
        doi="10.1/abc",
        title="Test Paper",
        authors=["A", "B"],
        year=2020,
        journal="Journal",
        og_score=0.5,
        forward_influence=2,
        year_bucket="history",
        role_in_set="foundational",
        tier="A",
        extracted_at="2026-04-29T12:00:00",
        source_pdf="Sources/Papers/10.1_abc.pdf",
        tldr="Sentence 1. Sentence 2. Sentence 3.",
        why_it_matters=["bullet 1"],
        methods_summary="We did X.",
        key_findings=["finding [p1]", "finding [p2]", "finding [p3]"],
    )
    md = render_summary_markdown(summary)

    # Strip the frontmatter and parse.
    assert md.startswith("---\n")
    end = md.find("\n---\n", 4)
    assert end > 0
    fm_text = md[4:end]
    fm = yaml.safe_load(fm_text)
    assert fm["doi"] == "10.1/abc"
    assert fm["title"] == "Test Paper"
    assert fm["og_score"] == 0.5
    assert fm["tier"] == "A"
    assert fm["role_in_set"] == "foundational"


def test_render_markdown_uses_wikilinks_for_connections():
    summary = PaperSummary(
        doi="10.1/foo",
        title="t",
        connections_references=["10.1126_science.1225829"],
        connections_cited_by_in_set=["10.1038_nature17946", "10.1038_nature24644"],
        tier="A",
        tldr="x. y. z.",
        key_findings=["a [p1]"],
    )
    md = render_summary_markdown(summary)
    assert "[[10.1126_science.1225829]]" in md
    assert "[[10.1038_nature17946]]" in md
    assert "[[10.1038_nature24644]]" in md


def test_render_markdown_tier_c_indicates_stub():
    summary = PaperSummary(doi="10.1/foo", title="t", tier="C")
    md = render_summary_markdown(summary)
    assert "Tier C stub" in md


def test_connections_use_doi_slugs_not_raw_dois():
    """Wikilinks must use the same slugify_doi format as paths.summary_path."""
    corpus = _make_corpus_with_metrics()
    summary = summarize_paper(
        doi="10.1126/science.1225829",
        pdf_path=None,
        paper_metadata={"title": "x", "authors": [], "year": 2012, "journal": ""},
        corpus_metrics=corpus.metrics,
        corpus=corpus,
    )
    for slug in summary.connections_cited_by_in_set:
        # Slugs never carry slashes — they use underscore replacements.
        assert "/" not in slug
        # And they round-trip through slugify_doi (idempotent on slugs).
        assert slug == slugify_doi(slug)


# ---------------------------------------------------------------------------
# write_summary_to_kb
# ---------------------------------------------------------------------------


def test_write_summary_to_kb_routes_through_paths(tmp_path):
    summary = PaperSummary(
        doi="10.1126/science.1225829",
        title="t",
        tier="C",
    )
    written = write_summary_to_kb(summary, tmp_path)
    expected = summary_path(tmp_path, summary.doi)
    assert written == expected
    assert expected.exists()
    assert expected.parent.name == "Summaries"
    assert expected.parent.parent.name == "Wiki"


def test_write_summary_to_kb_keeps_existing_when_no_overwrite(tmp_path):
    target = summary_path(tmp_path, "10.1/abc")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("hand-edited content", encoding="utf-8")

    summary = PaperSummary(doi="10.1/abc", title="t", tier="A", tldr="x. y. z.")
    write_summary_to_kb(summary, tmp_path, overwrite=False)
    body = target.read_text(encoding="utf-8")
    # Existing content preserved.
    assert "hand-edited content" in body
    # Regen marker appended.
    assert "vaultlab regen attempt:" in body


def test_write_summary_to_kb_overwrites_when_flag_set(tmp_path):
    target = summary_path(tmp_path, "10.1/abc")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("OLD CONTENT", encoding="utf-8")

    summary = PaperSummary(
        doi="10.1/abc",
        title="t",
        tier="A",
        tldr="x. y. z.",
        key_findings=["a [p1]"],
    )
    write_summary_to_kb(summary, tmp_path, overwrite=True)
    new_body = target.read_text(encoding="utf-8")
    assert "OLD CONTENT" not in new_body
    assert "x. y. z." in new_body


# ---------------------------------------------------------------------------
# summarize_corpus end-to-end (mocked LLM)
# ---------------------------------------------------------------------------


def test_summarize_corpus_writes_one_file_per_paper(tmp_path):
    corpus = _make_corpus_with_metrics()
    pdf_cache = tmp_path / "_cache"
    pdf_cache.mkdir()
    kb_root = tmp_path / "kb"

    # Provide PDFs only for two of the three seeds; the third should
    # produce a Tier C stub.
    from vaultlab.research.acquisition import cache_path_for

    for doi in ("10.1126/science.1225829", "10.1038/nature17946"):
        cache_path_for(doi, pdf_cache).write_bytes(_FAKE_PDF_BYTES)

    fake = _fake_llm_returning(
        {
            "tldr": "A. B. C.",
            "why_it_matters": ["m1"],
            "methods_summary": "methods",
            "key_findings": ["f1 [p1]", "f2 [p2]", "f3 [p3]"],
            "extracted_references": [],
        }
    )

    summaries = summarize_corpus(
        corpus,
        pdf_cache_dir=pdf_cache,
        kb_root=kb_root,
        parallel=1,
        _llm=fake,
    )

    assert len(summaries) == 3
    tiers = {doi: s.tier for doi, s in summaries.items()}
    assert tiers["10.1126/science.1225829"] == "A"
    assert tiers["10.1038/nature17946"] == "A"
    assert tiers["10.1038/nature24644"] == "C"  # no PDF cached

    for doi in summaries:
        assert summary_path(kb_root, doi).exists()


def test_summarize_corpus_tier_c_stub_does_not_call_llm(tmp_path):
    corpus = _make_corpus_with_metrics()
    pdf_cache = tmp_path / "_empty_cache"
    pdf_cache.mkdir()
    kb_root = tmp_path / "kb"

    call_count = {"n": 0}

    def _llm_that_must_not_be_called(*args, **kwargs):
        call_count["n"] += 1
        raise AssertionError("LLM should not be called for Tier C papers")

    summaries = summarize_corpus(
        corpus,
        pdf_cache_dir=pdf_cache,
        kb_root=kb_root,
        parallel=1,
        _llm=_llm_that_must_not_be_called,
    )
    assert call_count["n"] == 0
    assert all(s.tier == "C" for s in summaries.values())
    # Files written for all three.
    for doi in summaries:
        assert summary_path(kb_root, doi).exists()


# ---------------------------------------------------------------------------
# Claude-Code-callable path: prepare_summary_task / render_summary_from_response
# ---------------------------------------------------------------------------


def test_summary_response_schema_is_valid_json_schema():
    """Schema must be a dict with 'type' and 'properties' for a JSON object."""
    schema = summary_response_schema()
    assert schema["type"] == "object"
    assert "properties" in schema
    # Required keys match the prompt instructions.
    assert set(schema["required"]) == {
        "tldr",
        "why_it_matters",
        "methods_summary",
        "key_findings",
        "extracted_references",
    }
    # Each declared property has a 'type' annotation.
    for key, spec in schema["properties"].items():
        assert "type" in spec, f"missing type for property {key!r}"
    # Schema round-trips through JSON.
    assert json.loads(json.dumps(schema)) == schema


def test_prepare_summary_task_makes_no_http_calls(tmp_path, monkeypatch):
    """Sanity: prepare path must not import / call anthropic."""
    # Force the anthropic SDK to blow up if loaded.
    import sys

    if "anthropic" in sys.modules:
        # Replace with a guard module that raises on attribute access.
        class _Guard:
            def __getattr__(self, name):
                raise AssertionError(
                    f"prepare_summary_task touched anthropic.{name}"
                )

        monkeypatch.setitem(sys.modules, "anthropic", _Guard())

    pdf = tmp_path / "p.pdf"
    pdf.write_bytes(_FAKE_PDF_BYTES)
    corpus = _make_corpus_with_metrics()

    task = prepare_summary_task(
        doi="10.1126/science.1225829",
        pdf_path=pdf,
        paper_metadata={
            "title": "Programmable RNA-Guided DNA Endonuclease",
            "authors": ["Jinek M", "Doudna JA"],
            "year": 2012,
            "journal": "Science",
        },
        corpus_metrics=corpus.metrics,
        corpus=corpus,
        kb_root=tmp_path,
        acquisition_source="unpaywall",
        acquisition_license="cc-by",
    )

    assert isinstance(task, SummarizationTask)
    assert task.doi == "10.1126/science.1225829"
    assert task.pdf_path == pdf
    assert task.tier == "A"
    assert task.acquisition_source == "unpaywall"
    assert task.output_path == summary_path(tmp_path, task.doi)
    assert task.response_schema == summary_response_schema()
    # Citation stats already populated.
    assert task.citation_stats["og_score"] > 0
    # Output path inside the KB tree.
    assert task.output_path.parent.name == "Summaries"


def test_prepare_summary_task_prompt_matches_sdk_prompt(tmp_path):
    """The prompt produced by prepare_summary_task must be identical to the
    prompt the SDK path would build for the same paper.

    This is the contract that lets a Claude Code reader produce JSON
    that ``render_summary_from_response`` happily consumes — both paths
    are answering the SAME question.
    """
    pdf = tmp_path / "p.pdf"
    pdf.write_bytes(_FAKE_PDF_BYTES)
    corpus = _make_corpus_with_metrics()

    task = prepare_summary_task(
        doi="10.1126/science.1225829",
        pdf_path=pdf,
        paper_metadata={
            "title": "Seed A",
            "authors": ["Jinek M"],
            "year": 2012,
            "journal": "Science",
        },
        corpus_metrics=corpus.metrics,
        corpus=corpus,
        kb_root=tmp_path,
    )

    # The same role_in_set is used in both paths.
    expected_prompt = build_summary_prompt(
        paper_metadata={
            "title": "Seed A",
            "authors": ["Jinek M"],
            "year": 2012,
            "journal": "Science",
            "doi": "10.1126/science.1225829",
        },
        crossref_refs_missing=False,
        role_hint=task.citation_stats["role_in_set"],
    )
    assert task.prompt == expected_prompt
    # Critical schema cues are embedded in the prompt.
    assert "tldr" in task.prompt
    assert "key_findings" in task.prompt
    assert "extracted_references" in task.prompt


def test_render_summary_from_response_populates_paper_summary(tmp_path):
    """A captured JSON response yields a fully-populated PaperSummary."""
    pdf = tmp_path / "p.pdf"
    pdf.write_bytes(_FAKE_PDF_BYTES)
    corpus = _make_corpus_with_metrics()
    task = prepare_summary_task(
        doi="10.1126/science.1225829",
        pdf_path=pdf,
        paper_metadata={
            "title": "Seed A",
            "authors": ["Jinek M", "Doudna JA"],
            "year": 2012,
            "journal": "Science",
        },
        corpus_metrics=corpus.metrics,
        corpus=corpus,
        kb_root=tmp_path,
        acquisition_source="unpaywall",
        acquisition_license="cc-by",
    )

    response = {
        "tldr": "Sentence A. Sentence B. Sentence C.",
        "why_it_matters": ["First", "Second"],
        "methods_summary": "We did X with Y.",
        "key_findings": ["alpha [p1]", "beta [p2]", "gamma [p3]"],
        "extracted_references": [],
    }
    summary = render_summary_from_response(
        task,
        response,
        corpus_metrics=corpus.metrics,
        corpus=corpus,
        tokens_input=1000,
        tokens_output=500,
    )

    assert isinstance(summary, PaperSummary)
    assert summary.tier == "A"
    assert summary.tldr == "Sentence A. Sentence B. Sentence C."
    assert summary.why_it_matters == ["First", "Second"]
    assert summary.methods_summary == "We did X with Y."
    assert summary.key_findings == ["alpha [p1]", "beta [p2]", "gamma [p3]"]
    assert summary.extracted_references == []
    # Citation stats survive the round-trip.
    assert summary.og_score > 0
    # Provenance applied.
    assert summary.acquisition_source == "unpaywall"
    assert summary.tokens_input == 1000
    assert summary.tokens_output == 500
    # Source pdf set.
    assert summary.source_pdf == "Sources/Papers/10.1126_science.1225829.pdf"


def test_render_summary_from_response_then_write(tmp_path):
    """Full Claude-Code path: prepare -> render -> write_summary_to_kb."""
    pdf = tmp_path / "p.pdf"
    pdf.write_bytes(_FAKE_PDF_BYTES)
    corpus = _make_corpus_with_metrics()
    task = prepare_summary_task(
        doi="10.1126/science.1225829",
        pdf_path=pdf,
        paper_metadata={
            "title": "Seed A",
            "authors": ["Jinek M"],
            "year": 2012,
            "journal": "Science",
        },
        corpus_metrics=corpus.metrics,
        corpus=corpus,
        kb_root=tmp_path,
    )
    response = {
        "tldr": "x. y. z.",
        "why_it_matters": ["m"],
        "methods_summary": "ms",
        "key_findings": ["a [p1]", "b [p2]", "c [p3]"],
        "extracted_references": [],
    }
    summary = render_summary_from_response(
        task, response, corpus_metrics=corpus.metrics, corpus=corpus
    )
    written = write_summary_to_kb(summary, tmp_path, overwrite=True)
    assert written == task.output_path
    assert written.exists()
    body = written.read_text(encoding="utf-8")
    assert "x. y. z." in body
    # Frontmatter parses.
    assert body.startswith("---\n")
    end = body.find("\n---\n", 4)
    fm = yaml.safe_load(body[4:end])
    assert fm["tier"] == "A"


def test_summarize_corpus_with_reader(tmp_path):
    """Reader mode: summarize_corpus invokes the reader callback per paper."""
    corpus = _make_corpus_with_metrics()
    pdf_cache = tmp_path / "_cache"
    pdf_cache.mkdir()
    kb_root = tmp_path / "kb"

    from vaultlab.research.acquisition import cache_path_for

    # Two PDFs => two reader calls + one Tier-C stub.
    for doi in ("10.1126/science.1225829", "10.1038/nature17946"):
        cache_path_for(doi, pdf_cache).write_bytes(_FAKE_PDF_BYTES)

    seen_tasks: list[SummarizationTask] = []

    def _reader(task: SummarizationTask) -> dict[str, Any]:
        seen_tasks.append(task)
        return {
            "tldr": f"[reader] {task.doi}. b. c.",
            "why_it_matters": ["r1"],
            "methods_summary": "m",
            "key_findings": ["a [p1]", "b [p2]", "c [p3]"],
            "extracted_references": [],
        }

    summaries = summarize_corpus(
        corpus,
        pdf_cache_dir=pdf_cache,
        kb_root=kb_root,
        reader=_reader,
    )

    # Reader invoked exactly once per Tier-A paper.
    assert len(seen_tasks) == 2
    # All summaries written, including the Tier-C stub.
    assert len(summaries) == 3
    tiers = {doi: s.tier for doi, s in summaries.items()}
    assert tiers["10.1126/science.1225829"] == "A"
    assert tiers["10.1038/nature17946"] == "A"
    assert tiers["10.1038/nature24644"] == "C"
    # Tier-A summaries carry the reader's tldr.
    assert "[reader]" in summaries["10.1126/science.1225829"].tldr
    # Each task's output_path points at the canonical Wiki/Summaries location.
    for task in seen_tasks:
        assert task.output_path == summary_path(kb_root, task.doi)
        assert task.output_path.exists()


def test_summarize_corpus_reader_mode_does_not_use_anthropic(tmp_path, monkeypatch):
    """Reader mode must not load the anthropic SDK at all."""
    import sys

    class _Guard:
        def __getattr__(self, name):
            raise AssertionError(
                f"summarize_corpus(reader=...) touched anthropic.{name}"
            )

    monkeypatch.setitem(sys.modules, "anthropic", _Guard())
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    corpus = _make_corpus_with_metrics()
    pdf_cache = tmp_path / "_cache"
    pdf_cache.mkdir()
    kb_root = tmp_path / "kb"
    from vaultlab.research.acquisition import cache_path_for

    cache_path_for("10.1126/science.1225829", pdf_cache).write_bytes(_FAKE_PDF_BYTES)

    def _reader(task):
        return {
            "tldr": "x. y. z.",
            "why_it_matters": [],
            "methods_summary": "",
            "key_findings": ["a [p1]", "b [p2]", "c [p3]"],
            "extracted_references": [],
        }

    summaries = summarize_corpus(
        corpus,
        pdf_cache_dir=pdf_cache,
        kb_root=kb_root,
        reader=_reader,
    )
    assert len(summaries) == 3
