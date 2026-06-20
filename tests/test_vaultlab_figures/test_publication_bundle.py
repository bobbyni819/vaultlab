from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


def _contract(*, warn: bool = False):
    from vaultlab.figures.contract import FigureContract

    return FigureContract(
        conclusion="Toy values support the expected ordering.",
        evidence_chain={"A": "Panel A contains the toy measurement."},
        width_mm=200.0 if warn else 89.0,
        dpi=250 if warn else 300,
    )


def _coverage(**overrides: Any):
    from vaultlab.figures.publication.coverage import CoverageManifest

    values: dict[str, Any] = {
        "figure_id": "fig-toy",
        "script_path": "tests/toy.py",
        "timestamp": "2026-06-20T12:00:00",
        "panel_role": "main",
        "regions_included": ["mucosa", "submucosa"],
        "donors_included": ["d1", "d2"],
        "cell_types_included": ["T", "B"],
        "exclusions": ["muscularis"],
        "exclusion_reasons": {"muscularis": "not assayed"},
        "source_data": ["toy.csv"],
        "source_data_sha256": {"toy.csv": "abc123"},
        "params": {"normalization": "zscore"},
    }
    values.update(overrides)
    return CoverageManifest(**values)


def test_coverage_manifest_json_round_trip_and_footer(tmp_path: Path) -> None:
    manifest = _coverage()
    path = tmp_path / "fig.coverage.json"

    written = manifest.to_json(path)
    loaded = manifest.read_json(path)

    assert written == path
    assert loaded == manifest
    assert loaded.to_dict()["schema"] == "vaultlab-coverage-manifest/v1"
    footer = loaded.footer_text()
    assert "regions: mucosa, submucosa" in footer
    assert "donors: n=2" in footer
    assert "cell types: n=2" in footer
    assert "excluded: muscularis" in footer


def test_coverage_manifest_validate_reports_required_and_footer_mismatch() -> None:
    manifest = _coverage(figure_id="", footer="regions: fabricated", params={"n_regions": -1})

    problems = manifest.validate()

    assert any("figure_id" in problem for problem in problems)
    assert any("negative" in problem and "params.n_regions" in problem for problem in problems)
    assert any("footer" in problem and "manifest" in problem for problem in problems)


def test_save_publication_figure_writes_bundle_and_receipts(tmp_path: Path) -> None:
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from vaultlab.figures.publication.bundle import save_publication_figure

    fig, ax = plt.subplots(figsize=(2, 2))
    ax.plot([0, 1, 2], [0, 1, 0])
    ax.set_xlabel("x")
    ax.set_ylabel("y")

    result = save_publication_figure(
        fig,
        tmp_path / "toy",
        contract=_contract(warn=True),
        coverage=_coverage(),
        recipe_id="toy_recipe",
    )

    assert result.png == tmp_path / "toy_main.png"
    assert result.svg == tmp_path / "toy.svg"
    assert result.pdf == tmp_path / "toy.pdf"
    assert result.coverage_json == tmp_path / "toy.coverage.json"
    assert result.provenance_json == tmp_path / "toy_main.png.provenance.json"
    assert result.method_md == tmp_path / "toy_main.png.method.md"
    for path in (
        result.png,
        result.svg,
        result.pdf,
        result.coverage_json,
        result.provenance_json,
        result.method_md,
    ):
        assert path is not None
        assert path.exists()

    assert result.layout_audit is not None
    assert result.layout_audit.overall_severity in {"pass", "warn", "fail"}
    assert result.coverage_audit is not None
    assert result.coverage_audit.ok is True
    assert result.contract_warnings

    receipt = json.loads(result.provenance_json.read_text(encoding="utf-8"))
    assert receipt["generated_by"] == "publication-bundle"
    assert receipt["kind"] == "figure"
    assert receipt["params"]["recipe_id"] == "toy_recipe"
    assert receipt["params"]["coverage_path"] == str(result.coverage_json)


def test_render_with_contract_dispatches_real_recipe(tmp_path: Path) -> None:
    pd = pytest.importorskip("pandas")

    from vaultlab.figures.publication.bundle import render_with_contract

    df = pd.DataFrame(
        [[1.0, 2.0], [3.0, 4.0]],
        index=["cluster_a", "cluster_b"],
        columns=["marker_1", "marker_2"],
    )

    result = render_with_contract(
        "heatmap",
        df,
        tmp_path / "heatmap_bundle",
        contract=_contract(),
        coverage=_coverage(script_path="vaultlab.figures.recipes.heatmap"),
        variant="cluster_by_marker",
        title="Toy heatmap",
    )

    assert result.png.exists()
    assert result.svg.exists()
    assert result.pdf.exists()
    assert result.coverage_json is not None
    assert result.coverage_json.exists()
