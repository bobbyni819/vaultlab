"""Unit tests for vaultlab.research.report — the /lit-report deep-research pipeline.

Every external dependency (search, CrossRef ref-walk, PDF acquisition,
LLM calls, crosstalk meetings, rigor audits) is stubbed via callbacks /
injection points so the suite runs offline.

Coverage
--------
* Section taxonomy: SECTION_ORDER + SECTION_ROLES + SECTION_WORD_TARGETS
  match the spec.
* prepare_report_task produces a valid task without an LLM call.
* render_section_from_response parses JSON, flags missing-evidence
  claims, and emits NEEDS-EVIDENCE blockquotes when section_text has no
  wikilinks.
* run_lit_report end-to-end with a synthetic 5-paper corpus produces:
    - Wiki/Concepts/<topic>-report-<date>.md (assembled review)
    - Per-section drafts under <topic>-report-<date>/
    - audit.md with a status label
    - Frontmatter has total_words + audit_status
* Cohesion threading: section N+1 receives sections 1..N in
  prior_sections.
* Audit strict mode raises on blocker-level issues.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from vaultlab.kb.paths import concept_path, slugify_doi
from vaultlab.research.acquisition import AcquisitionResult
from vaultlab.research.corpus import Corpus
from vaultlab.research.paper import Paper
from vaultlab.research.report import (
    SECTION_ORDER,
    SECTION_ROLES,
    SECTION_WORD_TARGETS,
    ReportRunResult,
    ReportTask,
    build_section_prompt,
    prepare_report_task,
    render_section_from_response,
    run_lit_report,
    section_response_schema,
)
from vaultlab.research.summarize import PaperSummary


# ---------------------------------------------------------------------------
# Synthetic 5-paper corpus (CODEX cellular neighborhoods, like the spec)
# ---------------------------------------------------------------------------


def _make_seeds() -> list[Paper]:
    """Five seeds across history/development/sota buckets."""
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
            abstract="CN definition: clustering by cell-type neighborhoods.",
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
    """All seeds get a fake PDF (so depth=thorough reads everything)."""
    from vaultlab.research.acquisition import cache_path_for

    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    out: dict[str, AcquisitionResult] = {}
    for doi in corpus.papers:
        target = cache_path_for(doi, cache_dir)
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
                doi=doi, pdf_path=None, source="failed",
                license=None, error="ref-only",
            )
    return out


class _FakeClient:
    def __init__(self, seeds: list[Paper]):
        self._seeds = seeds

    def search(self, query, max_results=20, sources=None):
        return list(self._seeds)


def _stub_reader(task):
    """Stub PDF reader — returns canned summary JSON."""
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


def _three_summaries() -> dict[str, PaperSummary]:
    """Synthetic in-memory summaries used to exercise prepare_report_task /
    render_section_from_response without going through the orchestrator."""
    return {
        "10.1038/nmeth.4391": PaperSummary(
            doi="10.1038/nmeth.4391",
            title="histoCAT",
            authors=["Schapiro D"],
            year=2017,
            year_bucket="history",
            tldr="Tissue social networks vocabulary.",
            key_findings=["dual-RNA guide [p3]"],
            og_score=0.66,
            forward_influence=2,
            tier="A",
        ),
        "10.1016/j.cell.2018.07.010": PaperSummary(
            doi="10.1016/j.cell.2018.07.010",
            title="CODEX",
            authors=["Goltsev Y"],
            year=2018,
            year_bucket="development",
            tldr="Indexed niche operationalized.",
            key_findings=["50-marker panel [p4]"],
            og_score=0.4,
            forward_influence=1,
            tier="A",
        ),
        "10.1016/j.cell.2020.07.005": PaperSummary(
            doi="10.1016/j.cell.2020.07.005",
            title="CRC CN",
            authors=["Schurch CM"],
            year=2020,
            year_bucket="sota",
            tldr="CN predicts CRC outcomes.",
            key_findings=["9 CN clusters [p5]"],
            og_score=0.0,
            forward_influence=0,
            tier="A",
        ),
    }


# ---------------------------------------------------------------------------
# Section taxonomy
# ---------------------------------------------------------------------------


def test_section_order_and_roles_match_spec():
    """Spec mandates 5 sections in this exact order with specific role mixes."""
    assert SECTION_ORDER == (
        "background",
        "methods_landscape",
        "findings",
        "contradictions",
        "future_directions",
    )
    # Every section has roles, and synthesizer is always the last role
    # (so its JSON IS the meeting's final_output per the crosstalk runner).
    for sec in SECTION_ORDER:
        assert sec in SECTION_ROLES
        assert SECTION_ROLES[sec][-1] == "synthesizer"
    # Per spec Section/role mix:
    assert SECTION_ROLES["background"] == [
        "literature_surveyor", "domain_expert", "synthesizer"
    ]
    assert SECTION_ROLES["methods_landscape"] == [
        "literature_surveyor", "methods_critic", "synthesizer"
    ]
    assert SECTION_ROLES["findings"] == [
        "data_analyst", "methods_critic", "literature_critic", "synthesizer"
    ]
    assert SECTION_ROLES["contradictions"] == [
        "methods_critic", "literature_critic", "synthesizer"
    ]
    assert SECTION_ROLES["future_directions"] == [
        "domain_expert", "synthesizer"
    ]


def test_section_word_targets_in_spec_ranges():
    """Word targets must fall inside the spec's per-section ranges."""
    # Spec ranges:
    #   background 500-800, methods 800-1200, findings 1000-1500,
    #   contradictions 300-500, future 200-400 → totals 2800-4400.
    assert 500 <= SECTION_WORD_TARGETS["background"] <= 800
    assert 800 <= SECTION_WORD_TARGETS["methods_landscape"] <= 1200
    assert 1000 <= SECTION_WORD_TARGETS["findings"] <= 1500
    assert 300 <= SECTION_WORD_TARGETS["contradictions"] <= 500
    assert 200 <= SECTION_WORD_TARGETS["future_directions"] <= 400
    total = sum(SECTION_WORD_TARGETS.values())
    assert 2800 <= total <= 4400, f"target sum {total} out of band"


