from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from vaultlab.figures.contract import FigureArchetype, FigureContract
from vaultlab.figures.publication.coverage import CoverageManifest
from vaultlab.manuscript.claim_ledger import Claim


def _contract() -> FigureContract:
    return FigureContract(
        conclusion="Toy marker values increase in treated samples.",
        evidence_chain={
            "A": "Panel A compares marker values by treatment arm.",
            "B": "Panel B summarizes donor-level paired differences.",
        },
        archetype=FigureArchetype.QUANTITATIVE_GRID,
        stats_block="paired Wilcoxon test with Benjamini-Hochberg correction",
        image_integrity_notes="No microscopy adjustments; plotted values are summary statistics.",
        source_data_path="data/toy-marker.csv",
        color_policy="Treatment groups use muted blue and signal green.",
        notes="Draft coverage excludes the unpaired pilot donor.",
    )


def _coverage() -> CoverageManifest:
    return CoverageManifest(
        figure_id="fig-toy",
        script_path="scripts/plot_toy.py",
        timestamp="2026-06-20T12:00:00",
        regions_included=["mucosa", "submucosa"],
        donors_included=["d1", "d2", "d3"],
        cell_types_included=["T cell", "B cell"],
        exclusions=["muscularis"],
        exclusion_reasons={"muscularis": "not assayed in this batch"},
        params={"normalization": "zscore", "min_cells": 20},
        source_data=["toy-marker.csv"],
    )


def test_explain_figure_builds_hedged_five_part_explainer() -> None:
    from vaultlab.figures.explain import explain_figure

    explainer = explain_figure(
        contract=_contract(),
        coverage=_coverage(),
        claims=[
            Claim(
                claim_id="C1",
                text="Treatment is compatible with higher marker activity.",
            )
        ],
    )

    assert explainer.figure_id == "fig-toy"
    assert explainer.one_breath
    assert "consistent with" in explainer.one_breath
    assert "proves" not in explainer.to_markdown().lower()
    assert explainer.what_it_is
    assert explainer.how_to_read
    assert explainer.method_plain
    assert explainer.what_it_means
    assert explainer.caveat
    assert "Panel A" in explainer.how_to_read
    assert "3 donors" in explainer.method_plain
    assert "muscularis" in explainer.caveat


def test_explainer_markdown_has_lead_and_required_sections() -> None:
    from vaultlab.figures.explain import explain_figure

    markdown = explain_figure(contract=_contract(), coverage=_coverage()).to_markdown()

    assert markdown.startswith("> 🟢 In one breath:")
    for heading in (
        "### What it is",
        "### How to read it",
        "### Method in plain words",
        "### What it means",
        "### Caveat",
    ):
        assert heading in markdown


def test_refine_fn_receives_and_replaces_deterministic_seed() -> None:
    from vaultlab.figures.explain import FigureExplainer, explain_figure

    seen: list[FigureExplainer] = []

    def refine(seed: FigureExplainer) -> FigureExplainer:
        seen.append(seed)
        return replace(seed, one_breath="Refined text remains consistent with the inputs.")

    explainer = explain_figure(contract=_contract(), refine_fn=refine)

    assert seen
    assert seen[0].one_breath != explainer.one_breath
    assert explainer.one_breath == "Refined text remains consistent with the inputs."


def test_explain_figure_requires_at_least_one_input() -> None:
    from vaultlab.figures.explain import explain_figure

    with pytest.raises(ValueError, match="contract, coverage, or claims"):
        explain_figure()


def test_explain_from_bundle_reads_coverage_json(tmp_path: Path) -> None:
    from vaultlab.figures.explain import explain_from_bundle

    coverage_path = tmp_path / "toy.coverage.json"
    _coverage().to_json(coverage_path)

    explainer = explain_from_bundle(coverage_path, contract=_contract())

    assert explainer.figure_id == "fig-toy"
    assert "3 donors" in explainer.method_plain


def test_write_explainer_writes_stem_explainer_markdown_atomically(tmp_path: Path) -> None:
    from vaultlab.figures.explain import explain_figure, write_explainer

    explainer = explain_figure(contract=_contract(), coverage=_coverage())

    written = write_explainer(tmp_path / "toy.png", explainer)

    assert written == tmp_path / "toy.explainer.md"
    text = written.read_text(encoding="utf-8")
    assert "> 🟢 In one breath:" in text
    assert "### Caveat" in text
