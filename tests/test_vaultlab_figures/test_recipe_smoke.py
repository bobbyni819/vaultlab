"""Smoke-render tests for every figure recipe (NEXT_STEPS B8).

Each recipe's ``render()`` is called with minimal valid synthetic data and must
return a non-empty PNG. Marked ``slow`` (they import matplotlib and rasterise)
so they stay separable from the fast structural invariants in
``test_recipe_invariants.py``. Every recipe in the registry must have a builder
here — an unregistered recipe fails loudly rather than being silently skipped.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import vaultlab.figures.recipes as recipes

pytestmark = pytest.mark.slow

_SEED = 0


def _png_ok(p: Path) -> bool:
    return p.exists() and p.stat().st_size > 1000


def _square_df(rng: np.random.Generator, n: int = 4, prefix: str = "cell") -> pd.DataFrame:
    names = [f"{prefix}{i}" for i in range(n)]
    return pd.DataFrame(rng.random((n, n)), index=names, columns=names)


def _trivial_png(path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    fig.savefig(path)
    plt.close(fig)


def _build_and_render(name: str, rng: np.random.Generator, tmp_path: Path) -> Path:
    out = tmp_path / f"{name}.png"
    mod = getattr(recipes, name)
    if name == "umap_overlay":
        df = pd.DataFrame(
            {
                "UMAP_1": rng.normal(size=120),
                "UMAP_2": rng.normal(size=120),
                "cluster": rng.choice(list("ABCD"), 120),
            }
        )
        return mod.render(df, output_path=out)
    if name == "stat_test_panel":
        df = pd.DataFrame(
            {
                "group": np.repeat(list("AB"), 30),
                "value": np.concatenate([rng.normal(10, 2, 30), rng.normal(12, 2, 30)]),
            }
        )
        return mod.render(df, x_col="group", y_col="value", output_path=out)
    if name == "spatial_map_overlay":
        df = pd.DataFrame(
            {
                "x": rng.uniform(0, 100, 150),
                "y": rng.uniform(0, 100, 150),
                "cell_type": rng.choice(["T", "B", "Mac", "Epi"], 150),
            }
        )
        return mod.render(df, output_path=out)
    if name == "multi_panel_composite":
        panels = []
        for i in range(2):
            pth = tmp_path / f"panel{i}.png"
            _trivial_png(pth)
            panels.append(pth)
        return mod.render(panels, variant="1xN_row", output_path=out)
    if name == "heatmap":
        df = pd.DataFrame(
            rng.random((4, 5)),
            index=[f"c{i}" for i in range(4)],
            columns=[f"M{j}" for j in range(5)],
        )
        return mod.render(df, output_path=out)
    if name == "marker_dot_plot":
        idx = pd.MultiIndex.from_product(
            [[f"c{i}" for i in range(3)], ["CD3", "CD20", "CD68"]],
            names=["cluster", "marker"],
        )
        df = pd.DataFrame(
            {
                "fraction_expressing": rng.uniform(0, 1, len(idx)),
                "mean_expression": rng.normal(0, 1, len(idx)),
            },
            index=idx,
        )
        return mod.render(df, output_path=out)
    if name == "pseudobulk_volcano":
        df = pd.DataFrame(
            {
                "feature": [f"gene{i}" for i in range(50)],
                "log2_fc": rng.normal(0, 2, 50),
                "pvalue": rng.uniform(1e-6, 1, 50),
            }
        )
        return mod.render(df, output_path=out)
    if name == "cci_heatmap":
        return mod.render(_square_df(rng, 4), output_path=out)
    if name == "metabolite_pathway_map":
        nodes = pd.DataFrame(
            {"name": [f"m{i}" for i in range(5)], "abundance": rng.normal(0, 1, 5)}
        )
        return mod.render(nodes, output_path=out)
    if name == "spatial_neighborhood":
        df = _square_df(rng, 4)
        z = (df + df.T) / 2  # symmetric z-matrix
        return mod.render(z, output_path=out)
    if name == "stacked_bar":
        df = pd.DataFrame(
            {
                "group": rng.choice(["d1", "d2", "d3"], 120),
                "category": rng.choice(["T", "B", "Mac"], 120),
            }
        )
        return mod.render(df, group_col="group", category_col="category", output_path=out)
    raise AssertionError(f"no smoke-render builder for recipe {name!r}")


@pytest.mark.parametrize("name", sorted(recipes.__all__))
def test_recipe_smoke_render(name: str, tmp_path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg", force=True)
    rng = np.random.default_rng(_SEED)
    out = _build_and_render(name, rng, tmp_path)
    assert isinstance(out, Path), f"{name}.render did not return a Path"
    assert _png_ok(out), f"{name}.render produced no / empty PNG at {out}"
