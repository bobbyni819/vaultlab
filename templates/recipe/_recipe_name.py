"""<recipe_name> recipe — <one-line layout summary>.

SCAFFOLD. Copy to ``src/vaultlab/figures/recipes/<recipe_name>.py``, rename, and
fill in every placeholder. The leading underscore keeps this template from being
importable as a real recipe if it is dropped into the package by mistake.

Layout sourced from <primary anchor>. See the sibling ``<recipe_name>.md``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt

from vaultlab.figures.publication.save import save_fig

logger = logging.getLogger(__name__)

__all__ = ["ANCHOR_PAPERS", "RECIPE_VERSION", "render"]

RECIPE_VERSION = "0.1.0"

# >= 3 REAL published figures (or well-established OSS galleries) whose layout
# this recipe reproduces. tests/test_vaultlab_figures/test_recipe_invariants.py
# FAILS the build if a recipe ships fewer than 3.
ANCHOR_PAPERS = (
    "Author A et al., Journal Year;vol:page (Fig N)",  # replace with a REAL figure
    "Author B et al., Journal Year;vol:page (Fig N)",  # replace with a REAL figure
    "scverse/<tool> gallery — <example>",              # replace with a REAL source
)


def render(
    data: Any,
    *,
    output_path: Path | str,
    title: str = "",
) -> Path:
    """Render the <recipe_name> figure.

    Parameters
    ----------
    data
        Be SPECIFIC about the expected input shape — column names, dtypes,
        index. (e.g. "long-form DataFrame with columns ``group``, ``value``".)
    output_path
        Where to write the figure. ``save_fig`` writes PNG + PDF by default.
    title
        Optional figure title.

    Returns
    -------
    Path
        The PNG output path (``save_fig`` returns every written format; the
        recipe contract returns ``paths[0]``).
    """
    fig, ax = plt.subplots(figsize=(4.5, 3.2))
    try:
        # --- replace with the real plotting logic ---
        ax.text(0.5, 0.5, "scaffold — implement render()", ha="center", va="center")
        if title:
            ax.set_title(title)
        fig.tight_layout()
        paths = save_fig(fig, Path(output_path), dpi=300)
    finally:
        plt.close(fig)
    return paths[0]
