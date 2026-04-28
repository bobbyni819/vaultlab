"""Color palettes + Rule 14 neutral-grey defaults.

The Rule 14 discipline (figure-design-rules-learned.md §14):
    Default to neutral grey when row labels already name the category. Opt in
    to color ONLY for sign (up/down/ns), cross-panel tracking, or secondary
    axis. This survived rounds 12-14 of the metabolism review and is now
    prescriptive.

Bare matplotlib defaults to a viridis-cycle that paints categorical bars in
rainbow colors. That looks generated. This module fights that default.
"""

from __future__ import annotations

from typing import Final, Mapping, Sequence

# ---------------------------------------------------------------------------
# Colorblind-safe palettes
# ---------------------------------------------------------------------------

#: Paul Tol's qualitative colorblind-safe palette (9 colors).
#: Reference: https://personal.sron.nl/~pault/
CB_PALETTE: Final[tuple[str, ...]] = (
    "#332288", "#88CCEE", "#44AA99", "#117733",
    "#999933", "#DDCC77", "#CC6677", "#882255", "#AA4499",
)

#: Extended palette for >9 categories (24 colors). Earlier 9 match CB_PALETTE
#: for stable mapping.
EXT_PALETTE: Final[tuple[str, ...]] = CB_PALETTE + (
    "#661100", "#6699CC", "#AA4466", "#4477AA", "#228833",
    "#CCBB44", "#EE6677", "#AA3377", "#BBBBBB", "#000000",
    "#66CCEE", "#1B9E77", "#D95F02", "#7570B3", "#E7298A",
)

# ---------------------------------------------------------------------------
# Neutral defaults (Rule 14)
# ---------------------------------------------------------------------------

#: Default fill for categorical bars when the row label already names the
#: category. Light enough to read black tick labels on top.
NEUTRAL_GREY: Final = "#888888"

#: Edge color paired with NEUTRAL_GREY for bars.
NEUTRAL_GREY_EDGE: Final = "#444444"

# ---------------------------------------------------------------------------
# Significance encoding (Rule 14: opt-in for sign)
# ---------------------------------------------------------------------------

SIG_COLOR_UP: Final = "#E64B35"     #: Red for up / enriched / positive
SIG_COLOR_DOWN: Final = "#4DBBD5"   #: Blue for down / depleted / negative
SIG_COLOR_NS: Final = "#CCCCCC"     #: Grey for non-significant


# ---------------------------------------------------------------------------
# Palette registry — for project-specific extensions
# ---------------------------------------------------------------------------


class PaletteRegistry:
    """Registry of named palettes for cross-figure consistency.

    A project (e.g., a CODEX run) registers its palettes once and recipes
    look them up by name. This way, "Cluster 3 = blue" stays consistent
    across every panel of a multi-figure study.

    Examples
    --------
    >>> reg = PaletteRegistry()
    >>> reg.register("cell_types", {"T cell": "#5A89A7", "B cell": "#8B008B"})
    >>> reg["cell_types"]["T cell"]
    '#5A89A7'
    >>> reg.list_palettes()
    ['cell_types']
    """

    def __init__(self) -> None:
        self._palettes: dict[str, dict[str, str]] = {}

    def register(self, name: str, palette: Mapping[str, str]) -> None:
        """Register a named palette (label -> hex color)."""
        self._palettes[name] = dict(palette)

    def __getitem__(self, name: str) -> dict[str, str]:
        return self._palettes[name]

    def get(self, name: str, default: dict[str, str] | None = None) -> dict[str, str] | None:
        return self._palettes.get(name, default)

    def list_palettes(self) -> list[str]:
        return sorted(self._palettes.keys())

    def __contains__(self, name: str) -> bool:
        return name in self._palettes


def palette_for(n: int) -> tuple[str, ...]:
    """Return a colorblind-safe palette of length n.

    Uses CB_PALETTE for n <= 9; EXT_PALETTE for 9 < n <= 24; cycles
    EXT_PALETTE for n > 24 (with warning — at that point you probably
    want grouping or a different visualization).

    Examples
    --------
    >>> from vaultlab.figures.publication import palette_for
    >>> palette_for(3)
    ('#332288', '#88CCEE', '#44AA99')
    >>> len(palette_for(15))
    15
    """
    if n <= 0:
        return ()
    if n <= len(CB_PALETTE):
        return CB_PALETTE[:n]
    if n <= len(EXT_PALETTE):
        return EXT_PALETTE[:n]
    # n > 24: cycle and warn
    import warnings
    warnings.warn(
        f"palette_for(n={n}) exceeds 24 distinct colors. Consider grouping "
        f"or a different visualization. Cycling EXT_PALETTE.",
        stacklevel=2,
    )
    cycled = list(EXT_PALETTE) * ((n // len(EXT_PALETTE)) + 1)
    return tuple(cycled[:n])


def bar_fill(
    labels: Sequence[str],
    *,
    sign: Sequence[float] | None = None,
    palette: Mapping[str, str] | None = None,
    default: str = NEUTRAL_GREY,
) -> list[str]:
    """Choose bar colors per Rule 14 discipline.

    Decision order:
        1. If `sign` is provided, color by sign of values (red up / blue down /
           grey ns). Sign-encoding overrides palette.
        2. Else if `palette` is provided AND a label maps in it, use that
           color. Bars without a palette entry default to NEUTRAL_GREY.
        3. Else default everything to NEUTRAL_GREY.

    The deliberate default to NEUTRAL_GREY is the Rule 14 fix for the rainbow
    bar plots that survived rounds 1-12 of the metabolism review. Color is
    information; only opt in when it carries meaning.

    Parameters
    ----------
    labels
        Bar category labels, in the same order as the bars.
    sign
        Optional values to color by sign (positive=up, negative=down, ~0=ns).
        Use this for log fold-change, t-statistic, or signed effect sizes.
    palette
        Optional explicit color mapping (label -> hex). For categories that
        carry consistent identity across figures (e.g., cell-type colors).
    default
        Fallback for labels with no entry in the palette. Defaults to
        NEUTRAL_GREY.

    Returns
    -------
    list[str]
        Hex color strings, one per label.

    Examples
    --------
    >>> from vaultlab.figures.publication import bar_fill, NEUTRAL_GREY
    >>> bar_fill(["A", "B", "C"])
    ['#888888', '#888888', '#888888']
    >>> bar_fill(["A", "B"], sign=[2.5, -1.2])
    ['#E64B35', '#4DBBD5']
    >>> bar_fill(["T", "B"], palette={"T": "#5A89A7", "B": "#8B008B"})
    ['#5A89A7', '#8B008B']
    """
    if sign is not None:
        if len(sign) != len(labels):
            raise ValueError(
                f"len(sign) ({len(sign)}) != len(labels) ({len(labels)})"
            )
        # Threshold near-zero values to NS at +/- 1e-3 (caller can pre-threshold)
        return [
            SIG_COLOR_UP if s > 1e-3 else SIG_COLOR_DOWN if s < -1e-3 else SIG_COLOR_NS
            for s in sign
        ]

    if palette is not None:
        return [palette.get(lbl, default) for lbl in labels]

    return [default] * len(labels)
