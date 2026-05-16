"""Tests for vaultlab.report.visual_designs_html — pattern #2 consumer.

Deterministic string-level + filesystem tests. Conventions match
:mod:`test_flowchart_html` and :mod:`test_incident_timeline_html`.
"""

from __future__ import annotations

import json
from pathlib import Path

from vaultlab.report.visual_designs_html import (
    DesignOption,
    VisualDesigns,
    build_visual_designs_html,
    write_visual_designs_html,
)


# ---------------------------------------------------------------------------
# Fixtures


def _minimal() -> VisualDesigns:
    return VisualDesigns(
        title="Pick a palette",
        context="Two-option draft.",
        options=[
            DesignOption(
                name="Pastel A",
                rationale="Soft pediatric palette",
                swatch_colors=["#a8d8ea", "#aa96da"],
            ),
            DesignOption(
                name="Pastel B",
                rationale="Higher contrast variant",
                swatch_colors=["#264653", "#e76f51"],
            ),
        ],
    )


def _full() -> VisualDesigns:
    return VisualDesigns(
        title="Figure 2 design directions",
        context="Pick a palette + layout for figure 2 before plotting.",
        options=[
            DesignOption(
                name="NMI Pastel",
                rationale="Matches the Nature Methods Impact palette.",
                swatch_colors=["#a8d8ea", "#aa96da", "#fcbad3", "#ffffd2"],
                archetype="discovery",
                inline_svg_preview=(
                    '<svg viewBox="0 0 100 50">'
                    '<rect width="50" height="50" fill="#a8d8ea"/>'
                    '<rect x="50" width="50" height="50" fill="#aa96da"/>'
                    "</svg>"
                ),
            ),
            DesignOption(
                name="Nature 2026",
                rationale="High contrast for print + colour-blind safe.",
                swatch_colors=["#264653", "#2a9d8f", "#e9c46a", "#e76f51"],
                archetype="methods",
            ),
            DesignOption(
                name="Dataset Browser",
                rationale="Neutral grays + one accent for table-heavy figures.",
                swatch_colors=["#333333", "#777777", "#dddddd", "#e63946"],
                archetype="dataset",
            ),
            DesignOption(
                name="Clinical Vivid",
                rationale="Vivid hues for clinical posters.",
                swatch_colors=["#1d3557", "#457b9d", "#a8dadc", "#e63946"],
                archetype="clinical",
            ),
        ],
    )


# ---------------------------------------------------------------------------
# build_visual_designs_html


def test_build_minimal_returns_well_formed_html():
    html = build_visual_designs_html(_minimal())
    assert isinstance(html, str)
    assert html.startswith("<!doctype html>")
    assert "</html>" in html
    assert "Pick a palette" in html
    assert "Pastel A" in html
    assert "Pastel B" in html


def test_build_full_renders_all_options():
    html = build_visual_designs_html(_full())
    assert "NMI Pastel" in html
    assert "Nature 2026" in html
    assert "Dataset Browser" in html
    assert "Clinical Vivid" in html
    # Rationale text appears
    assert "colour-blind safe" in html
    # Archetype labels surface
    assert "discovery" in html
    assert "methods" in html
    # Swatch colour values appear in inline SVG markup
    assert "#a8d8ea" in html
    assert "#264653" in html


def test_build_renders_inline_svg_when_supplied():
    html = build_visual_designs_html(_full())
    # The caller-supplied SVG preview is inlined verbatim (not escaped),
    # since the dataclass contract treats it as trusted HTML.
    assert '<svg viewBox="0 0 100 50">' in html


def test_build_renders_swatch_svg_even_without_preview():
    """Options that don't supply inline_svg_preview still get a swatch row."""
    designs = VisualDesigns(
        title="t",
        context="",
        options=[
            DesignOption(
                name="X",
                rationale="",
                swatch_colors=["#ff0000", "#00ff00", "#0000ff"],
            )
        ],
    )
    html = build_visual_designs_html(designs)
    assert "#ff0000" in html
    assert "#00ff00" in html
    assert "#0000ff" in html
    # An auto-built SVG block is present.
    assert "<svg" in html


def test_build_empty_options_still_renders():
    designs = VisualDesigns(title="empty", context="nothing", options=[])
    html = build_visual_designs_html(designs)
    assert html.startswith("<!doctype html>")
    assert "</html>" in html


def test_build_escapes_user_text():
    designs = VisualDesigns(
        title="<script>alert(1)</script>",
        context="Test & <b>escape</b>.",
        options=[
            DesignOption(
                name="<bad name>",
                rationale="<scripted rationale>",
                swatch_colors=["#abcdef"],
                archetype="<arch>",
            )
        ],
    )
    html = build_visual_designs_html(designs)
    assert "<script>alert(1)</script>" not in html
    assert "<scripted rationale>" not in html
    assert "&lt;script&gt;" in html or "&lt;script" in html


# ---------------------------------------------------------------------------
# write_visual_designs_html + provenance


def test_write_creates_output_file(tmp_path: Path):
    out = tmp_path / "designs.html"
    result = write_visual_designs_html(_minimal(), out)
    assert result == out
    assert out.exists()


def test_write_creates_provenance_sidecars(tmp_path: Path):
    out = tmp_path / "designs.html"
    write_visual_designs_html(_full(), out)
    prov_json = out.with_name(out.name + ".provenance.json")
    method_md = out.with_name(out.name + ".method.md")
    assert prov_json.exists()
    assert method_md.exists()
    payload = json.loads(prov_json.read_text(encoding="utf-8"))
    assert payload["generated_by"] == "vaultlab.report.visual_designs_html"
    assert payload["kind"] == "visual_designs_html"
    assert payload["params"]["option_count"] == 4
    assert payload["params"]["title"] == "Figure 2 design directions"


def test_write_accepts_string_path(tmp_path: Path):
    out = tmp_path / "designs.html"
    result = write_visual_designs_html(_minimal(), str(out))
    assert result == Path(str(out))
    assert out.exists()


def test_write_creates_parent_directories(tmp_path: Path):
    out = tmp_path / "nested" / "deeper" / "designs.html"
    write_visual_designs_html(_minimal(), out)
    assert out.exists()
    assert out.parent.exists()


# ---------------------------------------------------------------------------
# Dispatch routing


def test_dispatch_routes_visual_designs_dataclass(tmp_path: Path):
    from vaultlab.report.dispatch import write_artifact_html

    out = tmp_path / "designs.html"
    write_artifact_html(out, _full())
    html = out.read_text(encoding="utf-8")
    assert "Figure 2 design directions" in html
    assert "NMI Pastel" in html
