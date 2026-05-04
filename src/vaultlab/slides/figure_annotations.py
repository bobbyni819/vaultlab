"""Auto-attach native pptx annotations to a figure based on color motifs.

Bridges :mod:`vaultlab.figures.understand` (color-motif region extraction)
into :func:`build_from_plan` figure-slide rendering. For each figure
that the deck author flags, this module:

1. Runs ``extract_regions + merge_regions`` on the figure (programmatic,
   no LLM needed) to find pixel regions matching declared color motifs.
2. Translates those regions into ``annotation`` dicts in the format
   :func:`add_annotations` expects (rect / oval / circle).
3. Optionally ties each annotation to a bullet ``click_index`` so they
   reveal together with the bullet on click.

Usage:

    from vaultlab.figures.understand import ColorMotif
    from vaultlab.slides.figure_annotations import auto_annotate_figure

    motifs = [
        ColorMotif("red-callout", (350, 360), 0.5, 0.5, 0.0001),
        ColorMotif("yellow-callout", (40, 60), 0.6, 0.6, 0.0001),
    ]
    annotations = auto_annotate_figure(
        image_path,
        motifs=motifs,
        bullet_click_indices=[0, 1],
    )
    # → [{"type": "rect", "bbox": [...], "color": "FF5252", ...}, ...]

The result drops directly into a ``figure`` slide spec's ``annotations``
list. The slide builder's add_annotations call renders them as native
pptx shapes named ``ann{N}_box`` etc.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Sequence

from vaultlab.figures.understand import (
    ColorMotif,
    extract_regions,
    merge_regions,
)

logger = logging.getLogger(__name__)


# Default color motifs for common research-figure callouts.
# (hue_lo, hue_hi) in degrees 0-360; sat_min, val_min in 0-1; min_area_frac.
DEFAULT_MOTIFS = [
    ColorMotif("red-callout",    (350, 10),  0.55, 0.55, 0.0002),
    ColorMotif("yellow-callout", (40, 65),   0.55, 0.55, 0.0002),
    ColorMotif("green-callout",  (90, 140),  0.45, 0.45, 0.0002),
]

# Default annotation colors (hex w/o '#'). Matches CAR-T deck convention.
ANNOTATION_COLORS = {
    "red-callout":    "FF5252",
    "yellow-callout": "FFEB3B",
    "green-callout":  "4CAF50",
    "blue-callout":   "2196F3",
}


def auto_annotate_figure(
    image_path: Path | str,
    *,
    motifs: Sequence[ColorMotif] = DEFAULT_MOTIFS,
    max_regions: int = 4,
    annotation_type: str = "rect",
    weight_pt: int = 4,
    bullet_click_indices: Sequence[int] | None = None,
    dilation_px: int = 8,
) -> list[dict[str, Any]]:
    """Run color-motif extraction + return slide-builder annotation dicts.

    Args:
        image_path: Source figure to scan.
        motifs: Color filters to look for.
        max_regions: Cap on regions returned (largest by area first).
        annotation_type: ``"rect"`` (default) / ``"oval"`` / ``"circle"``.
        weight_pt: Outline stroke weight.
        bullet_click_indices: If supplied (one per region), tie each
            annotation to a bullet's click_index so they reveal together.
            Defaults to ``[0, 1, 2, ...]``.
        dilation_px: Forwarded to ``merge_regions``.

    Returns:
        Annotation dicts ready to drop into a figure slide-spec's
        ``annotations`` field. Empty list if no regions matched or the
        image can't be read.
    """
    image_path = Path(image_path)
    if not image_path.exists():
        return []

    try:
        from PIL import Image
        with Image.open(image_path) as im:
            iw, ih = im.size
    except Exception:  # noqa: BLE001
        return []
    if iw <= 0 or ih <= 0:
        return []

    try:
        regions = extract_regions(image_path, list(motifs))
        regions = merge_regions(regions, dilation_px=dilation_px)
    except Exception as exc:  # noqa: BLE001
        logger.warning("region extraction failed for %s: %s", image_path, exc)
        return []

    if not regions:
        return []

    # Sort by area (largest first) and take top N
    regions = sorted(
        regions,
        key=lambda r: (r.bbox_px[2] - r.bbox_px[0]) * (r.bbox_px[3] - r.bbox_px[1]),
        reverse=True,
    )[:max_regions]

    if bullet_click_indices is None:
        bullet_click_indices = list(range(len(regions)))

    annotations: list[dict[str, Any]] = []
    for i, region in enumerate(regions):
        x0, y0, x1, y1 = region.bbox_px
        # Convert to fractional bbox (0-1) — what add_annotations expects
        bbox_frac = [x0 / iw, y0 / ih, x1 / iw, y1 / ih]
        color = ANNOTATION_COLORS.get(region.motif_name, "FF5252")
        click = bullet_click_indices[i] if i < len(bullet_click_indices) else None
        ann: dict[str, Any] = {
            "type": annotation_type,
            "bbox": bbox_frac,
            "color": color,
            "weight_pt": weight_pt,
        }
        if click is not None:
            ann["click_index"] = click
        annotations.append(ann)
    return annotations


__all__ = ["auto_annotate_figure", "DEFAULT_MOTIFS", "ANNOTATION_COLORS"]
