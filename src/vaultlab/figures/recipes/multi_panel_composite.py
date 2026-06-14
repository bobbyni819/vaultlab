"""multi_panel_composite recipe — assemble panels into A-B-C-D grid.

Layout sourced from Pentimalli 2025 main figs. Composes existing figure
files (PNG / JPG) into a labeled multi-panel grid with publication-tight
panel-letter annotations.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import matplotlib.pyplot as plt
import numpy as np

if TYPE_CHECKING:
    from vaultlab.figures.contract import FigureContract

from vaultlab.figures.publication.save import save_with_optional_contract

logger = logging.getLogger(__name__)

__all__ = ["ANCHOR_PAPERS", "RECIPE_VERSION", "render"]

RECIPE_VERSION = "0.1.0"

ANCHOR_PAPERS = (
    "Pentimalli TM et al., Cell Systems 2025;16:101261 (main figures)",
    "Hickey JW et al., Nature 2023;619:572 (multi-panel main figures)",
    "Sorin M et al., Nature 2023;614:548 (multi-panel composite layouts)",
)


_GRID_BY_VARIANT: dict[str, tuple[int, int]] = {
    "2x2": (2, 2),
    "3x2": (2, 3),  # 2 rows, 3 cols
    "1xN_row": (1, -1),  # rows=1, cols=auto
    "Nx1_col": (-1, 1),  # cols=1, rows=auto
}


def render(
    panel_paths: Sequence[Path | str],
    *,
    variant: Literal["2x2", "3x2", "1xN_row", "Nx1_col"] = "2x2",
    panel_letters: bool = True,
    panel_letter_size_pt: int = 14,
    panel_letter_color: str = "black",
    output_path: Path | str,
    title: str = "",
    contract: FigureContract | None = None,
    figsize_per_panel: tuple[float, float] = (4.0, 3.0),
) -> Path:
    """Compose N existing figure files into a multi-panel composite.

    Anchor: Pentimalli 2025 main figs (see multi_panel_composite.md).
    """
    panel_paths = [Path(p) for p in panel_paths]
    if not panel_paths:
        raise ValueError("multi_panel_composite needs at least one panel_path")
    for p in panel_paths:
        if not p.exists():
            raise FileNotFoundError(f"panel image not found: {p}")

    n_panels = len(panel_paths)
    rows_arg, cols_arg = _GRID_BY_VARIANT[variant]
    if rows_arg == -1:
        rows = n_panels
        cols = 1
    elif cols_arg == -1:
        rows = 1
        cols = n_panels
    else:
        rows, cols = rows_arg, cols_arg
    if rows * cols < n_panels:
        # Auto-expand rows if user gave a too-small grid
        rows = (n_panels + cols - 1) // cols
        logger.warning(
            "variant %s grid too small for %d panels; auto-expanded to %dx%d",
            variant,
            n_panels,
            rows,
            cols,
        )

    figsize = (cols * figsize_per_panel[0], rows * figsize_per_panel[1])
    fig, axes = plt.subplots(rows, cols, figsize=figsize, constrained_layout=True)
    axes_flat = np.atleast_1d(axes).flatten()

    for idx, panel_path in enumerate(panel_paths):
        ax = axes_flat[idx]
        img = plt.imread(str(panel_path))
        ax.imshow(img)
        ax.axis("off")
        if panel_letters:
            letter = chr(ord("A") + idx)
            ax.text(
                0.0,
                1.02,
                letter,
                transform=ax.transAxes,
                fontsize=panel_letter_size_pt,
                fontweight="bold",
                color=panel_letter_color,
                ha="left",
                va="bottom",
            )

    for idx in range(n_panels, len(axes_flat)):
        axes_flat[idx].axis("off")

    if title:
        fig.suptitle(title, fontsize=12, fontweight="bold")

    out = Path(output_path)
    return save_with_optional_contract(fig, out, contract=contract)
