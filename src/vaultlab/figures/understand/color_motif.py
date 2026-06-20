"""Color-motif extraction - find pixel regions matching named color filters.

The "localize" step of the hybrid figure-understanding pipeline. Operates on
HSV-converted pixels; thresholds by hue range + minimum saturation + minimum
value. Connected-component analysis turns the binary mask into a list of
:class:`Region` objects with bounding boxes and centroids.

Why HSV (not RGB)
-----------------
BioRender + most published figures vary brightness/saturation as visual emphasis
but keep hue stable. HSV separates those axes - hue alone identifies *"this is
the neon-green family"* even when one instance is darker than another.

Why connected components (not simple masks)
-------------------------------------------
A single mask of all neon-green pixels is useless - it includes the introduced
TCR drawing AND the neon-green text label. Connected components separate them
so each element gets its own bounding box.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import numpy as np
import numpy.typing as npt
from PIL import Image
from skimage import color as skcolor
from skimage import measure, morphology


@dataclass(frozen=True)
class ColorMotif:
    """Declarative color filter for a class of figure elements.

    Attributes
    ----------
    name
        Stable identifier (kebab-case). Used as ``motif_name`` on extracted
        regions and in :func:`render_debug_overlay` legends.
    hue_range
        ``(low, high)`` in degrees [0, 360]. Wrap-around supported when
        ``low > high`` (e.g., ``(350, 10)`` covers reds straddling 0°).
    sat_min
        Minimum saturation in [0, 1]. Prevents matching gray / desaturated noise.
    val_min
        Minimum value (brightness) in [0, 1]. Prevents matching very dark pixels.
    min_area_frac
        Minimum connected-component area as a fraction of total image pixels.
        ~0.00003 (≈30 px on a 1000 px image side; ≈500 px on a 4000 px side)
        is a sensible default for individual receptor-glyph elements in
        BioRender figures.
    """

    name: str
    hue_range: tuple[float, float]
    sat_min: float
    val_min: float
    min_area_frac: float = 0.00003


@dataclass
class Region:
    """One extracted pixel region after thresholding + connected components.

    Attributes
    ----------
    motif_name
        The :class:`ColorMotif` that produced this region.
    bbox_px
        ``(x0, y0, x1, y1)`` pixel coordinates. ``x1, y1`` are exclusive.
    area_px
        Pixel count in the connected component.
    centroid_px
        ``(x, y)`` centroid of the component.
    """

    motif_name: str
    bbox_px: tuple[int, int, int, int]
    area_px: int
    centroid_px: tuple[int, int]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_regions(
    image_path: str | Path,
    motifs: Sequence[ColorMotif],
    *,
    opening_radius: int = 2,
) -> list[Region]:
    """Apply each motif to the image; return the union of region results.

    Parameters
    ----------
    image_path
        Path to the source figure (any PIL-readable format).
    motifs
        The color filters to apply.
    opening_radius
        Morphological opening radius in pixels - removes single-pixel speckle.
        Set to 0 to disable.

    Returns
    -------
    list[Region]
        All regions across all motifs, in motif order then descending area.
    """
    rgb = np.asarray(Image.open(Path(image_path)).convert("RGB"))
    hsv = cast(npt.NDArray[Any], skcolor.rgb2hsv(rgb))
    total_px = rgb.shape[0] * rgb.shape[1]

    out: list[Region] = []
    for motif in motifs:
        mask = _mask_for_motif(hsv, motif)
        if opening_radius > 0:
            mask = cast(
                npt.NDArray[Any],
                morphology.binary_opening(
                    mask,
                    footprint=morphology.disk(opening_radius),  # type: ignore[no-untyped-call]
                ),
            )
        min_area = max(20, int(total_px * motif.min_area_frac))
        mask = cast(
            npt.NDArray[Any],
            morphology.remove_small_objects(mask, min_size=min_area),  # type: ignore[no-untyped-call]
        )

        labels = measure.label(mask, connectivity=2)  # type: ignore[no-untyped-call]
        regions: list[Region] = []
        for region in measure.regionprops(labels):  # type: ignore[no-untyped-call]
            y0, x0, y1, x1 = region.bbox
            regions.append(
                Region(
                    motif_name=motif.name,
                    bbox_px=(int(x0), int(y0), int(x1), int(y1)),
                    area_px=int(region.area),
                    centroid_px=(int(region.centroid[1]), int(region.centroid[0])),
                )
            )
        regions.sort(key=lambda r: -r.area_px)
        out.extend(regions)
    return out


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------


def _mask_for_motif(hsv: npt.NDArray[Any], motif: ColorMotif) -> npt.NDArray[Any]:
    """Return a boolean mask of pixels matching the motif."""
    h = hsv[..., 0] * 360.0
    s = hsv[..., 1]
    v = hsv[..., 2]
    lo, hi = motif.hue_range
    if lo <= hi:
        hue_match = (h >= lo) & (h <= hi)
    else:
        # Wrap-around (e.g., red 350-10)
        hue_match = (h >= lo) | (h <= hi)
    return cast(npt.NDArray[Any], hue_match & (s >= motif.sat_min) & (v >= motif.val_min))


__all__ = ["ColorMotif", "Region", "extract_regions"]
