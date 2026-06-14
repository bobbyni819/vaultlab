"""marker_dot_plot recipe — per-cluster expression of N markers as a dot plot.

Layout sourced from Hickey 2021 Fig 4 (47 markers × 25 clusters). See
`marker_dot_plot.md` for the full spec, anchor papers, and variants.

Public surface: :func:`render`.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import matplotlib.pyplot as plt
import numpy as np

if TYPE_CHECKING:
    import pandas as pd

    from vaultlab.figures.contract import FigureContract

from vaultlab.figures.publication.save import save_with_optional_contract

logger = logging.getLogger(__name__)

__all__ = ["ANCHOR_PAPERS", "RECIPE_VERSION", "render"]

RECIPE_VERSION = "0.1.0"

ANCHOR_PAPERS = (
    "Hickey JW et al., Front Immunol 2021;12:727626 (Fig 4)",
    "Schurch CM et al., Cell 2020;182:1341 (Fig 2C)",
    "Goltsev Y et al., Cell 2018;174:968 (Fig 4)",
)


def render(
    df: pd.DataFrame,
    *,
    cluster_order: list[str] | None = None,
    marker_order: list[str] | None = None,
    variant: Literal["portrait", "landscape", "with_dendrogram"] = "portrait",
    palette: str = "viridis",
    output_path: Path | str,
    title: str = "",
    contract: FigureContract | None = None,
    normalize: Literal["z", "minmax", "none"] = "z",
) -> Path:
    """Render a marker dot plot.

    Parameters
    ----------
    df
        DataFrame with MultiIndex (cluster, marker) and two columns:
        ``fraction_expressing`` (0-1) and ``mean_expression`` (any scale).
    cluster_order, marker_order
        Optional explicit ordering. If None, follow the order present in ``df``.
    variant
        ``portrait`` (markers on Y, clusters on X), ``landscape`` (transposed),
        or ``with_dendrogram`` (adds hierarchical clustering on both axes).
    palette
        Matplotlib colormap name. Defaults to ``viridis``.
    output_path
        Path where the figure is saved. Multiple formats written via
        :func:`save_fig` (PNG + PDF by default).
    title
        Figure title.
    normalize
        ``z`` (z-score within marker), ``minmax``, or ``none``.

    Returns
    -------
    Path
        The PNG output path.

    Anchor: Hickey et al., Front Immunol 2021 Fig 4 (see marker_dot_plot.md).
    """
    import pandas as pd  # local import — pandas not in vaultlab base deps

    if not isinstance(df.index, pd.MultiIndex) or len(df.index.names) != 2:
        raise ValueError(
            f"marker_dot_plot expects a MultiIndex (cluster, marker); got {df.index!r}"
        )
    required = {"fraction_expressing", "mean_expression"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"marker_dot_plot missing required columns: {missing}")

    pivot_size = df["fraction_expressing"].unstack(level="marker", fill_value=0.0)
    pivot_color = df["mean_expression"].unstack(level="marker", fill_value=np.nan)

    if cluster_order is not None:
        pivot_size = pivot_size.reindex(cluster_order)
        pivot_color = pivot_color.reindex(cluster_order)
    if marker_order is not None:
        pivot_size = pivot_size[marker_order]
        pivot_color = pivot_color[marker_order]

    if normalize == "z":
        pivot_color = pivot_color.subtract(pivot_color.mean(axis=0), axis=1).divide(
            pivot_color.std(axis=0).replace(0, 1.0), axis=1
        )
    elif normalize == "minmax":
        col_min = pivot_color.min(axis=0)
        col_max = pivot_color.max(axis=0)
        pivot_color = (pivot_color - col_min) / (col_max - col_min).replace(0, 1.0)

    if variant == "landscape":
        pivot_size = pivot_size.T
        pivot_color = pivot_color.T

    n_rows, n_cols = pivot_size.shape
    figsize = (max(4.0, n_cols * 0.30 + 2.0), max(3.0, n_rows * 0.28 + 1.5))

    fig, ax = plt.subplots(figsize=figsize, constrained_layout=True)

    x_idx, y_idx = np.meshgrid(np.arange(n_cols), np.arange(n_rows))
    sizes = pivot_size.values * 200  # max area = 200 (scatter `s` parameter, sq pts)
    colors = pivot_color.values

    sc = ax.scatter(
        x_idx,
        y_idx,
        s=sizes,
        c=colors,
        cmap=palette,
        edgecolors="black",
        linewidths=0.4,
    )

    ax.set_xticks(np.arange(n_cols))
    ax.set_xticklabels(pivot_size.columns, rotation=45, ha="right", fontsize=9)
    ax.set_yticks(np.arange(n_rows))
    ax.set_yticklabels(pivot_size.index, fontsize=9)
    ax.tick_params(direction="out", length=3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    cbar = fig.colorbar(sc, ax=ax, fraction=0.025, pad=0.02)
    cbar.set_label(
        {"z": "Z-score (per marker)", "minmax": "Min-max (per marker)", "none": "Mean expression"}[
            normalize
        ],
        fontsize=9,
    )
    cbar.ax.tick_params(labelsize=8)

    handles = []
    for frac in [0.25, 0.5, 0.75, 1.0]:
        handles.append(
            plt.scatter(
                [],
                [],
                s=frac * 200,
                c="lightgray",
                edgecolors="black",
                linewidths=0.4,
                label=f"{int(frac * 100)}%",
            )
        )
    # Size legend as a horizontal row BELOW the plot, clear of the data grid and
    # the colorbar. (A right-anchored legend's left edge extended back into the
    # rightmost data column and occluded those dots.)
    ax.legend(
        handles=handles,
        title="Fraction expressing",
        loc="upper center",
        bbox_to_anchor=(0.5, -0.22),
        ncol=4,
        columnspacing=1.6,
        handletextpad=0.2,
        fontsize=8,
        title_fontsize=8,
        frameon=False,
    )

    if title:
        ax.set_title(title, fontsize=11)

    out = Path(output_path)
    return save_with_optional_contract(fig, out, contract=contract)
