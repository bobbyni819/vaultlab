"""Crop a multi-panel figure to a single named panel.

Bobby's 2026-05-04 ask: when a figure has panels A/B/C/D/E/F/G and a
slide only needs ONE of them, crop to that panel rather than placing
the whole figure (which makes the relevant content tiny).

Pipeline:
1. Run :func:`detect_panels` on the source figure.
2. Look up the requested label (case-insensitive; "A" matches "a").
3. Crop the source PIL image to the panel's bbox.
4. Save next to the original with a suffix (``<orig>_panel-A.png``) so
   re-runs are idempotent.

Public API:

- :func:`crop_to_panel(image_path, panel_label, output_dir=None)` → Path
- :func:`crop_to_panels(image_path, panel_labels, output_dir=None)` →
   dict[label, Path] for batch
"""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image

from vaultlab.figures.panel_extraction import Panel, detect_panels

logger = logging.getLogger(__name__)


def crop_to_panel(
    image_path: Path | str,
    panel_label: str,
    *,
    output_dir: Path | str | None = None,
    margin_px: int = 8,
    overwrite: bool = False,
) -> Path | None:
    """Crop a multi-panel figure to a single named panel.

    Args:
        image_path: Source figure.
        panel_label: Panel letter to crop to (case-insensitive).
        output_dir: Where to save the cropped panel. Defaults to the
            directory of ``image_path``.
        margin_px: Pixels of padding to include around the detected
            panel bbox so we don't clip panel labels or axis ticks.
        overwrite: If False (default), reuse existing crop file when
            already present (idempotent re-runs).

    Returns:
        Path to the cropped panel image, or ``None`` if the panel label
        wasn't found in the figure.
    """
    image_path = Path(image_path)
    if not image_path.exists():
        return None

    out_dir = Path(output_dir) if output_dir else image_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    label_norm = panel_label.strip().upper()
    out_path = out_dir / f"{image_path.stem}_panel-{label_norm}{image_path.suffix}"

    if out_path.exists() and not overwrite:
        return out_path

    panels = detect_panels(image_path)
    if not panels:
        return None

    target = next((p for p in panels if p.label == label_norm), None)
    if target is None:
        logger.info(
            "Panel %r not found in %s. Available: %s",
            label_norm, image_path.name, [p.label for p in panels],
        )
        return None

    img = Image.open(image_path)
    iw, ih = img.size
    x0, y0, x1, y1 = target.bbox_px
    # Add margin, clamp to image bounds
    x0 = max(0, x0 - margin_px)
    y0 = max(0, y0 - margin_px)
    x1 = min(iw, x1 + margin_px)
    y1 = min(ih, y1 + margin_px)

    cropped = img.crop((x0, y0, x1, y1))
    cropped.save(out_path)
    return out_path


def crop_to_panels(
    image_path: Path | str,
    panel_labels: list[str],
    *,
    output_dir: Path | str | None = None,
    margin_px: int = 8,
    overwrite: bool = False,
) -> dict[str, Path]:
    """Batch-crop multiple panels from a figure. Returns label→path map.

    Labels not found in the figure are silently omitted from the result.
    """
    out: dict[str, Path] = {}
    for label in panel_labels:
        p = crop_to_panel(
            image_path, label,
            output_dir=output_dir, margin_px=margin_px, overwrite=overwrite,
        )
        if p is not None:
            out[label.strip().upper()] = p
    return out


__all__ = ["crop_to_panel", "crop_to_panels"]