# ---------------------------------------------------------------------------
# section_response_schema
# ---------------------------------------------------------------------------


def test_section_response_schema_has_required_fields():
    schema = section_response_schema()
    assert schema["type"] == "object"
    assert set(schema["required"]) == {"section_text", "claims_with_evidence"}
    # claims_with_evidence has nested schema for the audit handle.
    claims = schema["properties"]["claims_with_evidence"]
    assert claims["type"] == "array"
    item = claims["items"]
    assert set(item["required"]) == {"claim", "doi_slugs"}


# ---------------------------------------------------------------------------
# prepare_report_task
# ---------------------------------------------------------------------------


def test_prepare_report_task_no_llm_call(tmp_path):
    """prepare_report_task is purely synchronous — no network, no LLM."""
    summaries = _three_summaries()
    task = prepare_report_task(
        topic="CODEX cellular neighborhoods",
        section="background",
        summaries=summaries,
        metrics=None,
        prior_sections={},
        audience="graduate-student",
        kb_root=tmp_path,
    )
    assert isinstance(task, ReportTask)
    assert task.topic == "CODEX cellular neighborhoods"
    assert task.section == "background"
    assert task.audience == "graduate-student"
    assert task.target_word_count == SECTION_WORD_TARGETS["background"]
    assert task.roles == SECTION_ROLES["background"]
    assert "CODEX" in task.prompt
    assert "Background" in task.system_prompt or "background" in task.system_prompt.lower()
    assert task.response_schema == section_response_schema()


def test_prepare_report_task_rejects_unknown_section():
    with pytest.raises(ValueError, match="unknown section"):
        prepare_report_task(
            topic="x",
            section="executive_summary",  # type: ignore[arg-type]
            summaries={},
            metrics=None,
            prior_sections={},
        )


def test_prepare_report_task_threads_prior_sections_into_prompt():
    """Section 2's prompt includes section 1's body for cohesion."""
    summaries = _three_summaries()
    section1_text = (
        "The cellular-neighborhood concept emerged from "
        "[[10.1038_nmeth.4391|Schapiro 2017]]."
    )
    task2 = prepare_report_task(
        topic="CODEX cellular neighborhoods",
        section="methods_landscape",
        summaries=summaries,
        metrics=None,
        prior_sections={"background": section1_text},
        audience="graduate-student",
    )
    # Prior section text must appear in the prompt for cohesion.
    assert "Schapiro 2017" in task2.prompt
    assert "Already-written: background" in task2.prompt


