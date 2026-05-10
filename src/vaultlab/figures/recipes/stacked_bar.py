"""stacked_bar recipe — relative cell-type / lipid-class frequencies per group.

Layout sourced from Hickey 2021 (multiplex-IF cell-type frequency stacks) +
Schurch 2020 (CCI frequency comparisons across patient groups). Standard
output for any cohort comparison where each group's composition is shown
as proportional segments stacked to 100%.

Used for:
- Cell-type frequency across patient groups (CODEX, multiplex IF)
- Lipid-class frequency across donor cohorts (MALDI IMS)
- Niche-composition comparison
- Treatment-response stratification
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
    "Hickey JW et al., Nature Methods 2021;18:1265 (Fig 4 — immune cell-type frequencies)",
    "Schurch CM et al., Cell 2020;182:1341 (Fig 2 — CCI cohort frequencies)",
    "scanpy gallery — sc.pl.dotplot + grouped abundance plots",
)


def render(
    df: pd.DataFrame,
    *,
    group_col: str,
    category_col: str,
    value_col: str | None = None,
    output_path: Path | str,
    title: str = "",
    palette: str = "tab20",
    normalize_to_100: bool = True,
    horizontal: bool = False,
    legend_loc: str = "right",
) -> Path:
    """Render a stacked bar chart of category frequencies per group.

    Parameters
    ----------
    df
        Long-form DataFrame. One row per (group, category) observation.
    group_col
        Column with group labels (e.g., ``"donor"``, ``"cohort"``, ``"treatment"``).
    category_col
        Column with category labels (e.g., ``"cell_type"``, ``"lipid_class"``).
    value_col
        Column with counts/abundances. If ``None``, uses observation count
        (treats each row as 1).
    output_path
        Path to write the PNG.
    title
        Optional figure title.
    palette
        matplotlib colormap name. ``tab20`` provides 20 distinguishable colors;
        for >20 categories consider grouping.
    normalize_to_100
        If True (default), bars sum to 100% within each group. If False,
        absolute counts.
    horizontal
        If True, bars run left-right (group labels on y-axis). Useful for
        long group names. Default False.
    legend_loc
        ``"right"`` (default) places legend outside the axes. ``"bottom"``
        places below.

    Returns
    -------
    Path to the saved PNG.

    Anchored: Hickey 2021 + Schurch 2020 layout — see stacked_bar.md.
    """

    required = {group_col, category_col}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"DataFrame missing required columns: {missing}")
    if value_col and value_col not in df.columns:
        raise ValueError(f"value_col {value_col!r} not in DataFrame")

    if value_col is None:
        # Count rows per (group, category)
        pivot = df.groupby([group_col, category_col]).size().unstack(fill_value=0)
    else:
        pivot = df.groupby([group_col, category_col])[value_col].sum().unstack(fill_value=0)

    if normalize_to_100:
        row_sums = pivot.sum(axis=1).replace(0, np.nan)
        pivot = pivot.div(row_sums, axis=0).fillna(0) * 100

    groups = pivot.index.tolist()
    categories = pivot.columns.tolist()
    n_categories = len(categories)
    cmap = plt.get_cmap(palette, max(n_categories, 3))
    colors = [cmap(i) for i in range(n_categories)]

    if horizontal:
        fig, ax = plt.subplots(
            figsize=(6.0, max(3.0, len(groups) * 0.35 + 1.5)),
            constrained_layout=True,
        )
        positions = np.arange(len(groups))
        left = np.zeros(len(groups))
        for i, cat in enumerate(categories):
            vals = pivot[cat].to_numpy()
            ax.barh(
                positions,
                vals,
                left=left,
                color=colors[i],
                edgecolor="white",
                linewidth=0.4,
                label=str(cat),
            )
            left += vals
        ax.set_yticks(positions)
        ax.set_yticklabels(groups, fontsize=9)
        ax.set_xlabel("Proportion (%)" if normalize_to_100 else (value_col or "Count"), fontsize=10)
        ax.set_ylabel(group_col, fontsize=10)
        if normalize_to_100:
            ax.set_xlim(0, 100)
    else:
        fig, ax = plt.subplots(
            figsize=(max(4.0, len(groups) * 0.6 + 1.5), 4.5),
            constrained_layout=True,
        )
        positions = np.arange(len(groups))
        bottom = np.zeros(len(groups))
        for i, cat in enumerate(categories):
            vals = pivot[cat].to_numpy()
            ax.bar(
                positions,
                vals,
                bottom=bottom,
                color=colors[i],
                edgecolor="white",
                linewidth=0.4,
                label=str(cat),
            )
            bottom += vals
        ax.set_xticks(positions)
        ax.set_xticklabels(groups, rotation=30, ha="right", fontsize=9)
        ax.set_xlabel(group_col, fontsize=10)
        ax.set_ylabel("Proportion (%)" if normalize_to_100 else (value_col or "Count"), fontsize=10)
        if normalize_to_100:
            ax.set_ylim(0, 100)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    if title:
        ax.set_title(title, fontsize=11)

    if legend_loc == "right":
        ax.legend(
            bbox_to_anchor=(1.02, 1.0),
            loc="upper left",
            fontsize=8,
            frameon=False,
            title=category_col,
            title_fontsize=9,
        )
    else:
        ax.legend(
            bbox_to_anchor=(0.5, -0.15),
            loc="upper center",
            ncol=min(n_categories, 6),
            fontsize=8,
            frameon=False,
        )

    out = Path(output_path)
    paths = save_fig(fig, out, dpi=300)
    return paths[0]
