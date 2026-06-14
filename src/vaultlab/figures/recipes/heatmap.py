"""heatmap recipe — two-axis matrix visualization with color encoding.

Layout sourced from Schurch 2020 Fig 5 (CN co-occurrence) + Pentimalli 2025
Fig 4B (niche × ligand). See ``heatmap.md`` for the full spec.

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
    "Schurch CM et al., Cell 2020;182:1341 (Fig 5, co-occurrence)",
    "Pentimalli TM et al., Cell Systems 2025;16:101261 (Fig 4B, niche-ligand)",
    "Hickey JW et al., Front Immunol 2021;12:727626 (cluster_by_marker)",
)


def _autoselect_palette(variant: str) -> str:
    if variant == "co_occurrence":
        return "RdBu_r"
    return "viridis"


def render(
    df: pd.DataFrame,
    *,
    variant: Literal["cell_by_feature", "cluster_by_marker", "co_occurrence"] = "cluster_by_marker",
    palette: str | None = None,
    row_order: list[str] | None = None,
    col_order: list[str] | None = None,
    cluster_rows: bool = False,
    cluster_cols: bool = False,
    significance_mask: pd.DataFrame | None = None,
    output_path: Path | str,
    title: str = "",
    contract: FigureContract | None = None,
) -> Path:
    """Render a heatmap.

    Parameters
    ----------
    df
        Numerical matrix as a DataFrame. Rows + columns are labeled.
    variant
        Specialization: ``cell_by_feature``, ``cluster_by_marker``, or
        ``co_occurrence``. Auto-selects palette + normalization.
    palette
        Matplotlib colormap name. Defaults: viridis (sequential),
        RdBu_r (diverging for co_occurrence).
    row_order, col_order
        Optional explicit ordering.
    cluster_rows, cluster_cols
        If True, run scipy hierarchical clustering on that axis. Default False.
    significance_mask
        Optional same-shape DataFrame with p-values; cells where p<0.05 get
        asterisks overlaid (`*` p<0.05, `**` p<0.01, `***` p<0.001).
    output_path
        Path where the figure is saved.
    title
        Figure title.

    Anchor: Schurch 2020 Fig 5 + Pentimalli 2025 Fig 4B (see heatmap.md).
    """

    if variant == "co_occurrence" and df.shape[0] != df.shape[1]:
        raise ValueError(f"co_occurrence variant requires square matrix; got {df.shape}")

    matrix = df.copy()

    if cluster_rows:
        try:
            from scipy.cluster.hierarchy import leaves_list, linkage

            row_link = linkage(matrix.values, method="average")
            row_order_idx = leaves_list(row_link)
            matrix = matrix.iloc[row_order_idx]
        except ImportError:
            logger.warning("scipy not available; skipping row clustering")

    if cluster_cols:
        try:
            from scipy.cluster.hierarchy import leaves_list, linkage

            col_link = linkage(matrix.T.values, method="average")
            col_order_idx = leaves_list(col_link)
            matrix = matrix.iloc[:, col_order_idx]
        except ImportError:
            logger.warning("scipy not available; skipping column clustering")

    if row_order is not None:
        matrix = matrix.reindex(row_order)
    if col_order is not None:
        matrix = matrix[col_order]

    if variant == "cluster_by_marker":
        col_mean = matrix.mean(axis=0)
        col_std = matrix.std(axis=0).replace(0, 1.0)
        matrix = matrix.subtract(col_mean, axis=1).divide(col_std, axis=1)

    if palette is None:
        palette = _autoselect_palette(variant)

    n_rows, n_cols = matrix.shape
    figsize = (max(4.0, n_cols * 0.3 + 2.0), max(3.0, n_rows * 0.3 + 1.5))

    fig, ax = plt.subplots(figsize=figsize, constrained_layout=True)

    if variant == "co_occurrence" or palette in ("RdBu_r", "RdBu", "PuOr_r", "BrBG"):
        vmax = float(np.nanmax(np.abs(matrix.values)))
        vmin = -vmax
    else:
        vmin = float(np.nanmin(matrix.values))
        vmax = float(np.nanmax(matrix.values))

    im = ax.imshow(
        matrix.values,
        cmap=palette,
        aspect="auto",
        vmin=vmin,
        vmax=vmax,
        interpolation="nearest",
    )

    ax.set_xticks(np.arange(n_cols))
    ax.set_xticklabels(matrix.columns, rotation=45, ha="right", fontsize=9)
    ax.set_yticks(np.arange(n_rows))
    ax.set_yticklabels(matrix.index, fontsize=9)

    ax.set_xticks(np.arange(-0.5, n_cols, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, n_rows, 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=0.3)
    ax.tick_params(which="minor", length=0)

    cbar_label_map = {
        "co_occurrence": "log2 fold-change vs null",
        "cluster_by_marker": "Z-score (per marker)",
        "cell_by_feature": "Value",
    }
    cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    cbar.set_label(cbar_label_map.get(variant, "Value"), fontsize=9)
    cbar.ax.tick_params(labelsize=8)

    if significance_mask is not None:
        if not significance_mask.shape == matrix.shape:
            logger.warning(
                "significance_mask shape mismatch; got %s, expected %s — skipping",
                significance_mask.shape,
                matrix.shape,
            )
        else:
            sig = significance_mask.reindex(index=matrix.index, columns=matrix.columns)
            for i, row_label in enumerate(matrix.index):
                for j, col_label in enumerate(matrix.columns):
                    p = float(sig.iloc[i, j])
                    star = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else ""
                    if star:
                        ax.text(j, i, star, ha="center", va="center", fontsize=7, color="black")

    if title:
        ax.set_title(title, fontsize=11)

    out = Path(output_path)
    return save_with_optional_contract(fig, out, contract=contract)
