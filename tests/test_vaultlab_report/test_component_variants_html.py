"""Tests for vaultlab.report.component_variants_html — pattern #8 consumer."""

from __future__ import annotations

import json
from pathlib import Path

from vaultlab.report.component_variants_html import (
    ComponentInventory,
    ComponentVariant,
    build_component_variants_html,
    write_component_variants_html,
)


# ---------------------------------------------------------------------------
# Fixtures


def _minimal() -> ComponentInventory:
    return ComponentInventory(
        title="Slide layouts",
        intro="Two variants for now.",
        variants=[
            ComponentVariant(name="Title slide", description="Single H1"),
            ComponentVariant(name="Two-column", description="50/50 split"),
        ],
    )


def _full() -> ComponentInventory:
    return ComponentInventory(
        title="vaultlab slide layouts",
        intro="Contact-sheet inventory of every slide layout primitive.",
        variants=[
            ComponentVariant(
                name="Title slide — light",
                description="Single H1 on a light background.",
                preview_html="<div style='padding:20px;'>Hello</div>",
                tags=["title", "light"],
            ),
            ComponentVariant(
                name="Title slide — dark",
                description="Single H1 on a dark background.",
                tags=["title", "dark"],
            ),
            ComponentVariant(
                name="Two-column — figure left",
                description="Figure left, text right.",
                tags=["two-column"],
            ),
            ComponentVariant(
                name="Two-column — figure right",
                description="Figure right, text left.",
                tags=["two-column"],
            ),
            ComponentVariant(
                name="Section divider",
                description="Single centered phrase.",
                tags=["divider"],
            ),
        ],
    )


# ---------------------------------------------------------------------------
# build_component_variants_html


def test_build_minimal_returns_well_formed_html():
    html = build_component_variants_html(_minimal())
    assert isinstance(html, str)
    assert html.startswith("<!doctype html>")
    assert "</html>" in html
    assert "Slide layouts" in html
    assert "Title slide" in html


def test_build_full_renders_all_variants():
    html = build_component_variants_html(_full())
    assert "Title slide — light" in html
    assert "Title slide — dark" in html
    assert "Two-column — figure left" in html
    assert "Two-column — figure right" in html
    assert "Section divider" in html


def test_build_inlines_preview_html_when_supplied():
    html = build_component_variants_html(_full())
    # The preview HTML is inlined verbatim (trusted-html contract).
    assert "padding:20px" in html
    assert "Hello" in html


def test_build_groups_by_tag_when_enabled():
    """When group_by_tag is True, variants sharing the first tag are sectioned."""
    inv = ComponentInventory(
        title="t",
        intro="",
        variants=[
            ComponentVariant(name="A", description="", tags=["alpha"]),
            ComponentVariant(name="B", description="", tags=["beta"]),
            ComponentVariant(name="C", description="", tags=["alpha"]),
        ],
        group_by_tag=True,
    )
    html = build_component_variants_html(inv)
    # Group headings appear as section labels.
    assert "alpha" in html
    assert "beta" in html


def test_build_flat_mode_when_grouping_disabled():
    inv = ComponentInventory(
        title="t",
        intro="",
        variants=[
            ComponentVariant(name="A", description="", tags=["alpha"]),
            ComponentVariant(name="B", description="", tags=["beta"]),
        ],
        group_by_tag=False,
    )
    html = build_component_variants_html(inv)
    assert "A" in html
    assert "B" in html


def test_build_empty_variants_still_renders():
    inv = ComponentInventory(title="empty", intro="", variants=[])
    html = build_component_variants_html(inv)
    assert html.startswith("<!doctype html>")
    assert "</html>" in html


def test_build_escapes_user_text():
    inv = ComponentInventory(
        title="<script>alert(1)</script>",
        intro="Test & <b>escape</b>.",
        variants=[
            ComponentVariant(
                name="<bad name>",
                description="<scripted desc>",
                tags=["<bad tag>"],
            )
        ],
    )
    html = build_component_variants_html(inv)
    assert "<script>alert(1)</script>" not in html
    assert "<scripted desc>" not in html
    assert "&lt;script&gt;" in html or "&lt;script" in html


# ---------------------------------------------------------------------------
# write_component_variants_html + provenance


def test_write_creates_output_file(tmp_path: Path):
    out = tmp_path / "comps.html"
    result = write_component_variants_html(_minimal(), out)
    assert result == out
    assert out.exists()


def test_write_creates_provenance_sidecars(tmp_path: Path):
    out = tmp_path / "comps.html"
    write_component_variants_html(_full(), out)
    prov_json = out.with_name(out.name + ".provenance.json")
    method_md = out.with_name(out.name + ".method.md")
    assert prov_json.exists()
    assert method_md.exists()
    payload = json.loads(prov_json.read_text(encoding="utf-8"))
    assert payload["generated_by"] == "vaultlab.report.component_variants_html"
    assert payload["kind"] == "component_variants_html"
    assert payload["params"]["variant_count"] == 5
    assert payload["params"]["title"] == "vaultlab slide layouts"


def test_write_accepts_string_path(tmp_path: Path):
    out = tmp_path / "comps.html"
    result = write_component_variants_html(_minimal(), str(out))
    assert result == Path(str(out))
    assert out.exists()


# ---------------------------------------------------------------------------
# Dispatch routing


def test_dispatch_routes_component_inventory_dataclass(tmp_path: Path):
    from vaultlab.report.dispatch import write_artifact_html

    out = tmp_path / "comps.html"
    write_artifact_html(out, _full())
    html = out.read_text(encoding="utf-8")
    assert "vaultlab slide layouts" in html
    assert "Title slide — light" in html
