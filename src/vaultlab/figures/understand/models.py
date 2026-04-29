"""Data classes for figure understanding."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ElementAnnotation:
    """A concept paired with its localized region in an image.

    The output of the full describe-find-match pipeline. The renderer in
    :mod:`vaultlab.figures.understand.render` consumes these to draw labeled
    overlays on the original figure.

    Attributes
    ----------
    label
        Short text drawn on the figure (e.g., "Introduced TCR").
    bbox_px
        Pixel-space (x0, y0, x1, y1) bounding box.
    explanation
        Long-form description for speaker notes / hover popups.
    motif_name
        Which :class:`ColorMotif` produced the region (provenance - useful when
        a user disputes the box and wants to know how it was derived).
    confidence
        Coarse 0.0-1.0 confidence; larger regions on rare motifs score higher.
        Currently a placeholder; future: combine area-fraction + motif-rarity
        + LLM verification verdict.
    """

    label: str
    bbox_px: tuple[int, int, int, int]
    explanation: str = ""
    motif_name: str = ""
    confidence: float = 0.0


__all__ = ["ElementAnnotation"]
