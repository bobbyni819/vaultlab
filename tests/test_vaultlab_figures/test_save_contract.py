"""Tests for save_with_optional_contract — the B11 foundation.

The opt-in path that lets a recipe satisfy a FigureContract (600 dpi
SVG+PDF+TIFF) without changing its default 300 dpi PNG+PDF behaviour.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import pytest

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt  # noqa: E402

from vaultlab.figures.contract import (  # noqa: E402
    ContractViolation,
    FigureContract,
)
from vaultlab.figures.publication.save import save_with_optional_contract  # noqa: E402

pytestmark = pytest.mark.slow


def _fig() -> plt.Figure:
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    return fig


def test_no_contract_writes_png_pdf_returns_png(tmp_path: Path) -> None:
    """Default path is unchanged: PNG + PDF, returns the PNG."""
    p = save_with_optional_contract(_fig(), tmp_path / "f.png")
    assert p == tmp_path / "f.png"
    assert (tmp_path / "f.png").exists()
    assert (tmp_path / "f.pdf").exists()


def test_contract_triple_exports_returns_pdf(tmp_path: Path) -> None:
    """With a contract: SVG + PDF + TIFF, returns the (vector) PDF."""
    contract = FigureContract(
        conclusion="X is consistent with Y.",
        evidence_chain={"A": "panel A shows the trend", "B": "panel B replicates"},
    )
    p = save_with_optional_contract(_fig(), tmp_path / "f.png", contract=contract)
    assert p == tmp_path / "f.pdf"
    for ext in ("svg", "pdf", "tiff"):
        assert (tmp_path / f"f.{ext}").exists()


def test_invalid_contract_raises(tmp_path: Path) -> None:
    """A hard contract failure (empty conclusion) is raised, not swallowed."""
    bad = FigureContract(conclusion="", evidence_chain={"A": "x"})
    fig = _fig()
    with pytest.raises(ContractViolation):
        save_with_optional_contract(fig, tmp_path / "f.png", contract=bad)
    plt.close(fig)
