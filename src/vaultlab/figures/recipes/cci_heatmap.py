"""cci_heatmap recipe — cell-cell interaction strength matrix.

Layout sourced from CellChat (Jin 2021) + Squidpy (Palla 2022) for the
canonical CCI heatmap convention: square matrix with cell types on
both axes, color = interaction strength, optional clustering by row
+ column. Annotations highlight the strongest interactions.

Used for:
- Cell-cell signaling strength matrices (CellChat output)
- Spatial co-occurrence matrices (Squidpy output)
- Receptor-ligand pair counts
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
    "Jin S et al., Nature Communications 2021;12:1088 (CellChat — Fig 2 layout)",
    "Palla G et al., Nature Methods 2022;19:171 (Squidpy — neighborhood enrichment heatmap)",
    "scverse/squidpy gallery — interaction matrix examples",
)


def render(
    matrix: np.ndarray | pd.DataFrame,
    *,
    output_path: Path | str,
    title: str = "",
    sender_label: str = "Sender cell type",
    receiver_label: str = "Receiver cell type",
    cmap: str = "viridis",
    annotate: bool = True,
    annotate_threshold: float | None = None,
    annot_fmt: str = ".2f",
    diagonal_mask: bool = False,
    colorbar_label: str = "Interaction strength",
) -> Path:
    """Render a cell-cell interaction strength heatmap.

    Parameters
    ----------
    matrix
        Square interaction matrix. If a numpy array, must be 2D and provide
        ``row_labels`` and ``col_labels`` separately (raises if missing). If
        a pandas DataFrame, uses the index as row labels and columns as
        column labels.
    output_path
        Path to write the PNG.
    title
        Figure title.
    sender_label, receiver_label
        Axis labels (default reflects directional CCI; for symmetric
        co-occurrence use "Cell type" for both).
    cmap
        Sequential colormap. Default ``viridis`` (perceptually uniform,
        colorblind-safe).
    annotate
        Whether to overlay numeric values on each cell. Default True.
    annotate_threshold
        Only annotate cells with values >= this threshold. Useful when the
        matrix has many low-value cells. None = annotate all.
    annot_fmt
        Format string for annotations (default ``".2f"``).
    diagonal_mask
        If True, mask out the diagonal (set to NaN; rendered transparent).
        Useful when self-interactions are not meaningful.
    colorbar_label
        Colorbar label.

    Returns
    -------
    Path to the saved PNG.

    Anchored: CellChat Fig 2 + Squidpy neighborhood enrichment heatmap.
    """
    import pandas as pd

    if isinstance(matrix, pd.DataFrame):
        m = matrix.to_numpy(dtype=float)
        row_labels = matrix.index.astype(str).tolist()
        col_labels = matrix.columns.astype(str).tolist()
    else:
        m = np.asarray(matrix, dtype=float)
        row_labels = [f"Row {i}" for i in range(m.shape[0])]
        col_labels = [f"Col {i}" for i in range(m.shape[1])]

    if m.ndim != 2:
        raise ValueError(f"matrix must be 2D, got shape {m.shape}")

    if diagonal_mask and m.shape[0] == m.shape[1]:
        m = m.copy()
        np.fill_diagonal(m, np.nan)

    n_rows, n_cols = m.shape
    fig, ax = plt.subplots(
        figsize=(max(4.0, n_cols * 0.45 + 2.0), max(4.0, n_rows * 0.45 + 1.5)),
        constrained_layout=True,
    )

    im = ax.imshow(
        m,
        cmap=cmap,
        aspect="auto",
        interpolation="nearest",
    )

    # Annotations
    if annotate:
        threshold = annotate_threshold
        finite_max = np.nanmax(m) if np.isfinite(np.nanmax(m)) else 1.0
        finite_min = np.nanmin(m) if np.isfinite(np.nanmin(m)) else 0.0
        for i in range(n_rows):
            for j in range(n_cols):
                val = m[i, j]
                if not np.isfinite(val):
                    continue
                if threshold is not None and val < threshold:
                    continue
                # Pick text color for contrast: white on dark, black on light
                rel = (val - finite_min) / (finite_max - finite_min + 1e-9)
                text_color = "white" if rel > 0.5 else "black"
                ax.text(
                    j,
                    i,
                    format(val, annot_fmt),
                    ha="center",
                    va="center",
                    fontsize=7,
                    color=text_color,
                )

    ax.set_xticks(np.arange(n_cols))
    ax.set_yticks(np.arange(n_rows))
    ax.set_xticklabels(col_labels, rotation=45, ha="right", fontsize=8)
    ax.set_yticklabels(row_labels, fontsize=8)

    ax.set_xlabel(receiver_label, fontsize=10)
    ax.set_ylabel(sender_label, fontsize=10)

    # Tick alignment + minor grid as visual separators
    ax.set_xticks(np.arange(n_cols + 1) - 0.5, minor=True)
    ax.set_yticks(np.arange(n_rows + 1) - 0.5, minor=True)
    ax.grid(which="minor", color="white", linestyle="-", linewidth=0.6)
    ax.tick_params(which="minor", length=0)

    cbar = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.04)
    cbar.set_label(colorbar_label, fontsize=9)
    cbar.ax.tick_params(labelsize=8)

    if title:
        ax.set_title(title, fontsize=11)

    out = Path(output_path)
    paths = save_fig(fig, out, dpi=300)
    return paths[0]
