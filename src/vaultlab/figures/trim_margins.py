"""Trim white-margin padding from a figure so it uses the slide canvas fully.

Bobby's 2026-05-04 ask: when a figure has a generous white margin around
the actual content, the placed image is smaller than it needs to be —
because aspect-fit allocates space proportional to the WHOLE image, not
the content within it. Solution: pre-crop the white margin so the
content fills the available box.

Public API:

- :func:`trim_white_margin(image_path, output_dir=None, margin_keep=10)`
  → Path to the trimmed image. Idempotent re-runs.

The trim uses the same :func:`_global_content_bbox` from
``panel_extraction.py`` to find the bounding box of non-background pixels.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from vaultlab.figures.panel_extraction import _binarize, _global_content_bbox
import numpy as np


def trim_white_margin(
    image_path: Path | str,
    *,
    output_dir: Path | str | None = None,
    margin_keep_px: int = 10,
    white_threshold: int = 240,
    overwrite: bool = False,
) -> Path | None:
    """Crop the white margin around a figure's content.

    Args:
        image_path: Source figure.
        output_dir: Where to save the trimmed image. Defaults to the
            directory of ``image_path``.
        margin_keep_px: Pixels of padding to keep around the content
            bbox (so figure labels and axis ticks aren't clipped).
        white_threshold: Pixel intensity ≥ this is treated as white.
        overwrite: If False (default), reuse existing trim file when
            present.

    Returns:
        Path to the trimmed image, or ``None`` if the source can't be
        opened OR the figure is already tightly cropped (no margin to
        trim — returns the original path unchanged).
    """
    image_path = Path(image_path)
    if not image_path.exists():
        return None

    out_dir = Path(output_dir) if output_dir else image_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{image_path.stem}_trimmed{image_path.suffix}"

    if out_path.exists() and not overwrite:
        return out_path

    try:
        img = Image.open(image_path).convert("RGB")
    except Exception:  # noqa: BLE001
        return None
    arr = np.asarray(img.convert("L"))
    binarized = _binarize(arr, threshold=white_threshold)

    x0, y0, x1, y1 = _global_content_bbox(binarized)
    iw, ih = img.size

    # If the bbox is essentially the whole image, no margin to trim — return
    # the original path unchanged.
    if (x1 - x0) > 0.95 * iw and (y1 - y0) > 0.95 * ih:
        return image_path

    # Add margin, clamp to bounds
    x0 = max(0, x0 - margin_keep_px)
    y0 = max(0, y0 - margin_keep_px)
    x1 = min(iw, x1 + margin_keep_px)
    y1 = min(ih, y1 + margin_keep_px)

    cropped = img.crop((x0, y0, x1, y1))
    cropped.save(out_path)
    return out_path


__all__ = ["trim_white_margin"]