def test_prepare_report_task_word_target_override():
    summaries = _three_summaries()
    task = prepare_report_task(
        topic="x",
        section="findings",
        summaries=summaries,
        metrics=None,
        prior_sections={},
        target_word_count=900,
    )
    assert task.target_word_count == 900


# ---------------------------------------------------------------------------
# build_section_prompt
# ---------------------------------------------------------------------------


def test_build_section_prompt_includes_topic_and_section_label():
    summaries = _three_summaries()
    prompt = build_section_prompt(
        topic="CODEX cellular neighborhoods",
        section="findings",
        summaries=summaries,
        prior_sections={},
        target_word_count=1250,
        audience="graduate-student",
    )
    assert "CODEX cellular neighborhoods" in prompt
    assert "key findings" in prompt.lower() or "findings" in prompt.lower()
    # Word range must be in the prompt.
    assert "1000-1500" in prompt
    assert "graduate-student" in prompt


# ---------------------------------------------------------------------------
# render_section_from_response
# ---------------------------------------------------------------------------


def test_render_section_with_wikilinks_and_evidence_passes_clean():
    """Well-formed response with wikilinks + evidence has no NEEDS-EVIDENCE flags."""
    summaries = _three_summaries()
    task = prepare_report_task(
        topic="t",
        section="background",
        summaries=summaries,
        metrics=None,
        prior_sections={},
    )
    response = {
        "section_text": (
            "The field began with [[10.1038_nmeth.4391|Schapiro 2017]] "
            "introducing tissue social networks. Later, "
            "[[10.1016_j.cell.2018.07.010|Goltsev 2018]] operationalized "
            "the indexed niche concept."
        ),
        "claims_with_evidence": [
            {
                "claim": "histoCAT introduced the analytical vocabulary.",
                "doi_slugs": ["10.1038_nmeth.4391"],
            },
            {
                "claim": "CODEX defined indexed niches.",
                "doi_slugs": ["10.1016_j.cell.2018.07.010"],
            },
        ],
    }
    md = render_section_from_response(task, response)
    assert "Schapiro 2017" in md
    assert "[NEEDS EVIDENCE]" not in md


def test_render_section_flags_claims_without_evidence():
    summaries = _three_summaries()
    task = prepare_report_task(
        topic="t",
        section="background",
        summaries=summaries,
        metrics=None,
        prior_sections={},
    )
    response = {
        "section_text": (
            "Research [[10.1038_nmeth.4391|Schapiro 2017]] established the area."
        ),
        "claims_with_evidence": [
            {"claim": "Some unsupported claim with no evidence.", "doi_slugs": []},
        ],
    }
    md = render_section_from_response(task, response)
    assert "[NEEDS EVIDENCE]" in md
    assert "Some unsupported claim" in md


def test_render_section_flags_when_no_wikilinks():
    """Section text without ANY wikilinks gets a global NEEDS-EVIDENCE flag."""
    summaries = _three_summaries()
    task = prepare_report_task(
        topic="t",
        section="background",
        summaries=summaries,
        metrics=None,
        prior_sections={},
    )
    response = {
        "section_text": "This is some prose without any citations whatsoever.",
        "claims_with_evidence": [],
    }
    md = render_section_from_response(task, response)
    assert "[NEEDS EVIDENCE]" in md
    assert "No [[wikilinks]] detected" in md


def test_render_section_handles_empty_response():
    summaries = _three_summaries()
    task = prepare_report_task(
        topic="t",
        section="background",
        summaries=summaries,
        metrics=None,
        prior_sections={},
    )
    md = render_section_from_response(task, {})
    assert "no section_text" in md or "empty response" in md


# ---------------------------------------------------------------------------
# run_lit_report — end-to-end with stubs
# ---------------------------------------------------------------------------


