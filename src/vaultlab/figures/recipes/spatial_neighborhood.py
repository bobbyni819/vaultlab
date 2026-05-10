"""spatial_neighborhood recipe — spatial neighborhood enrichment matrix.

Layout sourced from Squidpy (Palla 2022) + Schurch 2020. Square cell-type
× cell-type matrix where color = z-score enrichment (positive = more
proximal than chance; negative = avoidant). Diverging colormap centered
on zero; cells annotated with significance markers.

Used for:
- Spatial co-occurrence enrichment from CODEX / spatial transcriptomics
- "Which cell types live together?" matrix for tissue architecture papers
- Niche-relationship visualization
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import numpy as np

if TYPE_CHECKING:
    import pandas as pd

from vaultlab.figures.publication.save import save_fig

logger = logging.getLogger(__name__)

__all__ = ["ANCHOR_PAPERS", "RECIPE_VERSION", "render"]

RECIPE_VERSION = "0.1.0"

ANCHOR_PAPERS = (
    "Palla G et al., Nature Methods 2022;19:171 (Squidpy — Fig 3 spatial neighborhood enrichment)",
    "Schurch CM et al., Cell 2020;182:1341 (CCI spatial neighborhoods, Fig 4)",
    "scverse/squidpy docs — sq.gr.nhood_enrichment + sq.pl.nhood_enrichment",
)


def render(
    z_matrix: np.ndarray | pd.DataFrame,
    *,
    output_path: Path | str,
    title: str = "",
    cmap: str = "RdBu_r",
    vmin: float | None = None,
    vmax: float | None = None,
    significance_threshold: float = 2.0,
    show_significance_markers: bool = True,
    diagonal_mask: bool = True,
    cluster_axes: bool = False,
) -> Path:
    """Render a spatial neighborhood enrichment heatmap.

    Parameters
    ----------
    z_matrix
        Square z-score matrix from spatial neighborhood enrichment analysis
        (e.g., output of squidpy.gr.nhood_enrichment). Positive z-scores =
        more proximal than chance; negative = avoidant.
    output_path
        Path to write the PNG.
    title
        Optional figure title.
    cmap
        Diverging colormap centered on zero. Default ``RdBu_r`` (red = high,
        blue = low; intuitive for enrichment).
    vmin, vmax
        Color limits. If None, symmetric around zero with magnitude
        ``max(|z_matrix|)``.
    significance_threshold
        Z-score threshold for marking cells as significantly enriched (|z|
        >= this value). Default 2.0 (~95% CI).
    show_significance_markers
        Overlay ``*`` on cells where |z| >= threshold. Default True.
    diagonal_mask
        Mask self-pairings. Default True (self-co-occurrence is trivially
        positive and uninformative).
    cluster_axes
        If True, hierarchically cluster rows + columns to group similar
        cell types. Requires scipy. Default False.

    Returns
    -------
    Path to the saved PNG.

    Anchored: Squidpy Fig 3 + Schurch 2020 Fig 4 layout.
    """
    import pandas as pd

    if isinstance(z_matrix, pd.DataFrame):
        m = z_matrix.to_numpy(dtype=float)
        row_labels = z_matrix.index.astype(str).tolist()
        col_labels = z_matrix.columns.astype(str).tolist()
    else:
        m = np.asarray(z_matrix, dtype=float)
        row_labels = [f"Type {i}" for i in range(m.shape[0])]
        col_labels = [f"Type {i}" for i in range(m.shape[1])]

    if m.ndim != 2:
        raise ValueError(f"z_matrix must be 2D, got shape {m.shape}")

    if cluster_axes:
        try:
            from scipy.cluster.hierarchy import leaves_list, linkage
            from scipy.spatial.distance import squareform

            # Cluster on the absolute z-score distance for symmetry
            dist = 1.0 / (1.0 + np.abs(m))
            np.fill_diagonal(dist, 0.0)
            condensed = squareform(dist, checks=False)
            Z = linkage(condensed, method="average")
            order = leaves_list(Z)
            m = m[np.ix_(order, order)]
            row_labels = [row_labels[i] for i in order]
            col_labels = [col_labels[i] for i in order]
        except ImportError:
            logger.warning("scipy.cluster not available; skipping cluster_axes")

    if diagonal_mask and m.shape[0] == m.shape[1]:
        m = m.copy()
        np.fill_diagonal(m, np.nan)

    n_rows, n_cols = m.shape

    if vmin is None and vmax is None:
        finite = m[np.isfinite(m)]
        if finite.size:
            mag = float(np.max(np.abs(finite)))
            vmin, vmax = -mag, mag
        else:
            vmin, vmax = -1.0, 1.0
    elif vmin is None:
        vmin = -abs(vmax)
    elif vmax is None:
        vmax = abs(vmin)

    fig, ax = plt.subplots(
        figsize=(max(4.0, n_cols * 0.45 + 2.0), max(4.0, n_rows * 0.45 + 1.5)),
        constrained_layout=True,
    )

    im = ax.imshow(
        m,
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        aspect="auto",
        interpolation="nearest",
    )

    if show_significance_markers:
        for i in range(n_rows):
            for j in range(n_cols):
                val = m[i, j]
                if not np.isfinite(val):
                    continue
                if abs(val) >= significance_threshold:
                    ax.text(
                        j,
                        i,
                        "*",
                        ha="center",
                        va="center",
                        fontsize=12,
                        fontweight="bold",
                        color="black",
                    )

    ax.set_xticks(np.arange(n_cols))
    ax.set_yticks(np.arange(n_rows))
    ax.set_xticklabels(col_labels, rotation=45, ha="right", fontsize=8)
    ax.set_yticklabels(row_labels, fontsize=8)

    ax.set_xlabel("Cell type", fontsize=10)
    ax.set_ylabel("Cell type", fontsize=10)

    ax.set_xticks(np.arange(n_cols + 1) - 0.5, minor=True)
    ax.set_yticks(np.arange(n_rows + 1) - 0.5, minor=True)
    ax.grid(which="minor", color="white", linestyle="-", linewidth=0.6)
    ax.tick_params(which="minor", length=0)

    cbar = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.04)
    cbar.set_label("Neighborhood enrichment\n(z-score)", fontsize=9)
    cbar.ax.tick_params(labelsize=8)

    if title:
        ax.set_title(title, fontsize=11)

    out = Path(output_path)
    paths = save_fig(fig, out, dpi=300)
    return paths[0]
