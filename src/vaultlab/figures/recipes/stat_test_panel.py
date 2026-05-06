"""stat_test_panel recipe — bar/box/violin with significance brackets.

Layout sourced from Sorin 2023 Fig 4 + Pentimalli 2025 Fig 5F. See
``stat_test_panel.md``.

🚧 STUB — full implementation pending.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    import pandas as pd

__all__ = ["render", "RECIPE_VERSION", "ANCHOR_PAPERS"]

RECIPE_VERSION = "0.1.0-stub"
ANCHOR_PAPERS = (
    "Sorin M et al., Nature 2023;614:548 (Fig 4)",
    "Pentimalli TM et al., Cell Systems 2025;16:101261 (Fig 5F)",
)


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
) -> Path:
    """Render a statistical-test panel with significance brackets.

    Parameters
    ----------
    df
        DataFrame in long form: one row per observation.
    variant
        ``bar_with_significance``, ``box_grouped``, or ``violin_split``.
    x_col, y_col, hue_col
        Column names for axes + grouping.
    test
        Statistical test for pairwise comparisons. Default Mann-Whitney U.
    output_path
        Path where the figure is saved.
    title
        Figure title.
    """
    raise NotImplementedError(
        "stat_test_panel recipe is a stub. Use marker_dot_plot or heatmap for now; "
        "full implementation lands in Phase 1 follow-up commit. "
        "Contract documented in stat_test_panel.md."
    )
