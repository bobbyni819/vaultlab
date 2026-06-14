"""Contract-honouring render tests for figure recipes (NEXT_STEPS B11).

Every recipe's ``render()`` accepts an optional :class:`FigureContract`. When
one is supplied, ``save_with_optional_contract`` triple-exports SVG + PDF +
TIFF at the contract's DPI (camera-ready) instead of the default PNG + PDF.
These tests render a representative spread of recipes with a contract and
assert the triple-export artifacts land on disk. Marked ``slow`` (matplotlib
rasterisation) like the smoke tests.

The default-behaviour (``contract=None``) path is covered by
``test_recipe_smoke.py`` and ``test_save_contract.py``; this file only checks
the opt-in contract path through the recipes.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import vaultlab.figures.recipes as recipes
from vaultlab.figures.contract import FigureContract

pytestmark = pytest.mark.slow

_SEED = 0


def _contract() -> FigureContract:
    return FigureContract(
        conclusion="X is consistent with Y.",
        evidence_chain={"A": "panel A", "B": "panel B"},
    )


def _render_with_contract(name: str, rng: np.random.Generator, out: Path) -> Path:
    mod = getattr(recipes, name)
    contract = _contract()
    if name == "heatmap":
        df = pd.DataFrame(
            rng.random((4, 5)),
            index=[f"c{i}" for i in range(4)],
            columns=[f"M{j}" for j in range(5)],
        )
        return mod.render(df, output_path=out, contract=contract)
    if name == "umap_overlay":
        df = pd.DataFrame(
            {
                "UMAP_1": rng.normal(size=120),
                "UMAP_2": rng.normal(size=120),
                "cluster": rng.choice(list("ABCD"), 120),
            }
        )
        return mod.render(df, output_path=out, contract=contract)
    if name == "stacked_bar":
        df = pd.DataFrame(
            {
                "group": rng.choice(["d1", "d2", "d3"], 120),
                "category": rng.choice(["T", "B", "Mac"], 120),
            }
        )
        return mod.render(
            df, group_col="group", category_col="category", output_path=out, contract=contract
        )
    raise AssertionError(f"no contract-render builder for recipe {name!r}")


@pytest.mark.parametrize("name", ["heatmap", "umap_overlay", "stacked_bar"])
def test_recipe_honours_contract(name: str, tmp_path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg", force=True)
    rng = np.random.default_rng(_SEED)
    out = tmp_path / f"{name}.png"

    returned = _render_with_contract(name, rng, out)

    assert isinstance(returned, Path), f"{name}.render did not return a Path"
    stem = out.with_suffix("")
    for ext in ("svg", "pdf", "tiff"):
        target = stem.with_suffix(f".{ext}")
        assert target.exists(), f"{name}: contract export missing {target}"
        assert target.stat().st_size > 0, f"{name}: contract export empty {target}"
