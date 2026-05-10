"""Integration tests for verifier_callback wiring in run_lit_arc."""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Reuse the existing fakes from test_picker
from tests.test_vaultlab_research.test_picker import (
    _fake_acquire,
    _fake_fetch_refs,
    _FakeClient,
    _make_seeds,
)
from vaultlab.research.claim_verification import ClaimVerificationTask


def _stub_summary_llm(*, pdf_bytes, prompt, api_key, model, **_):
    """Stub summary LLM that returns the same shape as the real one."""
    return (
        {
            "tldr": "Stub TL;DR for tests. Two sentences. Three.",
            "why_it_matters": ["x"],
            "methods_summary": "m",
            "key_findings": ["claim a [p1]", "claim b [p2]"],
            "extracted_references": [],
        },
        1,
        1,
    )


def _stub_narrator(arc_task) -> dict[str, str]:
    """Stub narrator returns three short paragraphs with wikilink citations."""
    # Use real DOIs from _make_seeds() — they're slugified into wikilinks.
    return {
        "history": ("[[10.1000_seed-2018|Seed 2018]] introduced the foundational method."),
        "development": ("[[10.1000_seed-2020|Seed 2020]] refined the protocol."),
        "sota": ("[[10.1000_seed-2024|Seed 2024]] pushes the frontier."),
    }


def test_verifier_callback_runs_when_supplied(tmp_path: Path, monkeypatch):
    """When verifier_callback is given, it gets called once per non-empty section."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("vaultlab.research.config.get_config", lambda *a, **k: {})
    from vaultlab.research.lineage import run_lit_arc

    seen_tasks: list[ClaimVerificationTask] = []

    def verifier(task: ClaimVerificationTask) -> dict[str, Any]:
        seen_tasks.append(task)
        # Return one supported verdict per claim
        return {
            "verifications": [
                {
                    "position": claim.position,
                    "verdict": "supported",
                    "evidence": "matches the summary",
                    "evidence_doi": (claim.cited_dois[0] if claim.cited_dois else ""),
                }
                for claim in task.claims
            ]
        }

    seeds = _make_seeds()
    result = run_lit_arc(
        "topic-X",
        kb_root=tmp_path,
        max_seeds=5,
        max_papers_to_summarize=3,
        narrator=_stub_narrator,
        _client=_FakeClient(seeds),
        _fetch_refs=_fake_fetch_refs,
        _acquire=_fake_acquire,
        _llm_summary=_stub_summary_llm,
        _today="2026-05-01",
        verifier_callback=verifier,
    )

    # Verifier was called once per non-empty section (3 sections)
    assert len(seen_tasks) == 3
    section_ids = {t.section_id for t in seen_tasks}
    assert section_ids == {"history", "development", "sota"}
    # Run still completed; arc was written
    assert result.arc_path.exists()


def test_no_verifier_callback_means_no_verification(tmp_path: Path, monkeypatch):
    """Without a verifier_callback, no verification happens (back-compat).

    The arc is still written; nothing in the output mentions verification.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("vaultlab.research.config.get_config", lambda *a, **k: {})
    from vaultlab.research.lineage import run_lit_arc

    seeds = _make_seeds()
    result = run_lit_arc(
        "topic-Y",
        kb_root=tmp_path,
        max_seeds=5,
        max_papers_to_summarize=3,
        narrator=_stub_narrator,
        _client=_FakeClient(seeds),
        _fetch_refs=_fake_fetch_refs,
        _acquire=_fake_acquire,
        _llm_summary=_stub_summary_llm,
        _today="2026-05-01",
        # verifier_callback intentionally not passed
    )
    assert result.arc_path.exists()


def test_verifier_callback_handles_unverifiable_claims(tmp_path: Path, monkeypatch):
    """When the verifier returns unverifiable for some claims, the run
    completes without crashing (Schurch-2020-style overclaim case)."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("vaultlab.research.config.get_config", lambda *a, **k: {})
    from vaultlab.research.lineage import run_lit_arc

    def verifier(task: ClaimVerificationTask) -> dict[str, Any]:
        # Mark every claim as unverifiable (simulating no Tier-A summaries)
        return {
            "verifications": [
                {
                    "position": claim.position,
                    "verdict": "unverifiable",
                    "evidence": "",
                    "evidence_doi": "",
                }
                for claim in task.claims
            ]
        }

    seeds = _make_seeds()
    result = run_lit_arc(
        "topic-Z",
        kb_root=tmp_path,
        max_seeds=5,
        max_papers_to_summarize=3,
        narrator=_stub_narrator,
        _client=_FakeClient(seeds),
        _fetch_refs=_fake_fetch_refs,
        _acquire=_fake_acquire,
        _llm_summary=_stub_summary_llm,
        _today="2026-05-01",
        verifier_callback=verifier,
    )
    # Run completed — overclaim handling is graceful
    assert result.arc_path.exists()


def test_verifier_callback_exception_does_not_crash_run(tmp_path: Path, monkeypatch):
    """A crashing verifier_callback is caught; the rest of the run completes."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("vaultlab.research.config.get_config", lambda *a, **k: {})
    from vaultlab.research.lineage import run_lit_arc

    def broken_verifier(task):
        raise RuntimeError("verifier oops")

    seeds = _make_seeds()
    # Note: the inner verify_paragraph_claims helper catches the
    # exception (logs warning, returns unverifiable). Our wrapper in
    # run_lit_arc additionally guards with try/except. The run should
    # complete either way.
    result = run_lit_arc(
        "topic-W",
        kb_root=tmp_path,
        max_seeds=5,
        max_papers_to_summarize=3,
        narrator=_stub_narrator,
        _client=_FakeClient(seeds),
        _fetch_refs=_fake_fetch_refs,
        _acquire=_fake_acquire,
        _llm_summary=_stub_summary_llm,
        _today="2026-05-01",
        verifier_callback=broken_verifier,
    )
    assert result.arc_path.exists()
