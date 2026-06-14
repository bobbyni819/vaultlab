"""Multi-format figure save (provenance is a separate, opt-in concern).

`save_fig()` writes the figure in multiple formats (PNG + PDF by default) and
returns the list of output paths. The provenance sidecar (`.provenance.json` +
`.method.md`) is intentionally NOT written here — that's a separate concern
handled by `vaultlab.provenance.write_receipts()`, so a caller can attach the
rich input/code/params context (a `ProvenanceRecord`) only when it wants a
receipt.

Convention (per AGENTS.md Red Line #2): a pipeline that *produces* a figure as
an audited artifact follows its `save_fig()` with `write_receipts(path,
record)` — e.g. `vaultlab.analysis.run_pipeline` does this for every figure it
emits. The low-level `recipes.*.render()` helpers, by contrast, only save the
image (no receipt); receipts are the producing caller's job, not the recipe's.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from matplotlib.figure import Figure

    from vaultlab.figures.contract import FigureContract


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

        from vaultlab.provenance import ProvenanceRecord, write_receipts
        write_receipts(paths[0], ProvenanceRecord(generated_by=..., kind=...,
                                                  inputs=..., params=...))

    `write_receipts` creates `{path}.provenance.json` and `{path}.method.md`
    per the vaultlab reproducibility convention.
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


def save_with_optional_contract(
    fig: Figure,
    out_path: Path | str,
    *,
    contract: FigureContract | None = None,
    dpi: int = 300,
) -> Path:
    """Save a recipe figure, optionally honouring a :class:`FigureContract`.

    Default (``contract is None``): PNG + PDF at ``dpi`` via :func:`save_fig`,
    returning the PNG path — exactly the existing recipe convention, unchanged.

    With a contract: validate it (``validate_contract`` raises
    ``ContractViolation`` on hard failures), then triple-export to the
    contract's formats (SVG + PDF + TIFF) at its DPI (default 600) for
    camera-ready journal output, returning the PDF path (vector, journal-
    friendly) or the first written path. This is the opt-in path that lets a
    recipe satisfy ``vaultlab.figures.contract`` (NEXT_STEPS B11) without
    changing any recipe's default behaviour.
    """
    out = Path(out_path)
    if contract is None:
        return save_fig(fig, out, dpi=dpi)[0]

    from vaultlab.figures.contract import triple_export, validate_contract

    validate_contract(contract)  # raises ContractViolation on a hard failure
    written = triple_export(fig, out.with_suffix(""), contract=contract)
    # triple_export does not close the figure; match save_fig's close-after-save.
    import matplotlib.pyplot as plt

    plt.close(fig)
    return written.get("pdf") or next(iter(written.values()))