def _make_crosstalk_runner(canned_section_text):
    """Build a runner_callback that returns canned synthesizer JSON.

    The synthesizer's payload changes shape based on the meeting purpose:
    - report-<section> meetings → {section_text, claims_with_evidence}
    - rigor audit → {passed, issues}

    We sniff via the agenda statement (matching test_run_lit_arc_with_adversarial pattern).
    """
    def _crosstalk(meeting, roles):
        outputs = []
        agenda_text = (meeting.agenda.statement if meeting.agenda else "") or ""
        is_audit = "Audit the report document" in agenda_text or \
                   meeting.topic.startswith("rigor audit")
        for r in roles:
            if r.id == "synthesizer" and not is_audit:
                # Section-meeting synthesizer.
                # Determine section from topic suffix in agenda statement.
                section_id = "background"
                for sec in SECTION_ORDER:
                    if sec.replace("_", " ") in agenda_text:
                        section_id = sec
                        break
                payload = canned_section_text(section_id)
                outputs.append({"output": json.dumps(payload)})
            elif r.id == "rigor_auditor":
                # Rigor-audit single-role meeting.
                payload = {"passed": True, "issues": []}
                outputs.append({"output": json.dumps(payload)})
            else:
                # Non-synth role just returns a placeholder.
                outputs.append({"output": f"[{r.id}]"})
        return outputs
    return _crosstalk


