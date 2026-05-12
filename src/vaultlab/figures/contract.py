"""Figure contract — the discipline that must precede plotting code.

Absorbed from the nature-figure skill (Yuan Yizhe, SJTU). Forces the agent
to commit to a *figure contract* — core conclusion, evidence chain,
archetype, backend, export targets — BEFORE any matplotlib/ggplot2 call.

The contract is also load-bearing at audit time: anything that fails the
contract (e.g. a panel that doesn't carry unique evidence, an
"asymmetric" archetype claim with three equal-weight panels, missing
SVG/PDF/TIFF triple-export) is a reviewable rigor issue, not a stylistic
preference.

Public API
----------

- :class:`FigureContract` — the dataclass that holds the commitments
- :class:`FigureArchetype` — the four archetypes
- :func:`validate_contract` — raise :class:`ContractViolation` for missing /
  malformed fields
- :func:`triple_export` — save a matplotlib Figure to SVG + PDF + 600 DPI TIFF
- :data:`NMI_PASTEL` — the low-saturation 8-color palette for dense
  ML/NMI-style figure pages

Background
----------

See ``G:/My Drive/Knowledge/vaultlab/Output/Plans/html-and-nature-skills-2026-05-12.html``
and the upstream skill at ``nature-skills/skills/nature-figure/``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Literal


class FigureArchetype(str, Enum):
    """The four nature-figure archetypes.

    QUANTITATIVE_GRID — multi-panel grid of plots (bar/line/heatmap),
        all panels carry data, no schematic.
    SCHEMATIC_LED_COMPOSITE — schematic up top + data panels below (or
        side-by-side); the schematic carries the framing argument.
    IMAGE_PLATE_AND_QUANT — microscopy/volume images on one side, paired
        with quantitative panels on the other. Usually dark background
        for the image plate.
    ASYMMETRIC_MIXED_MODALITY — one hero panel + subordinate evidence
        panels in differing layouts. Most editorial autonomy.
    """

    QUANTITATIVE_GRID = "quantitative_grid"
    SCHEMATIC_LED_COMPOSITE = "schematic_led_composite"
    IMAGE_PLATE_AND_QUANT = "image_plate_and_quant"
    ASYMMETRIC_MIXED_MODALITY = "asymmetric_mixed_modality"


Backend = Literal["python", "r"]
ExportFormat = Literal["svg", "pdf", "tiff", "png"]


# Low-saturation 8-color palette for dense ML / NMI-style figure pages.
# Reserves saturated green / red for directional cues (gains, drops).
NMI_PASTEL: tuple[str, ...] = (
    "#7BA6C9",  # muted slate-blue
    "#C29F8E",  # taupe
    "#8FB9A8",  # sage
    "#D4B870",  # mustard
    "#9F8DAF",  # dusty violet
    "#B8927B",  # warm sand
    "#7E9CB2",  # cool steel
    "#A6B07E",  # olive
)
# Reserved-for-direction signal colors. Use sparingly.
SIGNAL_GAIN = "#2E7D32"
SIGNAL_LOSS = "#C62828"


# Mandatory matplotlib rcParams when generating publication figures.
RC_PARAMS: dict[str, Any] = {
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
    "svg.fonttype": "none",  # editable text in SVG
    "pdf.fonttype": 42,  # editable TrueType text in PDF
    "font.size": 7,  # 7pt body; raise only for slide-sized panels
    "axes.spines.right": False,
    "axes.spines.top": False,
    "axes.linewidth": 0.8,
    "legend.frameon": False,
}


class ContractViolation(ValueError):
    """Raised when a FigureContract fails validation.

    Failure modes are intended to look like rigor-audit issues, not opaque
    type errors — the message names exactly which commitment is malformed
    or missing.
    """


@dataclass
class FigureContract:
    """The commitments a figure must satisfy before its plotting code runs.

    Attributes
    ----------
    conclusion:
        One-sentence statement of the claim this figure exists to defend.
    evidence_chain:
        Per-panel mapping (panel_id → 1-line evidence statement). Panels
        that don't carry a unique piece of evidence should be dropped.
    archetype:
        One of :class:`FigureArchetype`. Determines layout discipline.
    backend:
        ``"python"`` (matplotlib/seaborn) or ``"r"`` (ggplot2/patchwork).
    width_mm / height_mm:
        Final journal-targeting dimensions (Nature single column ≈ 89mm,
        double ≈ 183mm).
    export_formats:
        Which formats to materialize. Default is ``("svg", "pdf", "tiff")``.
    dpi:
        Raster DPI for TIFF/PNG exports. Defaults to 600.
    stats_block:
        Free-form note on test, n, error bars, multiple-testing correction.
        Required for any figure with statistical claims.
    image_integrity_notes:
        Required for microscopy / blot panels: contrast adjustments,
        gating, splicing, etc.
    source_data_path:
        Path to the source-data file the journal will require. Optional
        at draft stage; mandatory before submission.
    color_policy:
        Free-form note on palette choice. Default: use :data:`NMI_PASTEL`
        and reserve saturated green/red for directional cues.
    notes:
        Free-form notes (limitations, reviewer-anticipation, etc.).
    """

    conclusion: str
    evidence_chain: dict[str, str] = field(default_factory=dict)
    archetype: FigureArchetype = FigureArchetype.QUANTITATIVE_GRID
    backend: Backend = "python"
    width_mm: float = 183.0
    height_mm: float = 120.0
    export_formats: tuple[ExportFormat, ...] = ("svg", "pdf", "tiff")
    dpi: int = 600
    stats_block: str = ""
    image_integrity_notes: str = ""
    source_data_path: Path | str | None = None
    color_policy: str = "NMI_PASTEL; reserve saturated green/red for directional cues"
    notes: str = ""

    def panels(self) -> list[str]:
        """Ordered panel IDs (as inserted into evidence_chain)."""
        return list(self.evidence_chain.keys())


def validate_contract(contract: FigureContract) -> list[str]:
    """Validate a contract. Returns a list of advisory warnings; raises
    :class:`ContractViolation` for hard failures (missing required fields).

    Hard failures (raise):
      * empty conclusion
      * fewer than one panel in evidence_chain
      * archetype claims asymmetric mixed-modality but has only one panel

    Soft warnings (returned, not raised):
      * fewer than 2 panels in a quantitative grid (probably should be a
        single-panel layout)
      * width or height > 183mm (Nature double-column limit)
      * "tiff" export requested with dpi < 300
      * archetype is image-plate-and-quant but no image_integrity_notes
    """
    if not contract.conclusion or not contract.conclusion.strip():
        raise ContractViolation(
            "FigureContract.conclusion is empty — write a one-sentence claim before plotting."
        )
    if not contract.evidence_chain:
        raise ContractViolation(
            "FigureContract.evidence_chain has no panels. Map each panel to "
            "its unique piece of evidence before drawing."
        )
    if (
        contract.archetype == FigureArchetype.ASYMMETRIC_MIXED_MODALITY
        and len(contract.evidence_chain) < 2
    ):
        raise ContractViolation(
            "asymmetric_mixed_modality archetype needs ≥2 panels; got "
            f"{len(contract.evidence_chain)}."
        )

    warnings: list[str] = []
    if contract.archetype == FigureArchetype.QUANTITATIVE_GRID and len(contract.evidence_chain) < 2:
        warnings.append(
            "quantitative_grid with only one panel — consider a single-panel "
            "layout or add subordinate panels."
        )
    if contract.width_mm > 183.5:
        warnings.append(
            f"width_mm={contract.width_mm} exceeds Nature double-column 183mm; "
            "may be rejected at submission."
        )
    if contract.height_mm > 240:
        warnings.append(
            f"height_mm={contract.height_mm} exceeds typical page height; "
            "consider splitting into a supplementary figure."
        )
    if "tiff" in contract.export_formats and contract.dpi < 300:
        warnings.append(
            f"TIFF export at dpi={contract.dpi} — Nature requires ≥300 DPI; "
            "600 DPI is the documented preference."
        )
    if (
        contract.archetype == FigureArchetype.IMAGE_PLATE_AND_QUANT
        and not contract.image_integrity_notes.strip()
    ):
        warnings.append(
            "image_plate_and_quant archetype with no image_integrity_notes — "
            "document contrast adjustments / gating / splicing before submission."
        )
    return warnings


def apply_rcparams(rc_params: dict[str, Any] | None = None) -> None:
    """Apply the mandatory matplotlib rcParams in-place.

    Imports matplotlib lazily so this module doesn't require the figures
    extra to be installed.
    """
    import matplotlib as mpl

    params = dict(RC_PARAMS)
    if rc_params:
        params.update(rc_params)
    mpl.rcParams.update(params)


def triple_export(
    fig: Any,
    stem: Path | str,
    *,
    contract: FigureContract | None = None,
    formats: tuple[ExportFormat, ...] | None = None,
    dpi: int | None = None,
) -> dict[str, Path]:
    """Save a matplotlib Figure to SVG + PDF + 600 DPI TIFF.

    ``stem`` is the path WITHOUT extension. ``contract`` (optional)
    overrides ``formats`` / ``dpi`` from the contract's commitments. The
    function imports matplotlib lazily so vaultlab.figures stays
    importable without the figures extra.

    Returns
    -------
    dict[str, Path]
        Mapping ``{format: written_path}``.
    """
    fmts = formats or (contract.export_formats if contract else ("svg", "pdf", "tiff"))
    use_dpi = dpi or (contract.dpi if contract else 600)
    base = Path(stem)
    base.parent.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    for fmt in fmts:
        target = base.with_suffix(f".{fmt}")
        save_kwargs: dict[str, Any] = {"bbox_inches": "tight"}
        if fmt in {"tiff", "png"}:
            save_kwargs["dpi"] = use_dpi
        fig.savefig(target, **save_kwargs)
        written[fmt] = target
    return written


__all__ = [
    "NMI_PASTEL",
    "RC_PARAMS",
    "SIGNAL_GAIN",
    "SIGNAL_LOSS",
    "Backend",
    "ContractViolation",
    "ExportFormat",
    "FigureArchetype",
    "FigureContract",
    "apply_rcparams",
    "triple_export",
    "validate_contract",
]
