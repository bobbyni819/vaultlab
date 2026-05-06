"""stat_test_panel recipe — bar/box/violin with significance brackets.

Layout sourced from Sorin 2023 Fig 4 + Pentimalli 2025 Fig 5F.
"""

from __future__ import annotations

import itertools
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import matplotlib.pyplot as plt
import numpy as np

if TYPE_CHECKING:
    import pandas as pd

from vaultlab.figures.publication.save import save_fig

logger = logging.getLogger(__name__)

__all__ = ["render", "RECIPE_VERSION", "ANCHOR_PAPERS"]

RECIPE_VERSION = "0.1.0"

ANCHOR_PAPERS = (
    "Sorin M et al., Nature 2023;614:548 (Fig 4)",
    "Pentimalli TM et al., Cell Systems 2025;16:101261 (Fig 5F)",
)


def _pvalue_to_stars(p: float) -> str:
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return "ns"


def _run_test(test: str, group_a, group_b):
    """Return p-value for one of the supported tests; falls back to NaN."""
    a = np.asarray(group_a, dtype=float)
    b = np.asarray(group_b, dtype=float)
    a = a[~np.isnan(a)]
    b = b[~np.isnan(b)]
    if len(a) < 2 or len(b) < 2:
        return float("nan")
    try:
        from scipy import stats  # local import — scipy not in vaultlab base
    except ImportError:
        logger.warning("scipy not available; skipping significance brackets")
        return float("nan")
    if test == "mannwhitneyu":
        return float(stats.mannwhitneyu(a, b, alternative="two-sided").pvalue)
    if test == "ttest_ind":
        return float(stats.ttest_ind(a, b, equal_var=False).pvalue)
    if test == "kruskal":
        return float(stats.kruskal(a, b).pvalue)
    raise ValueError(f"unknown test {test!r}")


def render(
    df: "pd.DataFrame",
    *,
    variant: Literal["bar_with_significance", "box_grouped", "violin_split"] = "bar_with_significance",
    x_col: str,
    y_col: str,
    hue_col: str | None = None,
    test: Literal["mannwhitneyu", "ttest_ind", "kruskal"] = "mannwhitneyu",
    output_path: Path | str,
    title: str = "",
    palette: str = "Set2",
) -> Path:
    """Render a stat-test panel with significance-bracket overlays.

    DataFrame must be in long form: one row per observation, with at minimum
    ``x_col`` (categorical group) and ``y_col`` (numerical value).

    Anchor: Sorin 2023 Fig 4 + Pentimalli 2025 Fig 5F (see stat_test_panel.md).
    """
    import pandas as pd

    if x_col not in df.columns or y_col not in df.columns:
        raise ValueError(f"x_col / y_col not in DataFrame: {x_col!r} / {y_col!r}")

    groups = df[x_col].astype("category").cat.categories.tolist()
    n_groups = len(groups)
    cmap = plt.get_cmap(palette, max(n_groups, 3))

    fig, ax = plt.subplots(figsize=(max(4.0, n_groups * 0.8 + 1.5), 4.0), constrained_layout=True)

    group_data = [df.loc[df[x_col] == g, y_col].values for g in groups]
    positions = np.arange(n_groups)

    if variant == "bar_with_significance":
        means = [float(np.nanmean(d)) if len(d) else 0.0 for d in group_data]
        sems = [float(np.nanstd(d, ddof=1) / np.sqrt(len(d))) if len(d) > 1 else 0.0 for d in group_data]
        bars = ax.bar(
            positions,
            means,
            yerr=sems,
            color=[cmap(i) for i in range(n_groups)],
            edgecolor="black",
            linewidth=0.6,
            capsize=4,
        )
        # Strip overlay (individual data points)
        for i, d in enumerate(group_data):
            if len(d):
                jitter = np.random.RandomState(0).normal(0, 0.05, size=len(d))
                ax.scatter(
                    np.full_like(d, positions[i], dtype=float) + jitter,
                    d,
                    s=6,
                    c="black",
                    alpha=0.4,
                    linewidths=0,
                )

    elif variant == "box_grouped":
        bp = ax.boxplot(
            group_data,
            positions=positions,
            widths=0.55,
            patch_artist=True,
            medianprops={"color": "black", "linewidth": 1.0},
        )
        for i, patch in enumerate(bp["boxes"]):
            patch.set_facecolor(cmap(i))
            patch.set_edgecolor("black")
            patch.set_linewidth(0.6)
        # Strip overlay
        for i, d in enumerate(group_data):
            if len(d):
                jitter = np.random.RandomState(0).normal(0, 0.05, size=len(d))
                ax.scatter(
                    np.full_like(d, positions[i], dtype=float) + jitter,
                    d,
                    s=4,
                    c="black",
                    alpha=0.3,
                    linewidths=0,
                )

    elif variant == "violin_split":
        parts = ax.violinplot(group_data, positions=positions, widths=0.7, showmeans=False, showmedians=True)
        for i, body in enumerate(parts["bodies"]):
            body.set_facecolor(cmap(i))
            body.set_edgecolor("black")
            body.set_linewidth(0.6)
            body.set_alpha(0.7)

    pairs = list(itertools.combinations(range(n_groups), 2))
    if pairs:
        ymax = max([np.nanmax(d) if len(d) else 0.0 for d in group_data])
        ymin = min([np.nanmin(d) if len(d) else 0.0 for d in group_data])
        y_range = ymax - ymin if ymax > ymin else 1.0
        bracket_step = y_range * 0.08
        cur_y = ymax + bracket_step
        for i, j in pairs:
            p = _run_test(test, group_data[i], group_data[j])
            stars = _pvalue_to_stars(p) if not np.isnan(p) else "n/a"
            ax.plot(
                [positions[i], positions[i], positions[j], positions[j]],
                [cur_y, cur_y + bracket_step * 0.3, cur_y + bracket_step * 0.3, cur_y],
                color="black",
                linewidth=0.8,
            )
            ax.text(
                (positions[i] + positions[j]) / 2,
                cur_y + bracket_step * 0.4,
                stars,
                ha="center",
                va="bottom",
                fontsize=8,
            )
            cur_y += bracket_step * 0.9

    ax.set_xticks(positions)
    ax.set_xticklabels(groups, rotation=30, ha="right", fontsize=9)
    ax.set_xlabel(x_col, fontsize=10)
    ax.set_ylabel(y_col, fontsize=10)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    if title:
        ax.set_title(title, fontsize=11)

    out = Path(output_path)
    paths = save_fig(fig, out, dpi=300)
    return paths[0]
