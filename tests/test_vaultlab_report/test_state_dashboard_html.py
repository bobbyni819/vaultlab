"""Tests for vaultlab.report.state_dashboard_html — patterns #16 + #6 + #15.

Deterministic string-level + filesystem tests; no browser rendering.
Conventions match :mod:`test_weekly_status_html` and
:mod:`test_html`.
"""

from __future__ import annotations

import json
from pathlib import Path

from vaultlab.report.state_dashboard_html import (
    StateDashboard,
    build_state_dashboard_html,
    write_state_dashboard_html,
)


# ---------------------------------------------------------------------------
# Fixtures


def _minimal() -> StateDashboard:
    return StateDashboard(
        project="vaultlab",
        date="2026-05-15",
        status_summary="A quiet day; baseline holds.",
    )


def _full() -> StateDashboard:
    return StateDashboard(
        project="vaultlab",
        date="2026-05-15",
        status_summary=(
            "Patterns #1, #6, #15, #19 shipped; v0.0.5 unblocked."
        ),
        metrics={
            "tests": "1734 passing",
            "modules": "11",
            "patterns implemented": "11/20",
        },
        shipped=[
            ("State dashboard consumer", "Composes #16 + #6 + #15."),
            ("Feature flag editor", "Two-way HTML for dispatch.json."),
        ],
        in_flight=[
            ("SPEC-F dispatch wiring", "Routing weights per task class."),
        ],
        blockers=[
            ("Lit-arc Tier-B cap", "CrossRef rate-limits during burst."),
        ],
        module_map=[
            ("vaultlab.report", "HTML output", ["vaultlab.slides", "vaultlab.kb"]),
            ("vaultlab.slides", "Slide decks", []),
            ("vaultlab.kb", "Knowledge base", []),
        ],
        concept_explainer={
            "title": "Lit-arc retrieval cascade",
            "summary": "Frontmatter → indexes → wikilinks → cumulative corpus.",
            "nodes": [
                {"id": "fm", "x": 100, "y": 100, "label": "frontmatter"},
                {"id": "idx", "x": 250, "y": 100, "label": "indexes"},
                {"id": "wl", "x": 400, "y": 100, "label": "wikilinks"},
            ],
            "edges": [("fm", "idx"), ("idx", "wl")],
            "hot_path": ["fm", "idx"],
        },
    )


# ---------------------------------------------------------------------------
# build_state_dashboard_html


def test_build_minimal_returns_non_empty_html():
    html = build_state_dashboard_html(_minimal())
    assert isinstance(html, str)
    assert html.startswith("<!doctype html>")
    assert "</html>" in html
    assert "vaultlab" in html
    assert "2026-05-15" in html
    assert "A quiet day" in html


def test_build_full_contains_all_sections():
    html = build_state_dashboard_html(_full())
    # Section titles
    assert "Metrics" in html
    assert "Shipped" in html
    assert "In flight" in html
    assert "Blockers" in html
    assert "Module map" in html
    # Item / metric contents
    assert "State dashboard consumer" in html
    assert "1734 passing" in html
    assert "vaultlab.report" in html
    assert "vaultlab.slides" in html


def test_build_full_renders_module_map_as_svg():
    html = build_state_dashboard_html(_full())
    # svg_arg_graph emits an inline <svg> tag
    assert "<svg" in html
    # The legend cards expose each module's downstream chips
    # — chip text shows the downstream module name.
    assert "vaultlab.slides" in html  # downstream chip from vaultlab.report


def test_build_concept_explainer_renders_when_present():
    html = build_state_dashboard_html(_full())
    assert "Lit-arc retrieval cascade" in html
    # The summary text appears via tldr_box "In one line" label
    assert "Frontmatter" in html
    # Hot path nodes get a "hot" class on the SVG graph
    assert "hot" in html


def test_build_omits_concept_explainer_when_none():
    state = _minimal()
    html = build_state_dashboard_html(state)
    # No explainer was supplied — its title must not appear.
    assert "Concept explainer" not in html


def test_build_escapes_user_text():
    state = StateDashboard(
        project="<script>alert(1)</script>",
        date="2026-05-15",
        status_summary="Test & <b>verify</b>.",
        shipped=[("<bad>", "<also bad>")],
        module_map=[("<evil>", "<x>", [])],
    )
    html = build_state_dashboard_html(state)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script" in html


def test_build_no_modules_omits_module_section():
    state = StateDashboard(
        project="vaultlab",
        date="2026-05-15",
        status_summary="quiet.",
    )
    html = build_state_dashboard_html(state)
    assert "Module map" not in html
    assert html.startswith("<!doctype html>")


# ---------------------------------------------------------------------------
# write_state_dashboard_html + provenance


def test_write_creates_output_file(tmp_path: Path):
    out = tmp_path / "state.html"
    result = write_state_dashboard_html(_minimal(), out)
    assert result == out
    assert out.exists()
    assert out.read_text(encoding="utf-8").startswith("<!doctype html>")


def test_write_creates_provenance_sidecars(tmp_path: Path):
    out = tmp_path / "state.html"
    write_state_dashboard_html(_full(), out)
    prov_json = out.with_name(out.name + ".provenance.json")
    method_md = out.with_name(out.name + ".method.md")
    assert prov_json.exists(), f"missing provenance sidecar at {prov_json}"
    assert method_md.exists(), f"missing method.md sidecar at {method_md}"
    payload = json.loads(prov_json.read_text(encoding="utf-8"))
    assert payload["generated_by"] == "vaultlab.report.state_dashboard_html"
    assert payload["kind"] == "state_dashboard_html"
    assert payload["params"]["project"] == "vaultlab"
    assert payload["params"]["module_count"] == 3
    assert payload["params"]["has_concept_explainer"] is True


def test_write_accepts_string_path(tmp_path: Path):
    out = tmp_path / "state.html"
    result = write_state_dashboard_html(_minimal(), str(out))
    assert result == Path(str(out))
    assert out.exists()


def test_write_creates_parent_directories(tmp_path: Path):
    out = tmp_path / "nested" / "subdir" / "state.html"
    write_state_dashboard_html(_minimal(), out)
    assert out.exists()
    assert out.parent.exists()
