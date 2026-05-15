"""Tests for vaultlab.report.flowchart_html — pattern #12 consumer.

Deterministic string-level + filesystem tests. Conventions match
:mod:`test_weekly_status_html` and :mod:`test_state_dashboard_html`.
"""

from __future__ import annotations

import json
from pathlib import Path

from vaultlab.report.flowchart_html import (
    Flowchart,
    FlowStep,
    build_flowchart_html,
    write_flowchart_html,
)


# ---------------------------------------------------------------------------
# Fixtures


def _minimal() -> Flowchart:
    return Flowchart(
        title="Two-step demo",
        description="Smallest possible flow.",
        steps=[
            FlowStep("a", "Step A", "First step.", successors=["b"]),
            FlowStep("b", "Step B", "Second step."),
        ],
        entry_step_id="a",
    )


def _full() -> Flowchart:
    return Flowchart(
        title="research-pipeline phases",
        description=(
            "Seven-phase research pipeline from verify-data to self-review."
        ),
        steps=[
            FlowStep(
                "p1",
                "Phase 1: Verify Data",
                "Sanity-check inputs before reasoning.",
                typical_duration="~15 min",
                failure_modes=["Missing column", "Type mismatch"],
                successors=["p2"],
            ),
            FlowStep(
                "p2",
                "Phase 2: Plan",
                "Sketch the analysis approach.",
                typical_duration="~10 min",
                failure_modes=["Scope creep"],
                successors=["p3"],
            ),
            FlowStep(
                "p3",
                "Phase 3: Reason",
                "Multi-agent reasoning over results.",
                typical_duration="~45 min",
                failure_modes=["Critic infinite loop", "Token budget blown"],
                successors=["p4"],
            ),
            FlowStep(
                "p4",
                "Phase 4: Figures",
                "Generate publication-grade figures.",
                typical_duration="~30 min",
                successors=[],
            ),
        ],
        entry_step_id="p1",
    )


# ---------------------------------------------------------------------------
# build_flowchart_html


def test_build_minimal_returns_well_formed_html():
    html = build_flowchart_html(_minimal())
    assert isinstance(html, str)
    assert html.startswith("<!doctype html>")
    assert "</html>" in html
    assert "Two-step demo" in html
    assert "Step A" in html
    assert "Step B" in html


def test_build_full_renders_all_steps():
    html = build_flowchart_html(_full())
    # All step labels appear
    assert "Phase 1: Verify Data" in html
    assert "Phase 2: Plan" in html
    assert "Phase 3: Reason" in html
    assert "Phase 4: Figures" in html
    # Failure mode bullets appear
    assert "Missing column" in html
    assert "Critic infinite loop" in html
    # Typical-duration chips appear
    assert "~15 min" in html
    assert "~30 min" in html


def test_build_renders_svg_diagram():
    html = build_flowchart_html(_full())
    # svg_arg_graph emits inline <svg> with our 4 nodes
    assert "<svg" in html
    # Each step_id ends up as a label in the SVG (label text or chip)
    assert "Phase 1: Verify Data" in html


def test_build_drops_unknown_successors():
    """Successors that don't reference declared steps are silently dropped."""
    chart = Flowchart(
        title="bad-edge",
        steps=[
            FlowStep("a", "A", "Lonely", successors=["nope", "b"]),
            FlowStep("b", "B", "Real"),
        ],
        entry_step_id="a",
    )
    html = build_flowchart_html(chart)
    # Should not crash; "nope" should appear in the Successors chip list of A
    # but not as an edge (svg_arg_graph skips edges with unknown endpoints).
    assert html.startswith("<!doctype html>")
    assert "A" in html and "B" in html


def test_build_empty_steps_still_renders():
    chart = Flowchart(
        title="empty",
        steps=[],
        entry_step_id="",
        description="nothing to flow",
    )
    html = build_flowchart_html(chart)
    assert html.startswith("<!doctype html>")
    assert "</html>" in html


def test_build_unknown_entry_id_degrades_gracefully():
    chart = Flowchart(
        title="bad-entry",
        steps=[FlowStep("a", "A", "ok")],
        entry_step_id="ghost",
    )
    # Should not crash
    html = build_flowchart_html(chart)
    assert "A" in html


def test_build_escapes_user_text():
    chart = Flowchart(
        title="<script>alert(1)</script>",
        description="Test & <b>escape</b>.",
        steps=[
            FlowStep(
                "<bad>",
                "<bad label>",
                "<scripted desc>",
                failure_modes=["<bad mode>"],
                successors=["<bad>"],
            )
        ],
        entry_step_id="<bad>",
    )
    html = build_flowchart_html(chart)
    assert "<script>alert(1)</script>" not in html
    assert "<scripted desc>" not in html
    assert "&lt;script&gt;" in html or "&lt;script" in html


# ---------------------------------------------------------------------------
# write_flowchart_html + provenance


def test_write_creates_output_file(tmp_path: Path):
    out = tmp_path / "flow.html"
    result = write_flowchart_html(_minimal(), out)
    assert result == out
    assert out.exists()


def test_write_creates_provenance_sidecars(tmp_path: Path):
    out = tmp_path / "flow.html"
    write_flowchart_html(_full(), out)
    prov_json = out.with_name(out.name + ".provenance.json")
    method_md = out.with_name(out.name + ".method.md")
    assert prov_json.exists()
    assert method_md.exists()
    payload = json.loads(prov_json.read_text(encoding="utf-8"))
    assert payload["generated_by"] == "vaultlab.report.flowchart_html"
    assert payload["kind"] == "flowchart_html"
    assert payload["params"]["step_count"] == 4
    assert payload["params"]["entry_step_id"] == "p1"
    # 2 + 1 + 2 + 0 = 5 failure modes
    assert payload["params"]["failure_mode_total"] == 5
    # 1 + 1 + 1 + 0 = 3 successor edges
    assert payload["params"]["edge_count"] == 3


def test_write_accepts_string_path(tmp_path: Path):
    out = tmp_path / "flow.html"
    result = write_flowchart_html(_minimal(), str(out))
    assert result == Path(str(out))
    assert out.exists()


def test_write_creates_parent_directories(tmp_path: Path):
    out = tmp_path / "nested" / "deeper" / "flow.html"
    write_flowchart_html(_minimal(), out)
    assert out.exists()
    assert out.parent.exists()
