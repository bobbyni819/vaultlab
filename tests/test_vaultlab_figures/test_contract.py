"""Tests for vaultlab.figures.contract — figure contract discipline."""

from __future__ import annotations

from pathlib import Path

import pytest

from vaultlab.figures.contract import (
    NMI_PASTEL,
    RC_PARAMS,
    SIGNAL_GAIN,
    SIGNAL_LOSS,
    ContractViolation,
    FigureArchetype,
    FigureContract,
    triple_export,
    validate_contract,
)

# ---------------------------------------------------------------------------
# FigureContract dataclass


def test_default_contract_has_required_fields():
    c = FigureContract(conclusion="X recovers Y in 5/6 tissues.")
    assert c.conclusion
    assert c.backend == "python"
    assert c.archetype == FigureArchetype.QUANTITATIVE_GRID
    assert c.dpi == 600
    assert "svg" in c.export_formats and "pdf" in c.export_formats and "tiff" in c.export_formats


def test_panels_returns_ordered_ids():
    c = FigureContract(
        conclusion="x",
        evidence_chain={"a": "x", "b": "y", "c": "z"},
    )
    assert c.panels() == ["a", "b", "c"]


# ---------------------------------------------------------------------------
# validate_contract — hard failures


def test_empty_conclusion_raises():
    with pytest.raises(ContractViolation, match="conclusion is empty"):
        validate_contract(FigureContract(conclusion=""))


def test_whitespace_conclusion_raises():
    with pytest.raises(ContractViolation, match="conclusion is empty"):
        validate_contract(FigureContract(conclusion="   "))


def test_no_panels_raises():
    with pytest.raises(ContractViolation, match="evidence_chain has no panels"):
        validate_contract(FigureContract(conclusion="x"))


def test_asymmetric_with_single_panel_raises():
    with pytest.raises(ContractViolation, match="needs ≥2 panels"):
        validate_contract(
            FigureContract(
                conclusion="x",
                evidence_chain={"a": "x"},
                archetype=FigureArchetype.ASYMMETRIC_MIXED_MODALITY,
            )
        )


# ---------------------------------------------------------------------------
# validate_contract — soft warnings


def test_quantitative_grid_single_panel_warns():
    warnings = validate_contract(
        FigureContract(
            conclusion="x",
            evidence_chain={"a": "x"},
            archetype=FigureArchetype.QUANTITATIVE_GRID,
        )
    )
    assert any("single-panel" in w for w in warnings)


def test_overwide_warns():
    warnings = validate_contract(
        FigureContract(
            conclusion="x",
            evidence_chain={"a": "x", "b": "y"},
            width_mm=200,
        )
    )
    assert any("183mm" in w for w in warnings)


def test_low_dpi_tiff_warns():
    warnings = validate_contract(
        FigureContract(
            conclusion="x",
            evidence_chain={"a": "x", "b": "y"},
            export_formats=("tiff",),
            dpi=200,
        )
    )
    assert any("300 DPI" in w for w in warnings)


def test_image_plate_without_integrity_notes_warns():
    warnings = validate_contract(
        FigureContract(
            conclusion="x",
            evidence_chain={"a": "x", "b": "y"},
            archetype=FigureArchetype.IMAGE_PLATE_AND_QUANT,
        )
    )
    assert any("image_integrity_notes" in w for w in warnings)


def test_well_formed_contract_no_warnings():
    warnings = validate_contract(
        FigureContract(
            conclusion="X recovers Y.",
            evidence_chain={
                "a": "UMAP gt",
                "b": "UMAP method",
                "c": "ARI bars",
                "d": "Sensitivity",
            },
            archetype=FigureArchetype.QUANTITATIVE_GRID,
            width_mm=183,
            height_mm=120,
            dpi=600,
        )
    )
    assert warnings == []


# ---------------------------------------------------------------------------
# Palette + rcParams


def test_nmi_pastel_has_eight_colors():
    assert len(NMI_PASTEL) == 8
    for color in NMI_PASTEL:
        assert color.startswith("#")
        assert len(color) == 7


def test_signal_colors_are_green_and_red():
    assert SIGNAL_GAIN.startswith("#")
    assert SIGNAL_LOSS.startswith("#")


def test_rc_params_includes_required_keys():
    for key in (
        "font.family",
        "font.sans-serif",
        "svg.fonttype",
        "pdf.fonttype",
        "font.size",
    ):
        assert key in RC_PARAMS


def test_rc_params_svg_fonttype_is_none():
    """Editable SVG text requires svg.fonttype = 'none'."""
    assert RC_PARAMS["svg.fonttype"] == "none"


def test_rc_params_pdf_fonttype_is_truetype():
    assert RC_PARAMS["pdf.fonttype"] == 42


# ---------------------------------------------------------------------------
# triple_export — needs matplotlib


def test_triple_export_writes_svg_pdf_tiff(tmp_path: Path):
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(2, 2))
    ax.plot([0, 1], [0, 1])

    written = triple_export(fig, tmp_path / "fig1")
    plt.close(fig)

    assert (tmp_path / "fig1.svg").exists()
    assert (tmp_path / "fig1.pdf").exists()
    assert (tmp_path / "fig1.tiff").exists()
    assert set(written.keys()) == {"svg", "pdf", "tiff"}


def test_triple_export_respects_contract_formats(tmp_path: Path):
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(2, 2))
    ax.plot([0, 1], [0, 1])

    contract = FigureContract(
        conclusion="x",
        evidence_chain={"a": "x", "b": "y"},
        export_formats=("svg", "png"),
        dpi=300,
    )
    written = triple_export(fig, tmp_path / "fig2", contract=contract)
    plt.close(fig)

    assert (tmp_path / "fig2.svg").exists()
    assert (tmp_path / "fig2.png").exists()
    assert not (tmp_path / "fig2.pdf").exists()
    assert set(written.keys()) == {"svg", "png"}


def test_triple_export_creates_parent_dirs(tmp_path: Path):
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(2, 2))
    ax.plot([0, 1])

    deep_path = tmp_path / "nested" / "deeper" / "fig3"
    triple_export(fig, deep_path, formats=("svg",))
    plt.close(fig)

    assert (tmp_path / "nested" / "deeper" / "fig3.svg").exists()


# ---------------------------------------------------------------------------
# apply_rcparams (depends on matplotlib)


def test_apply_rcparams_sets_mpl_rcparams():
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg")
    import matplotlib as mpl

    from vaultlab.figures.contract import apply_rcparams

    original = mpl.rcParams["font.size"]
    try:
        apply_rcparams()
        assert mpl.rcParams["svg.fonttype"] == "none"
        assert mpl.rcParams["pdf.fonttype"] == 42
        assert mpl.rcParams["font.size"] == 7
    finally:
        mpl.rcParams["font.size"] = original


def test_apply_rcparams_with_override():
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg")
    import matplotlib as mpl

    from vaultlab.figures.contract import apply_rcparams

    original = mpl.rcParams["font.size"]
    try:
        apply_rcparams({"font.size": 9})
        assert mpl.rcParams["font.size"] == 9
    finally:
        mpl.rcParams["font.size"] = original
