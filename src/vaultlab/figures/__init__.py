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
from vaultlab.figures.explain import (
    FigureExplainer,
    explain_figure,
    explain_from_bundle,
    write_explainer,
)
from vaultlab.figures.index import (
    FigureStage,
    archive_superseded,
    default_stage,
    find_existing_for_claim,
    get_figure_stage,
    list_by_stage,
    manuscript_figures,
    set_figure_stage,
)

__all__ = [
    "Figure",
    "FigureAcquisitionResult",
    "FigureExplainer",
    "FigureStage",
    "acquire_figures",
    "acquire_figures_for_corpus",
    "archive_superseded",
    "default_stage",
    "explain_figure",
    "explain_from_bundle",
    "figure_cache_dir",
    "find_existing_for_claim",
    "get_figure_stage",
    "list_by_stage",
    "manuscript_figures",
    "set_figure_stage",
    "write_explainer",
]
