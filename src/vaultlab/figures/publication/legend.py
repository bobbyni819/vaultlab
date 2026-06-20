"""Legend handling — standalone export and density-aware positioning.

Two concerns this module addresses:
    1. Legend overlay (Rule 1): legends inside an axis often collide with data;
       pick position based on data density, or export as a standalone figure.
    2. Standalone legend export: a separate file the user can place wherever
       in the final figure assembly without matplotlib's whims.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from vaultlab.figures.publication.style import LEGEND_SIZE

if TYPE_CHECKING:
    from pathlib import Path

    from matplotlib.artist import Artist

# Position strings supported by matplotlib (subset; cleaner than passing
# arbitrary strings around).
LegendPos = str  # "best", "upper right", "upper left", "lower left", "lower right",
# "right", "center left", "center right", "lower center",
# "upper center", "center"


def legend_position_for_density(
    x: Sequence[float],
    y: Sequence[float],
    *,
    candidates: Sequence[LegendPos] = ("upper right", "upper left", "lower right", "lower left"),
) -> LegendPos:
    """Pick the legend corner with the fewest data points (Rule 1).

    Splits the x-y bounding box into quadrants and counts points per quadrant.
    Returns the quadrant string with the lowest count.

    Parameters
    ----------
    x, y
        Data coordinates (any sequences with same length).
    candidates
        Legend positions to choose between. Defaults to the four corners.

    Returns
    -------
    str
        One of the candidate positions, suitable for `ax.legend(loc=...)`.

    Examples
    --------
    >>> import numpy as np
    >>> from vaultlab.figures.publication import legend_position_for_density
    >>> # Most points in upper-right quadrant
    >>> rng = np.random.default_rng(42)
    >>> x = np.concatenate([rng.uniform(0, 1, 90), rng.uniform(0, 1, 10)])
    >>> y = np.concatenate([rng.uniform(0, 1, 90), rng.uniform(0, 1, 10)])
    >>> # Function returns one of the four corners; specific choice depends on density
    >>> result = legend_position_for_density(x, y)
    >>> result in ("upper right", "upper left", "lower right", "lower left")
    True

    Notes
    -----
    For dense scatter plots where ALL quadrants are crowded, prefer
    `save_legend()` (standalone export) instead.
    """
    if len(x) != len(y):
        raise ValueError(f"len(x) ({len(x)}) != len(y) ({len(y)})")
    if len(x) == 0:
        return candidates[0]

    x_min, x_max = min(x), max(x)
    y_min, y_max = min(y), max(y)
    x_mid = (x_min + x_max) / 2
    y_mid = (y_min + y_max) / 2

    counts: dict[LegendPos, int] = {}
    for pos in candidates:
        upper = "upper" in pos
        right = "right" in pos
        n = 0
        for xi, yi in zip(x, y, strict=True):
            in_x = (xi > x_mid) if right else (xi <= x_mid)
            in_y = (yi > y_mid) if upper else (yi <= y_mid)
            if in_x and in_y:
                n += 1
        counts[pos] = n

    return min(counts, key=lambda p: counts[p])


def save_legend(
    handles: Sequence[Artist],
    labels: Sequence[str],
    out_path: Path | str,
    *,
    ncol: int = 1,
    title: str | None = None,
    markerscale: float = 1.5,
    fontsize: int = LEGEND_SIZE,
    formats: Sequence[str] = ("png", "pdf"),
    dpi: int = 300,
) -> None:
    """Save a standalone legend as its own figure file.

    Useful when:
        - Legend would overlap data in the main panel
        - You're assembling a multi-panel figure and want the legend in
          a fixed external location
        - Different panels share the same legend

    Parameters
    ----------
    handles, labels
        Output of `ax.get_legend_handles_labels()` (or constructed manually).
    out_path
        Output path WITHOUT extension. Files written as `{out_path}.{format}`
        for each format in `formats`.
    ncol
        Number of legend columns.
    title
        Optional legend title (rendered above entries).
    markerscale
        Scale factor applied to legend markers.
    fontsize
        Legend font size.
    formats
        Output formats (default: PNG + PDF for paper submissions).
    dpi
        Resolution for raster outputs.

    Examples
    --------
    >>> import matplotlib.pyplot as plt
    >>> from vaultlab.figures.publication import save_legend
    >>> fig, ax = plt.subplots()
    >>> ax.plot([0, 1], [0, 1], label="Treatment")
    >>> ax.plot([0, 1], [1, 0], label="Control")
    >>> handles, labels = ax.get_legend_handles_labels()
    >>> save_legend(handles, labels, "/tmp/legend_v1")  # writes legend_v1.png + legend_v1.pdf  # doctest: +SKIP
    """
    from pathlib import Path

    import matplotlib.pyplot as plt

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Sized to the legend content (height proportional to entries / ncol)
    height = 0.3 * len(labels) / max(ncol, 1) + 0.5
    fig_leg, ax_leg = plt.subplots(figsize=(3, height))
    ax_leg.axis("off")

    leg_kwargs: dict[str, object] = {
        "loc": "center",
        "frameon": False,
        "fontsize": fontsize,
        "markerscale": markerscale,
        "ncol": ncol,
    }
    if title is not None:
        leg_kwargs["title"] = title
        leg_kwargs["title_fontsize"] = fontsize + 1

    ax_leg.legend(handles, labels, **leg_kwargs)

    for fmt in formats:
        fig_leg.savefig(
            out_path.with_suffix(f".{fmt}"),
            dpi=dpi,
            bbox_inches="tight",
            facecolor="white",
        )
    plt.close(fig_leg)
