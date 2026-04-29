"""Publication-tight figure styling: rcParams + size presets + style_ax.

Defaults follow Nature/Cell journal conventions: Arial, embeddable text in
PDFs, large readable labels, bold axis spines, tight layouts.

The vaultlab.figures.layout module provides PRESENTATION_LOOSE / POSTER
overrides for non-paper contexts; this module is the publication-tight default.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from matplotlib.axes import Axes

# ---------------------------------------------------------------------------
# Figure size presets (inches; Nature column widths)
# ---------------------------------------------------------------------------
FIG_1COL: Final = (3.5, 3.0)  # single column
FIG_1p5COL: Final = (5.5, 4.0)  # 1.5 column
FIG_2COL: Final = (7.0, 5.0)  # double column
FIG_WIDE: Final = (7.0, 3.5)  # wide panel
FIG_TALL: Final = (3.5, 6.0)  # tall panel (e.g., horizontal bars)
FIG_HEATMAP: Final = (7.0, 6.0)  # heatmaps
FIG_HEATMAP_WIDE: Final = (10.0, 8.0)  # wide heatmaps
FIG_VOLCANO: Final = (5.5, 5.0)  # volcano plots
FIG_UMAP: Final = (5.0, 4.5)  # UMAP / scatter
FIG_BARH: Final = (5.5, 8.0)  # horizontal bar charts
FIG_TRIPLE: Final = (10.5, 4.0)  # 3-panel side-by-side

# ---------------------------------------------------------------------------
# Font sizes (publication-tight; large enough to be readable in print)
# ---------------------------------------------------------------------------
TITLE_SIZE: Final = 14
LABEL_SIZE: Final = 12
TICK_SIZE: Final = 10
LEGEND_SIZE: Final = 10
ANNOT_SIZE: Final = 9
SMALL_SIZE: Final = 8
HEATMAP_ANNOT_SIZE: Final = 7

# ---------------------------------------------------------------------------
# Line / spine widths
# ---------------------------------------------------------------------------
SPINE_WIDTH: Final = 1.5
LINE_WIDTH: Final = 1.5
BAR_EDGE_WIDTH: Final = 0.8
MARKER_SIZE: Final = 20
MARKER_EDGE_WIDTH: Final = 0.5


def setup_rcparams() -> None:
    """Apply publication-tight rcParams globally.

    Sets Arial font (with sane fallbacks), embeddable text in PDF/PS output
    (fonttype=42 → editable text), and regular mathtext.

    Idempotent — safe to call multiple times.

    Examples
    --------
    >>> from vaultlab.figures.publication import setup_rcparams
    >>> setup_rcparams()
    >>> # all subsequent matplotlib figures use the publication-tight defaults
    """
    import matplotlib as mpl
    import matplotlib.pyplot as plt

    plt.rcParams["font.family"] = "Arial"
    plt.rcParams["font.sans-serif"] = ["Arial", "DejaVu Sans", "Helvetica"]
    mpl.rcParams["pdf.fonttype"] = 42
    mpl.rcParams["ps.fonttype"] = 42
    plt.rcParams["mathtext.default"] = "regular"


def style_ax(
    ax: Axes,
    title: str = "",
    xlabel: str = "",
    ylabel: str = "",
    *,
    title_size: int = TITLE_SIZE,
    label_size: int = LABEL_SIZE,
    tick_size: int = TICK_SIZE,
    title_weight: str = "bold",
    label_weight: str = "bold",
    despine: bool = True,
    spine_width: float = SPINE_WIDTH,
) -> None:
    """Apply publication-tight styling to a matplotlib axis.

    Sets bold title + labels with publication-tight font sizes, removes top +
    right spines, thickens remaining spines, and standardizes tick formatting.

    Parameters
    ----------
    ax
        The matplotlib axis to style (in place).
    title, xlabel, ylabel
        Optional text to set on the axis. Empty strings (default) leave existing
        text untouched.
    title_size, label_size, tick_size
        Font sizes (default to module-level publication-tight constants).
    title_weight, label_weight
        Font weight; default "bold" matches Nature/Cell conventions.
    despine
        If True, hide top + right spines (standard publication style).
    spine_width
        Width of remaining spines.

    Examples
    --------
    >>> import matplotlib.pyplot as plt
    >>> from vaultlab.figures.publication import setup_rcparams, style_ax
    >>> setup_rcparams()
    >>> fig, ax = plt.subplots(figsize=(3.5, 3.0))
    >>> ax.plot([1, 2, 3], [4, 5, 6])
    >>> style_ax(ax, title="My panel", xlabel="x", ylabel="y")
    """
    if title:
        ax.set_title(title, fontsize=title_size, fontweight=title_weight, pad=8)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=label_size, fontweight=label_weight)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=label_size, fontweight=label_weight)
    ax.tick_params(labelsize=tick_size, width=1.2, length=4)
    for spine in ax.spines.values():
        spine.set_linewidth(spine_width)
    if despine:
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
