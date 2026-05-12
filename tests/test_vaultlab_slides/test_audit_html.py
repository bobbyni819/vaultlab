"""Tests for vaultlab.slides.audit_html — HTML audit consumer."""

from __future__ import annotations

from pathlib import Path

import pytest

from vaultlab.slides.audit_html import (
    build_audit_report_html,
    write_audit_report,
)


@pytest.fixture
def sample_plan() -> dict:
    return {
        "title": "Multi-lung short deck",
        "slides": [
            {
                "type": "title",
                "title": "Multi-lung review",
                "subtitle": "5-min talk",
                "bullets": [],
            },
            {
                "type": "figure",
                "title": "Spatial transcriptomics overview",
                "bullets": ["Method maps cells in tissue space"],
            },
            {
                "type": "bullets",
                "title": "Findings",
                "bullets": ["A", "B", "C", "D", "E", "F", "G"],
            },
        ],
    }


@pytest.fixture
def passing_audit() -> dict:
    return {"passed": True, "issues": []}


@pytest.fixture
def failing_audit() -> dict:
    return {
        "passed": False,
        "issues": [
            {
                "loc": "Slide 2",
                "severity": "blocker",
                "kind": "missing-citation",
                "fix": "Cite Pentimalli 2025 for the spatial-tx claim.",
            },
            {
                "loc": "Slide 3",
                "severity": "major",
                "kind": "overclaim",
                "fix": "Soften 'X causes Y' to 'X is associated with Y'.",
            },
            {
                "loc": "Slide 3",
                "severity": "minor",
                "kind": "style",
                "fix": "Bullet 7 exceeds 24 words; split into two.",
            },
            {
                "loc": "(global)",
                "severity": "major",
                "kind": "reference-list",
                "fix": "Reference [3] is uncited in body.",
            },
        ],
    }


# ---------------------------------------------------------------------------
# Passing-audit case


def test_renders_passing_audit_cleanly(sample_plan, passing_audit):
    html = build_audit_report_html(sample_plan, passing_audit)
    assert "<!doctype html>" in html
    assert "Multi-lung short deck" in html
    assert "passed rigor audit" in html
    assert "PASSED" in html
    # No issue badges should appear on slides
    assert "blocker" not in html.lower() or "0 blocker" in html.lower()


def test_passing_audit_shows_all_clean_chips(sample_plan, passing_audit):
    html = build_audit_report_html(sample_plan, passing_audit)
    # Three slide cards, each badge'd "clean"
    assert html.count(">clean<") == 3


# ---------------------------------------------------------------------------
# Failing-audit case


def test_renders_failing_audit_with_summary(sample_plan, failing_audit):
    html = build_audit_report_html(sample_plan, failing_audit)
    assert "ISSUES FOUND" in html
    # Total counts (1 blocker + 2 major + 1 minor)
    assert "1 blocker" in html
    assert "2 major" in html
    assert "1 minor" in html


def test_failing_audit_groups_by_slide(sample_plan, failing_audit):
    html = build_audit_report_html(sample_plan, failing_audit)
    # Slide 2 should show the blocker
    assert "missing-citation" in html.lower() or "MISSING-CITATION" in html
    assert "Pentimalli 2025" in html
    # Slide 3 should show overclaim + style
    assert "overclaim" in html.lower() or "OVERCLAIM" in html


def test_global_issues_section_appears(sample_plan, failing_audit):
    html = build_audit_report_html(sample_plan, failing_audit)
    assert "Global / unattributed issues" in html
    assert "Reference [3] is uncited" in html


def test_filter_bar_present(sample_plan, failing_audit):
    html = build_audit_report_html(sample_plan, failing_audit)
    assert "vl-filter" in html
    for key in ("blocker", "major", "minor", "ok", "all"):
        assert f'data-filter="{key}"' in html


def test_per_slide_filter_keys(sample_plan, failing_audit):
    html = build_audit_report_html(sample_plan, failing_audit)
    # Slide 1 is clean (filter_key ok); slide 2 is blocker; slide 3 is major
    assert 'data-filter-key="ok"' in html
    assert 'data-filter-key="blocker"' in html
    assert 'data-filter-key="major"' in html


# ---------------------------------------------------------------------------
# Edge cases


def test_empty_plan():
    html = build_audit_report_html({"slides": []}, {"passed": True, "issues": []})
    assert "<!doctype html>" in html


def test_pptx_path_in_meta(sample_plan, passing_audit):
    html = build_audit_report_html(sample_plan, passing_audit, pptx_path="output/multi-lung.pptx")
    assert "output/multi-lung.pptx" in html


def test_write_audit_report_creates_file(tmp_path: Path, sample_plan, failing_audit):
    out = tmp_path / "sub" / "audit.html"
    written = write_audit_report(out, sample_plan, failing_audit)
    assert written == out
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "ISSUES FOUND" in text


def test_xss_safe_against_evil_slide_titles():
    plan = {
        "title": "x",
        "slides": [{"type": "title", "title": "<script>alert(1)</script>", "bullets": []}],
    }
    audit = {"passed": True, "issues": []}
    html = build_audit_report_html(plan, audit)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_xss_safe_against_evil_issue_fix(sample_plan):
    audit = {
        "passed": False,
        "issues": [
            {
                "loc": "Slide 1",
                "severity": "major",
                "kind": "test",
                "fix": "<img src=x onerror=alert(1)>",
            }
        ],
    }
    html = build_audit_report_html(sample_plan, audit)
    assert "<img src=x" not in html
    assert "&lt;img" in html


def test_severity_mapping_for_unknown_severity(sample_plan):
    audit = {
        "passed": False,
        "issues": [
            {"loc": "Slide 1", "severity": "warning", "kind": "x", "fix": "y"},
        ],
    }
    html = build_audit_report_html(sample_plan, audit)
    # Should not crash and should still render
    assert "<!doctype html>" in html
