"""multi_panel_composite recipe — assemble panels into A-B-C-D grid.

Layout sourced from Pentimalli 2025 main figs. Wraps
``vaultlab.figures.collage`` (lower-level) with publication styling.

🚧 STUB — full implementation pending.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Literal

__all__ = ["render", "RECIPE_VERSION", "ANCHOR_PAPERS"]

RECIPE_VERSION = "0.1.0-stub"
ANCHOR_PAPERS = (
    "Pentimalli TM et al., Cell Systems 2025;16:101261 (main figures)",
)


def render(
    panel_paths: Sequence[Path | str],
    *,
    variant: Literal["2x2", "3x2", "1xN_row", "Nx1_col"] = "2x2",
    panel_letters: bool = True,
    panel_letter_size_pt: int = 14,
    output_path: Path | str,
    title: str = "",
) -> Path:
    """Compose N existing figure files into a multi-panel composite.

    Parameters
    ----------
    panel_paths
        Paths to N existing figure files (PNG / PDF / SVG). Will be tiled
        in the order given.
    variant
        Grid layout. Default 2x2.
    panel_letters
        If True, annotate each panel with A/B/C/D in the top-left corner.
    panel_letter_size_pt
        Font size for panel letters.
    output_path
        Path where the composite is saved.
    title
        Optional figure-level title spanning all panels.
    """
    raise NotImplementedError(
        "multi_panel_composite recipe is a stub. Use vaultlab.figures.collage "
        "(lower-level) or marker_dot_plot/heatmap (atomic recipes) for now. "
        "Full implementation lands in Phase 1 follow-up commit. "
        "Contract documented in multi_panel_composite.md."
    )