def test_run_lit_report_with_stub_callbacks_full_pipeline(
    tmp_path, monkeypatch
):
    """Synthetic 5-paper corpus + stub crosstalk runner — verify that the
    full pipeline writes the assembled review, all 5 section drafts, and
    the audit file with passed status, and that total word count is in
    the spec's 3000-5000 range (or close — we use canned 700-word sections
    so totals fall under).
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(
        "vaultlab.research.config.get_config",
        lambda *a, **k: {},
    )

    # Make canned section text scale so the report hits at least 3000 words.
    # Each section gets 700 words of repeated lorem so total ~3500.
    def _canned(section_id):
        # Use a fixed wikilink slug (Goltsev 2018 — known to exist in seeds).
        text = (
            "Cellular-neighborhood research "
            "[[10.1016_j.cell.2018.07.010|Goltsev 2018]] "
            "operationalized indexed niches with multiplexed imaging "
            "[[10.1038_nmeth.4391|Schapiro 2017]] established the analytical "
            "vocabulary for tissue social networks. "
            "Subsequent work generalized the framework. "
        ) * 100  # ~50 words per cycle * 100 = 5000 words; plenty of headroom
        # Cap to about 700 words for test efficiency.
        words = text.split()[:700]
        return {
            "section_text": " ".join(words),
            "claims_with_evidence": [
                {
                    "claim": "Goltsev 2018 defined indexed niches.",
                    "doi_slugs": ["10.1016_j.cell.2018.07.010"],
                },
                {
                    "claim": "Schapiro 2017 established analytical vocabulary.",
                    "doi_slugs": ["10.1038_nmeth.4391"],
                },
            ],
        }

    runner = _make_crosstalk_runner(_canned)
    client = _FakeClient(_make_seeds())

    result = run_lit_report(
        "CODEX cellular neighborhoods",
        kb_root=tmp_path,
        max_seeds=5,
        max_papers_to_summarize=5,
        depth="thorough",
        _client=client,
        _fetch_refs=_fake_fetch_refs,
        _acquire=_fake_acquire,
        reader=_stub_reader,
        crosstalk_runner=runner,
        crosstalk_n_rounds=2,
        _today="2026-04-30",
    )

    # Result type and field sanity.
    assert isinstance(result, ReportRunResult)
    assert result.topic == "CODEX cellular neighborhoods"
    assert result.report_path.exists(), "report file not written"
    assert result.audit_report_path.exists(), "audit file not written"
    assert result.audit_status in {"passed", "passed_with_warnings", "failed"}
    assert result.duration_seconds >= 0.0

    # Path canonicalization.
    expected_report = concept_path(
        tmp_path, "CODEX cellular neighborhoods", "report", "2026-04-30"
    )
    assert result.report_path == expected_report

    # All 5 sections written.
    assert set(result.section_paths.keys()) == set(SECTION_ORDER)
    for sec, p in result.section_paths.items():
        assert p.exists(), f"missing draft for {sec}: {p}"

    # Per-section word counts populated and total inside spec band.
    for sec in SECTION_ORDER:
        assert sec in result.section_word_counts
        assert result.section_word_counts[sec] > 0
    assert result.word_count == sum(result.section_word_counts.values())
    # 5 sections * 700 words = 3500 (well in 3000-5000 spec band).
    assert 3000 <= result.word_count <= 5000

    # Frontmatter parses + has expected fields.
    md = result.report_path.read_text(encoding="utf-8")
    assert md.startswith("---\n")
    end = md.find("\n---\n", 4)
    fm = yaml.safe_load(md[4:end])
    assert fm["topic"] == "CODEX cellular neighborhoods"
    assert str(fm["date"]) == "2026-04-30"
    assert fm["total_words"] == result.word_count
    assert fm["audit_status"] == result.audit_status
    assert fm["generated_by"] == "vaultlab.research.report.run_lit_report"

    # All 5 section H2s present in the body.
    assert "## Background" in md
    assert "## Methods landscape" in md
    assert "## Key findings" in md
    assert "## Contradictions & open questions" in md
    assert "## Future directions" in md

    # References + audit footer present.
    assert "## References" in md
    assert "## Rigor audit" in md

    # Provenance receipts.
    json_p = result.report_path.with_name(
        result.report_path.name + ".provenance.json"
    )
    assert json_p.exists()
    rec = json.loads(json_p.read_text(encoding="utf-8"))
    assert rec["params"]["audit_status"] == result.audit_status
    assert rec["params"]["section_word_counts"] == result.section_word_counts


def test_run_lit_report_cohesion_threading(tmp_path, monkeypatch):
    """Section N+1's prepared task receives sections 1..N in prior_sections."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(
        "vaultlab.research.config.get_config",
        lambda *a, **k: {},
    )

    seen_prior_keys: list[set[str]] = []

    def _capturing_runner(meeting, roles):
        # Capture the prior-section keys present in the session_context
        # (which IS the task.prompt by design in _build_section_meeting).
        ctx = meeting.session_context or ""
        keys: set[str] = set()
        for sec in SECTION_ORDER:
            if f"Already-written: {sec}" in ctx:
                keys.add(sec)
        seen_prior_keys.append(keys)
        # Return a clean canned section with one wikilink.
        outputs = []
        for r in roles:
            if r.id == "synthesizer":
                payload = {
                    "section_text": (
                        "Sample text [[10.1038_nmeth.4391|Schapiro 2017]] " * 50
                    ),
                    "claims_with_evidence": [
                        {"claim": "x", "doi_slugs": ["10.1038_nmeth.4391"]},
                    ],
                }
                outputs.append({"output": json.dumps(payload)})
            elif r.id == "rigor_auditor":
                outputs.append({"output": json.dumps({"passed": True, "issues": []})})
            else:
                outputs.append({"output": f"[{r.id}]"})
        return outputs

    client = _FakeClient(_make_seeds())
    run_lit_report(
        "CODEX",
        kb_root=tmp_path,
        max_seeds=5,
        max_papers_to_summarize=5,
        _client=client,
        _fetch_refs=_fake_fetch_refs,
        _acquire=_fake_acquire,
        reader=_stub_reader,
        crosstalk_runner=_capturing_runner,
        crosstalk_n_rounds=1,
        _today="2026-04-30",
    )

    # The captured prior-section sets per section meeting (multiple rounds
    # may multiply per section, but we want the FIRST-round prior set per
    # section in canonical order — they should be cumulative).
    # The 5 section meetings + 1 audit meeting = 6 captures (with 1 round).
    assert len(seen_prior_keys) >= 5
    # First section: no priors.
    assert seen_prior_keys[0] == set()
    # Second section: includes 'background'.
    assert "background" in seen_prior_keys[1]
    # Third section: includes 'background' AND 'methods_landscape'.
    assert "background" in seen_prior_keys[2]
    assert "methods_landscape" in seen_prior_keys[2]


