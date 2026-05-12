"""Tests for vaultlab.report.dispatch — universal HTML dispatcher."""

from __future__ import annotations

from pathlib import Path

import pytest

from vaultlab.report.dispatch import (
    UnknownArtifact,
    render_artifact_html,
    write_artifact_html,
)

# ---------------------------------------------------------------------------
# Auto-detection


def test_detects_reasoning_chain():
    data = {
        "rounds": [],
        "final_output": {},
        "purpose": "test",
        "crosstalk_status": "complete",
    }
    html = render_artifact_html(data)
    assert "<!doctype html>" in html
    assert "Reasoning chain" in html


def test_detects_citation_audit():
    data = {
        "total": 0,
        "by_status": {},
        "high_risk_unverified": 0,
        "audit_date": "",
        "source_files": [],
        "hallucination_flags": [],
        "action_items": [],
        "citations": [],
    }
    html = render_artifact_html(data)
    assert "Citation audit" in html


def test_detects_litarc():
    data = {
        "narrative": "Some narrative.",
        "papers": [],
        "topic": "x",
    }
    html = render_artifact_html(data)
    assert "Lit-arc" in html


def test_detects_dossier():
    from datetime import UTC, datetime

    data = {
        "project_slug": "test-project",
        "sections": [],
        "compiled_at": datetime.now(UTC),
    }
    html = render_artifact_html(data)
    assert "test-project" in html


def test_detects_response_letter():
    data = {
        "reviewer": 1,
        "comments": [],
        "opening": "",
        "closing": "",
    }
    html = render_artifact_html(data)
    assert "Response to Reviewer 1" in html


def test_detects_deck_audit_with_plan_audit_keys():
    data = {
        "plan": {"title": "x", "slides": []},
        "audit": {"passed": True, "issues": []},
    }
    html = render_artifact_html(data)
    assert "Deck audit" in html


def test_unknown_artifact_raises():
    with pytest.raises(UnknownArtifact, match="Could not infer"):
        render_artifact_html({"random": "data"})


def test_unknown_artifact_includes_keys_in_error():
    with pytest.raises(UnknownArtifact, match="random"):
        render_artifact_html({"random": "data", "also": "this"})


# ---------------------------------------------------------------------------
# Explicit kind override


def test_explicit_kind_overrides_detection():
    """Pass kind="reasoning" even if shape doesn't match — should still work."""
    data = {
        "rounds": [],
        "final_output": {},
    }
    html = render_artifact_html(data, kind="reasoning")
    assert "Reasoning chain" in html


def test_explicit_kind_works_for_litarc():
    data = {
        "topic": "x",
        "narrative": "y",
        "papers": [],
    }
    html = render_artifact_html(data, kind="litarc")
    assert "Lit-arc" in html


# ---------------------------------------------------------------------------
# Extra kwargs forwarded


def test_extra_kwargs_forwarded_to_litarc():
    data = {
        "narrative": "",
        "papers": [],
    }
    html = render_artifact_html(data, kind="litarc", topic="custom topic")
    assert "custom topic" in html


# ---------------------------------------------------------------------------
# write_artifact_html


def test_write_artifact_html(tmp_path: Path):
    data = {
        "rounds": [],
        "final_output": {},
        "purpose": "test",
        "crosstalk_status": "complete",
    }
    out = tmp_path / "art.html"
    written = write_artifact_html(out, data)
    assert written == out
    assert out.exists()
    assert "<!doctype html>" in out.read_text(encoding="utf-8")


def test_write_creates_parent_dirs(tmp_path: Path):
    data = {
        "narrative": "",
        "papers": [],
    }
    out = tmp_path / "nested" / "deep" / "art.html"
    write_artifact_html(out, data, kind="litarc", topic="x")
    assert out.exists()
