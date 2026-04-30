"""vaultlab.figures — figure acquisition + understanding + publication.

Submodules:

* :mod:`vaultlab.figures.acquisition` — pull figures from APIs (PMC OA tar,
  Springer OA JSON).  Papers without an API path are marked
  ``source="unavailable"`` and skipped from figure pipelines.
"""

from __future__ import annotations

from vaultlab.figures.acquisition import (
    Figure,
    FigureAcquisitionResult,
    acquire_figures,
    acquire_figures_for_corpus,
    figure_cache_dir,
)

__all__ = [
    "Figure",
    "FigureAcquisitionResult",
    "acquire_figures",
    "acquire_figures_for_corpus",
    "figure_cache_dir",
]
