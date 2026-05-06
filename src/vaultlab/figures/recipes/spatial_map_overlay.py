"""spatial_map_overlay recipe — tissue image with cell/niche/signaling overlay.

Layout sourced from Pentimalli 2025 Figs 3D-F + 4C-E and Sorin 2023 IMC
overlays. See ``spatial_map_overlay.md``.

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
    "Pentimalli TM et al., Cell Systems 2025;16:101261 (Figs 3D-F, 4C-E)",
    "Sorin M et al., Nature 2023;614:548 (IMC overlays)",
)


def render(
    cells_df: "pd.DataFrame",
    *,
    background_image: Path | str | None = None,
    variant: Literal["tissue_bg_with_cells", "niche_overlay", "signaling_density"] = "tissue_bg_with_cells",
    color_col: str = "cell_type",
    palette: str | None = None,
    output_path: Path | str,
    title: str = "",
) -> Path:
    """Render a spatial map overlay.

    Parameters
    ----------
    cells_df
        DataFrame with ``x``, ``y`` coordinates plus ``color_col``.
    background_image
        Optional path to tissue background image (H&E, DAPI, etc.).
    variant
        ``tissue_bg_with_cells``, ``niche_overlay``, or ``signaling_density``.
    color_col
        Column for color encoding (default ``cell_type``).
    palette
        Colormap name; defaults inferred per variant.
    output_path
        Path where the figure is saved.
    title
        Figure title.
    """
    raise NotImplementedError(
        "spatial_map_overlay recipe is a stub. Most complex of the 6; needs image-"
        "handling + coordinate alignment. Full implementation lands in Phase 1 "
        "follow-up commit. Contract documented in spatial_map_overlay.md."
    )
