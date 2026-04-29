"""Multi-format figure save with provenance sidecar.

`save_fig()` writes the figure in multiple formats (PNG + PDF by default) and
returns the list of output paths. The provenance sidecar (`.provenance.json`)
is intentionally NOT written here — that's a separate concern handled by
`vaultlab.provenance.write_provenance()` so callers can attach the rich
input/code/params context.

Convention (per AGENTS.md): every recipe's `render()` function calls
`save_fig()` and then `vaultlab.provenance.write_provenance()` immediately
after, so each figure has both a PNG/PDF + a provenance receipt.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from matplotlib.figure import Figure


def save_fig(
    fig: Figure,
    out_path: Path | str,
    *,
    formats: Sequence[str] = ("png", "pdf"),
    dpi: int = 300,
    facecolor: str = "white",
    bbox_inches: str = "tight",
    close: bool = True,
) -> list[Path]:
    """Save a matplotlib figure in multiple formats.

    Parameters
    ----------
    fig
        The matplotlib figure to save.
    out_path
        Output path WITHOUT extension. Files written as `{out_path}.{format}`
        for each format in `formats`. Parent directory created if missing.
    formats
        Output formats. Defaults to ("png", "pdf") for paper submissions.
        For high-DPI raster only: ("png",). For vector only: ("pdf", "svg").
    dpi
        Resolution for raster formats. 300 is journal-acceptable; 600 for
        camera-ready.
    facecolor
        Figure face color. "white" prevents transparent backgrounds in
        rendered PowerPoint slides.
    bbox_inches
        Passed to `fig.savefig`. "tight" trims whitespace.
    close
        If True (default), close the figure after saving to free memory.

    Returns
    -------
    list[Path]
        Paths of files written, in the order of `formats`.

    Examples
    --------
    >>> import matplotlib.pyplot as plt
    >>> from vaultlab.figures.publication import save_fig
    >>> fig, ax = plt.subplots()
    >>> ax.plot([0, 1], [0, 1])
    >>> paths = save_fig(fig, "/tmp/example_v1")  # doctest: +SKIP
    >>> # paths == [Path('/tmp/example_v1.png'), Path('/tmp/example_v1.pdf')]

    Notes
    -----
    This function does NOT write a provenance sidecar. To get a full audit
    trail, follow with::

        from vaultlab.provenance import write_provenance
        write_provenance(paths[0], inputs=..., params=..., code_called=...)

    The provenance writer creates `{out_path}.provenance.json` and
    `{out_path}.method.md` per the vaultlab reproducibility convention.
    """
    import matplotlib.pyplot as plt

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for fmt in formats:
        target = out_path.with_suffix(f".{fmt}")
        fig.savefig(
            target,
            dpi=dpi,
            bbox_inches=bbox_inches,
            facecolor=facecolor,
        )
        written.append(target)

    if close:
        plt.close(fig)

    return written
