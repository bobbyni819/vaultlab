"""spatial_map_overlay recipe — tissue image with cell/niche/signaling overlay.

Layout sourced from Pentimalli 2025 Figs 3D-F + 4C-E and Sorin 2023 IMC
overlays.
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
    "Pentimalli TM et al., Cell Systems 2025;16:101261 (Figs 3D-F, 4C-E)",
    "Sorin M et al., Nature 2023;614:548 (IMC overlays)",
)


def _default_palette(variant: str) -> str:
    if variant == "signaling_density":
        return "viridis"
    return "tab20"


def render(
    cells_df: pd.DataFrame,
    *,
    background_image: Path | str | None = None,
    variant: Literal[
        "tissue_bg_with_cells", "niche_overlay", "signaling_density"
    ] = "tissue_bg_with_cells",
    color_col: str = "cell_type",
    palette: str | None = None,
    output_path: Path | str,
    title: str = "",
    point_size: float = 6.0,
    background_alpha: float = 0.4,
    point_alpha: float = 0.8,
    flip_y: bool = True,
) -> Path:
    """Render a spatial map overlay.

    Anchor: Pentimalli 2025 Figs 3D-F + 4C-E (see spatial_map_overlay.md).
    """

    if "x" not in cells_df.columns or "y" not in cells_df.columns:
        raise ValueError(
            "spatial_map_overlay expects 'x' and 'y' columns in cells_df; got "
            f"{list(cells_df.columns)}"
        )
    if color_col not in cells_df.columns:
        raise ValueError(f"color_col {color_col!r} not in cells_df columns")

    if palette is None:
        palette = _default_palette(variant)

    fig, ax = plt.subplots(figsize=(7.0, 6.0), constrained_layout=True)

    if background_image is not None:
        bg_path = Path(background_image)
        if bg_path.exists():
            bg = plt.imread(str(bg_path))
            ax.imshow(bg, alpha=background_alpha, origin="upper" if not flip_y else "lower")
        else:
            logger.warning("background_image not found: %s — skipping", bg_path)

    if variant == "signaling_density":
        sc = ax.scatter(
            cells_df["x"],
            cells_df["y"],
            s=point_size,
            c=cells_df[color_col],
            cmap=palette,
            alpha=point_alpha,
            linewidths=0,
        )
        cbar = fig.colorbar(sc, ax=ax, fraction=0.025, pad=0.02)
        cbar.set_label(color_col, fontsize=9)
        cbar.ax.tick_params(labelsize=8)
    else:
        cats = cells_df[color_col].astype("category")
        unique_cats = cats.cat.categories
        cmap = plt.get_cmap(palette, max(len(unique_cats), 3))
        for i, cat in enumerate(unique_cats):
            mask = cats == cat
            ax.scatter(
                cells_df.loc[mask, "x"],
                cells_df.loc[mask, "y"],
                s=point_size,
                color=cmap(i),
                alpha=point_alpha,
                label=str(cat),
                linewidths=0,
            )
        ax.legend(
            loc="center left",
            bbox_to_anchor=(1.02, 0.5),
            fontsize=8,
            frameon=True,
            edgecolor="black",
            markerscale=2.0,
        )

    if flip_y:
        ax.invert_yaxis()
    ax.set_aspect("equal", adjustable="box")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_visible(False)
    ax.spines["left"].set_visible(False)

    if title:
        ax.set_title(title, fontsize=11)

    out = Path(output_path)
    paths = save_fig(fig, out, dpi=300)
    return paths[0]
