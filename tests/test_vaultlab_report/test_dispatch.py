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


# ---------------------------------------------------------------------------
# v0.0.5 consumer wiring (deferred-followups bundle)
#
# WeeklyStatusReport / StateDashboard / FeatureFlagConfig / ApproachesCompare
# must auto-route through the universal dispatcher without callers having to
# import each builder by name.


def test_detects_weekly_status_dataclass(tmp_path: Path):
    from vaultlab.report.weekly_status_html import WeeklyStatusReport

    report = WeeklyStatusReport(
        week_label="Week of 2026-05-15",
        project="vaultlab",
        tldr="Shipped dispatch wiring + color-contrast + inset-axes.",
        shipped=[("dispatch", "wired 4 new kinds")],
    )
    out = tmp_path / "weekly.html"
    written = write_artifact_html(out, report)
    assert written == out
    html = out.read_text(encoding="utf-8")
    # Weekly-status renderer surfaces the project + week_label in the header.
    assert "vaultlab" in html
    assert "Week of 2026-05-15" in html
    # And the "shipped" severity chip.
    assert "shipped" in html.lower()


def test_detects_weekly_status_from_dict():
    data = {
        "week_label": "Week of 2026-05-15",
        "project": "vaultlab",
        "tldr": "Bundle of small followups.",
    }
    html = render_artifact_html(data)
    assert "Week of 2026-05-15" in html
    assert "vaultlab" in html


def test_detects_state_dashboard_dataclass(tmp_path: Path):
    from vaultlab.report.state_dashboard_html import StateDashboard

    state = StateDashboard(
        project="vaultlab",
        date="2026-05-15",
        status_summary="Repo green; bundle 2 in flight.",
        module_map=[("vaultlab.report", "HTML consumers", ["vaultlab.provenance"])],
    )
    out = tmp_path / "state.html"
    write_artifact_html(out, state)
    html = out.read_text(encoding="utf-8")
    # The state-dashboard renderer surfaces the project + date.
    assert "vaultlab" in html
    assert "2026-05-15" in html


def test_detects_feature_flag_editor_dataclass(tmp_path: Path):
    from vaultlab.report.feature_flag_editor import FeatureFlagConfig, FlagGroup

    cfg = FeatureFlagConfig(
        title="Vaultlab Config",
        intro="Toggle the v0.0.5 features.",
        groups=[
            FlagGroup(
                title="HTML Consumers",
                flags=[("weekly_status", True, "weekly status reports")],
            ),
        ],
    )
    out = tmp_path / "ff.html"
    write_artifact_html(out, cfg)
    html = out.read_text(encoding="utf-8")
    assert "Vaultlab Config" in html
    assert "weekly_status" in html


def test_detects_approaches_compare_dataclass(tmp_path: Path):
    from vaultlab.report.approaches_compare_html import Approach, ApproachesCompare

    comp = ApproachesCompare(
        title="How to ship the bundle",
        approaches=[
            Approach(name="One commit", summary="single coherent diff", recommended=True),
            Approach(name="Three commits", summary="split per item"),
        ],
        decision_rationale="One commit keeps the diff coherent.",
    )
    out = tmp_path / "compare.html"
    write_artifact_html(out, comp)
    html = out.read_text(encoding="utf-8")
    assert "How to ship the bundle" in html
    assert "One commit" in html


def test_feature_flag_not_confused_with_deck_plan():
    """A deck plan has 'slides' AND 'title'; FeatureFlagConfig has 'groups'
    AND 'title' but no 'slides'. Detection must keep them separate."""
    from vaultlab.report.dispatch import _detect_kind

    deck_plan = {"title": "Deck", "slides": [{"type": "title"}], "audit": {}, "plan": {}}
    assert _detect_kind(deck_plan) == "deck-audit"

    ff = {"title": "Config", "groups": [], "intro": ""}
    assert _detect_kind(ff) == "feature-flag-editor"
