"""Tests for vaultlab.report.approaches_compare_html — Pattern #1.

Deterministic string-level + filesystem tests; no browser rendering.
"""

from __future__ import annotations

import json
from pathlib import Path

from vaultlab.report.approaches_compare_html import (
    Approach,
    ApproachesCompare,
    build_approaches_compare_html,
    write_approaches_compare_html,
)


# ---------------------------------------------------------------------------
# Fixtures


def _two_approaches() -> ApproachesCompare:
    return ApproachesCompare(
        title="How to parallelize",
        context="The plan has 12 independent slices.",
        approaches=[
            Approach(
                name="Approach A: Subagent dispatch",
                summary="Spawn one subagent per slice.",
                pros=["Fast wall-clock", "Cheap to retry"],
                cons=["Token cost grows linearly"],
                estimated_effort="4 hours",
                recommended=True,
            ),
            Approach(
                name="Approach B: Sequential",
                summary="Do them one at a time in a long thread.",
                pros=["Simple to reason about"],
                cons=["Slow", "Context window pressure"],
                estimated_effort="1 day",
            ),
        ],
        decision_rationale="A wins on wall-clock; cost is acceptable.",
    )


def _three_approaches() -> ApproachesCompare:
    return ApproachesCompare(
        title="SPEC-F: How to weight dispatch",
        approaches=[
            Approach(name="A", summary="Static config", pros=["simple"], cons=["rigid"]),
            Approach(
                name="B",
                summary="Per-task learned weights",
                pros=["adaptive"],
                cons=["needs data"],
                recommended=True,
            ),
            Approach(name="C", summary="Round-robin", pros=["zero config"], cons=["dumb"]),
        ],
    )


# ---------------------------------------------------------------------------
# build_approaches_compare_html


def test_build_two_uses_compare_panel():
    html = build_approaches_compare_html(_two_approaches())
    assert html.startswith("<!doctype html>")
    # compare_panel emits the vl-compare class
    assert "vl-compare" in html
    # Pro / con bullets and effort appear
    assert "Fast wall-clock" in html
    assert "Token cost grows" in html
    assert "4 hours" in html
    # Recommendation label is appended for 2-up rendering
    assert "(recommended)" in html


def test_build_three_uses_card_grid_with_badge():
    html = build_approaches_compare_html(_three_approaches())
    # card_grid emits vl-cards
    assert "vl-cards" in html
    # RECOMMENDED chip on B
    assert "RECOMMENDED" in html
    # All three names appear
    for name in ("A", "B", "C"):
        # Card title surrounds the name verbatim
        assert f">{name}<" in html


def test_build_renders_context_and_rationale():
    html = build_approaches_compare_html(_two_approaches())
    assert "The plan has 12" in html
    assert "Decision rationale" in html
    assert "A wins on wall-clock" in html


def test_build_zero_approaches_handles_gracefully():
    comp = ApproachesCompare(title="Empty", approaches=[])
    html = build_approaches_compare_html(comp)
    assert html.startswith("<!doctype html>")
    assert "No approaches" in html


def test_build_escapes_user_text():
    comp = ApproachesCompare(
        title="<script>alert(1)</script>",
        approaches=[
            Approach(
                name="<bad>",
                summary="<x>",
                pros=["<p1>"],
                cons=["<c1>"],
            ),
        ],
    )
    html = build_approaches_compare_html(comp)
    # Raw injected script must not appear unescaped in the body
    body = html[html.index("<body>"):]
    assert "<script>alert(1)</script>" not in body
    assert "&lt;" in body


# ---------------------------------------------------------------------------
# write_approaches_compare_html + provenance


def test_write_creates_output_file(tmp_path: Path):
    out = tmp_path / "compare.html"
    result = write_approaches_compare_html(_two_approaches(), out)
    assert result == out
    assert out.exists()
    assert out.read_text(encoding="utf-8").startswith("<!doctype html>")


def test_write_creates_provenance_sidecars(tmp_path: Path):
    out = tmp_path / "compare.html"
    write_approaches_compare_html(_two_approaches(), out)
    prov_json = out.with_name(out.name + ".provenance.json")
    method_md = out.with_name(out.name + ".method.md")
    assert prov_json.exists()
    assert method_md.exists()
    payload = json.loads(prov_json.read_text(encoding="utf-8"))
    assert payload["generated_by"] == "vaultlab.report.approaches_compare_html"
    assert payload["kind"] == "approaches_compare"
    assert payload["params"]["approach_count"] == 2
    assert payload["params"]["recommended"].startswith("Approach A")
    assert payload["params"]["has_rationale"] is True
