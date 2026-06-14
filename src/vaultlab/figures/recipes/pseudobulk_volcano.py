"""pseudobulk_volcano recipe — differential abundance volcano plot.

Layout sourced from Pentimalli 2025 Fig 4 + universal volcano convention
in scanpy / decoupler / scvi-tools galleries. X-axis = log2 fold change;
y-axis = -log10(p-value); points colored by significance threshold;
top-N up/down regulated features labeled.

Used for differential gene/protein/metabolite abundance between two
groups (e.g., disease vs control, treated vs untreated, region A vs B).

Anchor papers + lineage in pseudobulk_volcano.md.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

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
    "Pentimalli TM et al., Cell Systems 2025;16:101261 (Fig 4)",
    "scanpy gallery — sc.tl.rank_genes_groups visualization (default volcano layout)",
    "decoupler-py docs — DA volcano standard layout",
)


def render(
    df: pd.DataFrame,
    *,
    log2fc_col: str = "log2_fc",
    pvalue_col: str = "pvalue",
    feature_col: str = "feature",
    output_path: Path | str,
    title: str = "",
    contract: FigureContract | None = None,
    log2fc_threshold: float = 1.0,
    pvalue_threshold: float = 0.05,
    top_n_label: int = 6,
    palette: tuple[str, str, str] = ("#6c757d", "#d62728", "#1f77b4"),
) -> Path:
    """Render a volcano plot for differential abundance analysis.

    Parameters
    ----------
    df
        DataFrame with one row per feature (gene/protein/metabolite). Must
        contain ``log2fc_col``, ``pvalue_col``, ``feature_col``.
    log2fc_col, pvalue_col, feature_col
        Column names. Defaults match common conventions.
    output_path
        Path to write the PNG (also writes companion PDF + provenance).
    log2fc_threshold
        Absolute log2FC threshold to call a feature "regulated". Default 1.0.
    pvalue_threshold
        P-value (or adjusted p-value) threshold. Default 0.05.
    top_n_label
        Number of most-significant up + down features to label by name.
    palette
        Three-color tuple: ``(non_significant, up_regulated, down_regulated)``.
        Default uses gray + Tableau red/blue (colorblind-safe).

    Returns
    -------
    Path
        Path to the saved PNG. PDF + .provenance.json land alongside.

    Anchored: Pentimalli 2025 Fig 4 layout + scanpy + decoupler-py gallery
    convention.
    """

    required = {log2fc_col, pvalue_col, feature_col}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"DataFrame missing required columns: {missing}")

    work = df[[log2fc_col, pvalue_col, feature_col]].copy()
    work = work.dropna(subset=[log2fc_col, pvalue_col])
    # Cap p-values at machine-min to avoid log10(0)
    work[pvalue_col] = work[pvalue_col].clip(lower=1e-300)

    log2fc = work[log2fc_col].to_numpy(dtype=float)
    neg_log_p = -np.log10(work[pvalue_col].to_numpy(dtype=float))
    features = work[feature_col].astype(str).tolist()

    sig_p = work[pvalue_col] < pvalue_threshold
    is_up = sig_p & (work[log2fc_col] > log2fc_threshold)
    is_down = sig_p & (work[log2fc_col] < -log2fc_threshold)

    fig, ax = plt.subplots(figsize=(5.5, 5.0), constrained_layout=True)

    # Non-significant points first (drawn behind the colored ones)
    ns_mask = ~(is_up | is_down)
    ax.scatter(
        log2fc[ns_mask],
        neg_log_p[ns_mask],
        c=palette[0],
        s=12,
        alpha=0.45,
        linewidths=0,
        rasterized=True,
    )
    ax.scatter(
        log2fc[is_up.to_numpy()],
        neg_log_p[is_up.to_numpy()],
        c=palette[1],
        s=18,
        alpha=0.85,
        edgecolors="black",
        linewidths=0.4,
        label="Up-regulated",
    )
    ax.scatter(
        log2fc[is_down.to_numpy()],
        neg_log_p[is_down.to_numpy()],
        c=palette[2],
        s=18,
        alpha=0.85,
        edgecolors="black",
        linewidths=0.4,
        label="Down-regulated",
    )

    # Threshold guide lines (dashed, light)
    ax.axhline(
        -np.log10(pvalue_threshold),
        color="black",
        linestyle="--",
        linewidth=0.5,
        alpha=0.5,
    )
    ax.axvline(log2fc_threshold, color="black", linestyle="--", linewidth=0.5, alpha=0.5)
    ax.axvline(-log2fc_threshold, color="black", linestyle="--", linewidth=0.5, alpha=0.5)

    # Label the top-N up + down regulated features by name
    if top_n_label > 0:
        from matplotlib import patheffects as pe

        # White outline keeps labels legible even where the most-significant
        # points (and their labels) cluster near the top edge.
        halo = [pe.withStroke(linewidth=1.8, foreground="white")]
        for mask_idx, mask in enumerate((is_up.to_numpy(), is_down.to_numpy())):
            indices = np.where(mask)[0]
            if not len(indices):
                continue
            # Rank within the mask by neg_log_p (most significant first)
            ranked = sorted(indices, key=lambda i: -neg_log_p[i])[:top_n_label]
            for i in ranked:
                ax.annotate(
                    features[i],
                    xy=(log2fc[i], neg_log_p[i]),
                    xytext=(4 if mask_idx == 0 else -4, 4),
                    textcoords="offset points",
                    ha="left" if mask_idx == 0 else "right",
                    fontsize=6.5,
                    color="black",
                    path_effects=halo,
                )

    ax.set_xlabel(f"log2 fold change ({log2fc_col})", fontsize=10)
    ax.set_ylabel(f"-log10({pvalue_col})", fontsize=10)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    # Headroom so the top-N labels (clustered at high significance) are not
    # clipped at the top spine.
    ax.margins(y=0.10)

    if title:
        ax.set_title(title, fontsize=11)

    # Legend lower-right: the top-left/top-right are where the up/down labels
    # cluster (most-significant points), so an upper legend collided with them.
    ax.legend(loc="lower right", fontsize=8, frameon=False)

    out = Path(output_path)
    return save_with_optional_contract(fig, out, contract=contract)
