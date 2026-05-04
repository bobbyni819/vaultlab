"""Analyze figure content density via pixel statistics.

Bobby's 2026-05-04 ask: when a figure has lots of small content packed
densely (e.g., a 6-panel figure where each panel has tiny axis labels),
the deck builder should know — so it can pick a layout that gives the
figure MORE area on the slide (full width, side-caption, or top-caption-
in-bottom-right) instead of squeezing it into the default figure-with-
bullets-on-right that wastes 40% of slide width on bullets.

Public API:

- :func:`analyze_figure_density(image_path)` → :class:`FigureDensity`

Heuristics:

- ``content_fraction``: 1 - mean(binarized) — fraction of non-white px.
  - <0.10  : sparse figure, small content, plenty of whitespace
  - 0.10-0.30 : typical multi-panel
  - >0.30  : dense (heat-maps, dense plots) — already uses its area well
- ``small_content_warning``: True when content is sparse AND aspect is
  flat (>1.4) — these figures benefit most from "stretch wider".
- ``content_bbox_fill``: how much of the figure bbox is content. <0.5 =
  generous margins; >0.85 = already tight.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from vaultlab.figures.panel_extraction import _binarize, _global_content_bbox


@dataclass
class FigureDensity:
    """Result of analyzing a figure's pixel-content distribution."""

    content_fraction: float  # 1 - mean(binarized), in [0, 1]
    aspect: float            # width / height
    content_bbox_fill: float # area of content bbox / area of full image
    small_content_warning: bool  # heuristic: sparse + flat → benefits from layout swap
    is_wide_flat: bool       # aspect > 1.4 (good candidate for top-caption-BR)
    is_tall_thin: bool       # aspect < 0.55
    is_dense: bool           # content_fraction > 0.30


def analyze_figure_density(
    image_path: Path | str,
    *,
    white_threshold: int = 240,
    sparse_content_threshold: float = 0.12,
    flat_aspect_threshold: float = 1.4,
) -> FigureDensity | None:
    """Analyze a figure's content density. Returns ``None`` if image unreadable.

    Args:
        image_path: source figure.
        white_threshold: pixel intensity ≥ this is treated as white background.
        sparse_content_threshold: content_fraction below this counts as
            "sparse" — small content relative to figure area.
        flat_aspect_threshold: aspect ≥ this is "flat-wide".
    """
    p = Path(image_path)
    if not p.exists():
        return None
    try:
        with Image.open(p) as im:
            w, h = im.size
            arr = np.asarray(im.convert("L"))
    except Exception:  # noqa: BLE001
        return None
    if w <= 0 or h <= 0 or arr.size == 0:
        return None

    binarized = _binarize(arr, threshold=white_threshold)
    # 1 = white, 0 = content. So content_fraction = 1 - mean(binarized).
    content_fraction = float(1.0 - binarized.mean())
    aspect = w / h

    # Bounding box of content
    cx0, cy0, cx1, cy1 = _global_content_bbox(binarized)
    content_bbox_area = max(0, cx1 - cx0) * max(0, cy1 - cy0)
    full_area = w * h
    content_bbox_fill = content_bbox_area / full_area if full_area else 0.0

    is_wide_flat = aspect >= flat_aspect_threshold and aspect <= 3.5
    is_tall_thin = aspect < 0.55
    is_dense = content_fraction > 0.30

    # "Small content" warning: figure has lots of whitespace AND it's
    # flat-wide (so a top-caption-BR layout would help by giving it the
    # full slide width).
    small_content_warning = (
        content_fraction < sparse_content_threshold and is_wide_flat
    )

    return FigureDensity(
        content_fraction=content_fraction,
        aspect=aspect,
        content_bbox_fill=content_bbox_fill,
        small_content_warning=small_content_warning,
        is_wide_flat=is_wide_flat,
        is_tall_thin=is_tall_thin,
        is_dense=is_dense,
    )


__all__ = ["FigureDensity", "analyze_figure_density"]
