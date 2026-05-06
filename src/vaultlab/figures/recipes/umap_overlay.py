"""umap_overlay recipe — 2D projection colored by cluster/marker/metadata.

Layout sourced from Pentimalli & Rajewsky 2025 Fig 1C. See ``umap_overlay.md``.

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
    "Pentimalli TM et al., Cell Systems 2025;16:101261 (Fig 1C)",
)


def render(
    df: "pd.DataFrame",
    *,
    variant: Literal["by_cluster", "by_marker", "by_metadata_continuous"] = "by_cluster",
    color_col: str | None = None,
    palette: str | None = None,
    output_path: Path | str,
    title: str = "",
) -> Path:
    """Render a UMAP overlay.

    Parameters
    ----------
    df
        DataFrame with at minimum ``UMAP_1`` and ``UMAP_2`` columns plus any
        columns referenced by ``color_col``.
    variant
        ``by_cluster`` (categorical), ``by_marker`` (continuous expression),
        or ``by_metadata_continuous`` (any continuous metadata).
    color_col
        Column name for color encoding. Defaults inferred per variant.
    palette
        Colormap name. Defaults: ``tab20`` for cluster, ``viridis`` for marker.
    output_path
        Path where the figure is saved.
    title
        Figure title.
    """
    raise NotImplementedError(
        "umap_overlay recipe is a stub. Use marker_dot_plot or heatmap for now; "
        "full implementation lands in Phase 1 follow-up commit. "
        "Contract documented in umap_overlay.md."
    )