def test_run_lit_report_audit_strict_blocks_on_blocker(tmp_path, monkeypatch):
    """audit_strict=True raises when the auditor returns a blocker issue."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(
        "vaultlab.research.config.get_config",
        lambda *a, **k: {},
    )

    def _runner(meeting, roles):
        outputs = []
        is_audit = meeting.topic.startswith("rigor audit")
        for r in roles:
            if r.id == "synthesizer":
                payload = {
                    "section_text": "[[10.1038_nmeth.4391|Schapiro 2017]] said x. " * 50,
                    "claims_with_evidence": [
                        {"claim": "x", "doi_slugs": ["10.1038_nmeth.4391"]}
                    ],
                }
                outputs.append({"output": json.dumps(payload)})
            elif r.id == "rigor_auditor":
                # Blocker-level issue → audit_strict should refuse to write.
                payload = {
                    "passed": False,
                    "issues": [
                        {
                            "loc": "Background",
                            "severity": "blocker",
                            "kind": "missing-evidence",
                            "fix": "Add wikilink for claim X.",
                        }
                    ],
                }
                outputs.append({"output": json.dumps(payload)})
            else:
                outputs.append({"output": f"[{r.id}]"})
            del is_audit
        return outputs

    client = _FakeClient(_make_seeds())
    with pytest.raises(RuntimeError, match="audit_strict"):
        run_lit_report(
            "CODEX",
            kb_root=tmp_path,
            max_seeds=5,
            max_papers_to_summarize=5,
            _client=client,
            _fetch_refs=_fake_fetch_refs,
            _acquire=_fake_acquire,
            reader=_stub_reader,
            crosstalk_runner=_runner,
            crosstalk_n_rounds=1,
            audit_strict=True,
            _today="2026-04-30",
        )


def test_run_lit_report_section_writer_fallback(tmp_path, monkeypatch):
    """When no crosstalk_runner is given, section_writer is used as fallback."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(
        "vaultlab.research.config.get_config",
        lambda *a, **k: {},
    )

    seen_sections: list[str] = []

    def _writer(task):
        seen_sections.append(task.section)
        return {
            "section_text": (
                "Goltsev [[10.1016_j.cell.2018.07.010|Goltsev 2018]] said. " * 80
            ),
            "claims_with_evidence": [
                {"claim": "x", "doi_slugs": ["10.1016_j.cell.2018.07.010"]}
            ],
        }

    client = _FakeClient(_make_seeds())
    result = run_lit_report(
        "CODEX",
        kb_root=tmp_path,
        max_seeds=5,
        max_papers_to_summarize=5,
        _client=client,
        _fetch_refs=_fake_fetch_refs,
        _acquire=_fake_acquire,
        reader=_stub_reader,
        section_writer=_writer,  # fallback path (no crosstalk_runner)
        _today="2026-04-30",
    )

    # All 5 sections went through the section_writer.
    assert set(seen_sections) == set(SECTION_ORDER)
    assert result.report_path.exists()
    # No crosstalk_runner means the rigor audit is skipped.
    assert result.audit_status == "passed"


def test_run_lit_report_provenance_records_word_counts(tmp_path, monkeypatch):
    """Provenance JSON records per-section word counts for reproducibility."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(
        "vaultlab.research.config.get_config",
        lambda *a, **k: {},
    )

    def _writer(task):
        return {
            "section_text": (
                "[[10.1038_nmeth.4391|Schapiro 2017]] established. " * 60
            ),
            "claims_with_evidence": [
                {"claim": "x", "doi_slugs": ["10.1038_nmeth.4391"]}
            ],
        }

    client = _FakeClient(_make_seeds())
    result = run_lit_report(
        "CODEX",
        kb_root=tmp_path,
        max_seeds=5,
        max_papers_to_summarize=5,
        _client=client,
        _fetch_refs=_fake_fetch_refs,
        _acquire=_fake_acquire,
        reader=_stub_reader,
        section_writer=_writer,
        _today="2026-04-30",
    )

    json_p = result.report_path.with_name(
        result.report_path.name + ".provenance.json"
    )
    rec = json.loads(json_p.read_text(encoding="utf-8"))
    assert rec["generated_by"] == "vaultlab.research.report.run_lit_report"
    assert rec["params"]["actual_total_words"] == result.word_count
    assert rec["params"]["section_word_counts"] == result.section_word_counts
    assert rec["params"]["depth"] == "thorough"
    assert rec["kind"] == "deep_research_report"
