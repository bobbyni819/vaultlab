"""vaultlab.figures.understand - hybrid figure-element extraction.

Phase 8b of the master-plan figures build. Bobby's 2026-04-29 insight:
LLM-only coordinate guessing is unreliable; pair the LLM's *semantic*
identification with *programmatic* pixel analysis to get precise locations.

Pipeline (master plan §3.5 + design rationale entry #8):

1. **Describe (LLM)** - read the figure visually; identify discrete elements
   in natural language ("there is a neon-green dimer in panel a representing
   the introduced TCR").
2. **Localize (programmatic)** - find pixel regions matching color motifs
   (or text labels via OCR; planned). Returns precise bounding boxes per
   region.
3. **Match (LLM)** - pair each named element with the best-fitting region.
4. **Verify (LLM, multimodal)** - render the annotated image; read it back;
   confirm each box landed on the intended element. Iterate if not.

This module owns steps 2 (color motif extraction + region merging) and
provides hooks for steps 1, 3, 4 (which are LLM-driven and live in the
runner).

Public API
----------

- :class:`ColorMotif` - declarative color filter (HSV ranges + min area)
- :class:`Region` - extracted pixel region (bbox, area, centroid, motif)
- :class:`ElementAnnotation` - concept-to-region pairing for downstream use
- :func:`extract_regions` - apply color motifs to an image; return regions
- :func:`merge_regions` - merge overlapping / adjacent regions of same motif
- :func:`render_debug_overlay` - draw colored bboxes onto the image with labels

Examples
--------

>>> from vaultlab.figures.understand import (
...     ColorMotif, extract_regions, merge_regions, render_debug_overlay
... )
>>> motifs = [
...     ColorMotif("introduced-tcr-green", (80, 140), 0.40, 0.40, 0.00003),
...     ColorMotif("endogenous-tcr-blue", (195, 240), 0.30, 0.35, 0.00003),
... ]
>>> regions = extract_regions("figure.png", motifs)  # doctest: +SKIP
>>> merged = merge_regions(regions, dilation_px=8)  # doctest: +SKIP
>>> render_debug_overlay("figure.png", merged, "debug.png")  # doctest: +SKIP
"""

from __future__ import annotations

from vaultlab.figures.understand.color_motif import (
    ColorMotif,
    Region,
    extract_regions,
)
from vaultlab.figures.understand.merge import merge_regions
from vaultlab.figures.understand.models import ElementAnnotation
from vaultlab.figures.understand.render import render_debug_overlay

__all__ = [
    "ColorMotif",
    "ElementAnnotation",
    "Region",
    "extract_regions",
    "merge_regions",
    "render_debug_overlay",
]
