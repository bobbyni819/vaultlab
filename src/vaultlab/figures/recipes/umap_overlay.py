"""umap_overlay recipe — 2D projection colored by cluster/marker/metadata.

Layout sourced from Pentimalli & Rajewsky 2025 Fig 1C. See ``umap_overlay.md``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import matplotlib.pyplot as plt

if TYPE_CHECKING:
    import pandas as pd

from vaultlab.figures.publication.save import save_fig

logger = logging.getLogger(__name__)

__all__ = ["ANCHOR_PAPERS", "RECIPE_VERSION", "render"]

RECIPE_VERSION = "0.1.0"

ANCHOR_PAPERS = (
    "Pentimalli TM et al., Cell Systems 2025;16:101261 (Fig 1C)",
    "Hickey JW et al., Nature 2023;619:572 (intestine atlas UMAPs)",
    "Becht E et al., Nature Biotechnology 2019;37:38 (UMAP single-cell embeddings)",
)


def _default_palette(variant: str) -> str:
    if variant == "by_cluster":
        return "tab20"
    return "viridis"


def render(
    df: pd.DataFrame,
    *,
    variant: Literal["by_cluster", "by_marker", "by_metadata_continuous"] = "by_cluster",
    color_col: str | None = None,
    palette: str | None = None,
    output_path: Path | str,
    title: str = "",
    point_size: float = 4.0,
    alpha: float = 0.7,
    show_legend: bool = True,
) -> Path:
    """Render a UMAP overlay.

    DataFrame must have ``UMAP_1`` and ``UMAP_2`` columns. ``color_col`` defaults
    to ``cluster`` for by_cluster variant; required for by_marker /
    by_metadata_continuous.

    Anchor: Pentimalli & Rajewsky 2025 Fig 1C (see umap_overlay.md).
    """

    if "UMAP_1" not in df.columns or "UMAP_2" not in df.columns:
        raise ValueError(
            f"umap_overlay expects 'UMAP_1' and 'UMAP_2' columns; got {list(df.columns)}"
        )

    if color_col is None:
        color_col = "cluster" if variant == "by_cluster" else None
    if color_col is None:
        raise ValueError(f"variant={variant!r} requires color_col to be specified")
    if color_col not in df.columns:
        raise ValueError(f"color_col {color_col!r} not in DataFrame columns")

    if palette is None:
        palette = _default_palette(variant)

    fig, ax = plt.subplots(figsize=(6.5, 5.5), constrained_layout=True)

    if variant == "by_cluster":
        categories = df[color_col].astype("category")
        cats = categories.cat.categories
        cmap = plt.get_cmap(palette, len(cats))
        for i, cat in enumerate(cats):
            mask = categories == cat
            ax.scatter(
                df.loc[mask, "UMAP_1"],
                df.loc[mask, "UMAP_2"],
                s=point_size,
                color=cmap(i),
                alpha=alpha,
                label=str(cat),
                linewidths=0,
            )
        if show_legend:
            ax.legend(
                loc="center left",
                bbox_to_anchor=(1.02, 0.5),
                fontsize=8,
                frameon=True,
                edgecolor="black",
                markerscale=2.0,
            )
    else:
        sc = ax.scatter(
            df["UMAP_1"],
            df["UMAP_2"],
            s=point_size,
            c=df[color_col],
            cmap=palette,
            alpha=alpha,
            linewidths=0,
        )
        cbar = fig.colorbar(sc, ax=ax, fraction=0.025, pad=0.02)
        cbar.set_label(color_col, fontsize=9)
        cbar.ax.tick_params(labelsize=8)

    ax.set_xlabel("UMAP 1", fontsize=10)
    ax.set_ylabel("UMAP 2", fontsize=10)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    if title:
        ax.set_title(title, fontsize=11)

    out = Path(output_path)
    paths = save_fig(fig, out, dpi=300)
    return paths[0]
