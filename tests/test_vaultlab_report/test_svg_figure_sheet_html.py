"""Tests for vaultlab.report.svg_figure_sheet_html — pattern #11 consumer."""

from __future__ import annotations

import json
from pathlib import Path

from vaultlab.report.svg_figure_sheet_html import (
    FigureSheet,
    Schematic,
    build_svg_figure_sheet_html,
    write_svg_figure_sheet_html,
)


# ---------------------------------------------------------------------------
# Fixtures


_DEMO_SVG = (
    '<svg viewBox="0 0 100 50" xmlns="http://www.w3.org/2000/svg">'
    '<rect x="10" y="10" width="30" height="30" fill="#a8d8ea"/>'
    '<rect x="60" y="10" width="30" height="30" fill="#aa96da"/>'
    "</svg>"
)


def _minimal() -> FigureSheet:
    return FigureSheet(
        title="Tiny sheet",
        intro="One schematic for testing.",
        schematics=[
            Schematic(
                label="Demo schematic",
                description="Two boxes side by side.",
                svg_source=_DEMO_SVG,
            )
        ],
    )


def _full() -> FigureSheet:
    return FigureSheet(
        title="vaultlab architecture schematics",
        intro="Copyable inline-SVG diagrams of the vaultlab subsystems.",
        schematics=[
            Schematic(
                label="Crosstalk pipeline",
                description="Frontmatter → indexes → wikilinks → corpus.",
                svg_source=_DEMO_SVG,
                related_concepts=["lit-arc", "abstract recall", "corpus"],
            ),
            Schematic(
                label="KB ingest",
                description="Raw PDF → metadata → frontmatter → wiki.",
                svg_source=_DEMO_SVG,
                related_concepts=["kb", "ingest", "metadata"],
            ),
            Schematic(
                label="Report dispatch",
                description="Auto-detect artifact shape → renderer.",
                svg_source=_DEMO_SVG,
            ),
        ],
    )


# ---------------------------------------------------------------------------
# build_svg_figure_sheet_html


def test_build_minimal_returns_well_formed_html():
    html = build_svg_figure_sheet_html(_minimal())
    assert isinstance(html, str)
    assert html.startswith("<!doctype html>")
    assert "</html>" in html
    assert "Tiny sheet" in html
    assert "Demo schematic" in html


def test_build_full_renders_all_schematics():
    html = build_svg_figure_sheet_html(_full())
    assert "Crosstalk pipeline" in html
    assert "KB ingest" in html
    assert "Report dispatch" in html


def test_build_inlines_svg_source_verbatim():
    """SVG markup is trusted and inlined verbatim (the whole point of #11)."""
    html = build_svg_figure_sheet_html(_full())
    assert '<svg viewBox="0 0 100 50"' in html
    assert "#a8d8ea" in html


def test_build_renders_related_concepts():
    html = build_svg_figure_sheet_html(_full())
    assert "lit-arc" in html
    assert "abstract recall" in html
    assert "metadata" in html


def test_build_renders_copy_button():
    """Each schematic has a 'copy SVG' affordance."""
    html = build_svg_figure_sheet_html(_full())
    # Use existing card-copy data-copy hook from severity_card actions.
    assert "data-copy" in html or "copy" in html.lower()


def test_build_empty_schematics_still_renders():
    sheet = FigureSheet(title="empty", intro="nothing", schematics=[])
    html = build_svg_figure_sheet_html(sheet)
    assert html.startswith("<!doctype html>")
    assert "</html>" in html


def test_build_escapes_user_text_but_inlines_svg():
    sheet = FigureSheet(
        title="<script>alert(1)</script>",
        intro="Test & <b>escape</b>.",
        schematics=[
            Schematic(
                label="<bad label>",
                description="<scripted desc>",
                svg_source='<svg><text>safe</text></svg>',
                related_concepts=["<bad concept>"],
            )
        ],
    )
    html = build_svg_figure_sheet_html(sheet)
    # Title + description escape user text.
    assert "<script>alert(1)</script>" not in html
    assert "<scripted desc>" not in html
    assert "&lt;script&gt;" in html or "&lt;script" in html
    # But svg_source inlines verbatim.
    assert "<svg><text>safe</text></svg>" in html


# ---------------------------------------------------------------------------
# write_svg_figure_sheet_html + provenance


def test_write_creates_output_file(tmp_path: Path):
    out = tmp_path / "sheet.html"
    result = write_svg_figure_sheet_html(_minimal(), out)
    assert result == out
    assert out.exists()


def test_write_creates_provenance_sidecars(tmp_path: Path):
    out = tmp_path / "sheet.html"
    write_svg_figure_sheet_html(_full(), out)
    prov_json = out.with_name(out.name + ".provenance.json")
    method_md = out.with_name(out.name + ".method.md")
    assert prov_json.exists()
    assert method_md.exists()
    payload = json.loads(prov_json.read_text(encoding="utf-8"))
    assert payload["generated_by"] == "vaultlab.report.svg_figure_sheet_html"
    assert payload["kind"] == "svg_figure_sheet_html"
    assert payload["params"]["schematic_count"] == 3
    assert payload["params"]["title"] == "vaultlab architecture schematics"


def test_write_accepts_string_path(tmp_path: Path):
    out = tmp_path / "sheet.html"
    result = write_svg_figure_sheet_html(_minimal(), str(out))
    assert result == Path(str(out))
    assert out.exists()


# ---------------------------------------------------------------------------
# Dispatch routing


def test_dispatch_routes_figure_sheet_dataclass(tmp_path: Path):
    from vaultlab.report.dispatch import write_artifact_html

    out = tmp_path / "sheet.html"
    write_artifact_html(out, _full())
    html = out.read_text(encoding="utf-8")
    assert "vaultlab architecture schematics" in html
    assert "Crosstalk pipeline" in html
