"""Recipe library — six publication-tight figure archetypes.

Each archetype is a Python module with a ``render()`` function and a sibling
``<archetype>.md`` documenting layout, primary anchor paper(s), 2-3 variants,
and public-repo cross-references (scanpy / squidpy / bioconductor / scverse).

The six archetypes (per
``Sources/Notes/figure-archetypes-implementation-roadmap-2026-05-06.md``):

- :mod:`marker_dot_plot` — per-cluster expression of N markers (Hickey 2021)
- :mod:`umap_overlay` — 2D projection colored by cluster/marker (Pentimalli 2025)
- :mod:`heatmap` — cell × feature / co-occurrence matrix (Schurch 2020)
- :mod:`stat_test_panel` — bar/box/violin with significance brackets (Sorin 2023)
- :mod:`multi_panel_composite` — A-B-C-D panel grid (Pentimalli 2025 main figs)
- :mod:`spatial_map_overlay` — tissue image with cell/niche overlay (Pentimalli 2025, Sorin 2023)

All six archetypes are fully implemented as of v0.0.3. Each ``render()`` returns
the saved figure ``Path`` and writes a sibling ``.provenance.json`` recording
the recipe version + anchor papers + input hash.
"""

from vaultlab.figures.recipes import (
    heatmap,
    marker_dot_plot,
    multi_panel_composite,
    spatial_map_overlay,
    stat_test_panel,
    umap_overlay,
)

__all__ = [
    "heatmap",
    "marker_dot_plot",
    "multi_panel_composite",
    "spatial_map_overlay",
    "stat_test_panel",
    "umap_overlay",
]

