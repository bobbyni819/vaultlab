"""Recipe library — publication-tight figure archetypes.

Each archetype is a Python module with a ``render()`` function and a sibling
``<archetype>.md`` documenting layout, primary anchor paper(s), 2-3 variants,
and public-repo cross-references (scanpy / squidpy / bioconductor / scverse).

The library now ships 11 archetypes (6 originals + 5 metabolism-priority
expansions per SPEC-L). Each ``render()`` saves the figure and returns its
``Path``; it does not itself write a provenance receipt. A pipeline that emits
a recipe figure as an audited artifact attaches the ``.provenance.json`` +
``.method.md`` receipt with ``vaultlab.provenance.write_receipts`` (the recipe
version + anchor papers belong in that record's params).

Original 6 (v0.0.3):

- :mod:`marker_dot_plot` — per-cluster expression of N markers (Hickey 2021)
- :mod:`umap_overlay` — 2D projection colored by cluster/marker (Pentimalli 2025)
- :mod:`heatmap` — cell × feature / co-occurrence matrix (Schurch 2020)
- :mod:`stat_test_panel` — bar/box/violin with significance brackets (Sorin 2023)
- :mod:`multi_panel_composite` — A-B-C-D panel grid (Pentimalli 2025)
- :mod:`spatial_map_overlay` — tissue image with cell/niche overlay (Pentimalli + Sorin)

SPEC-L expansion (metabolism-priority, shipped 2026-05-08):

- :mod:`pseudobulk_volcano` — log2FC vs -log10(p) volcano (Pentimalli 2025 Fig 4)
- :mod:`stacked_bar` — cell-type / lipid-class frequencies per group (Hickey 2021 Fig 4)
- :mod:`cci_heatmap` — cell-cell interaction strength matrix (CellChat / Squidpy)
- :mod:`spatial_neighborhood` — neighborhood enrichment z-scores (Squidpy / Schurch 2020)
- :mod:`metabolite_pathway_map` — pathway diagram with abundance overlay (Pentimalli + decoupler-py)
"""

from vaultlab.figures.recipes import (
    cci_heatmap,
    heatmap,
    marker_dot_plot,
    metabolite_pathway_map,
    multi_panel_composite,
    pseudobulk_volcano,
    spatial_map_overlay,
    spatial_neighborhood,
    stacked_bar,
    stat_test_panel,
    umap_overlay,
)

__all__ = [
    # Original 6
    "heatmap",
    "marker_dot_plot",
    "multi_panel_composite",
    "spatial_map_overlay",
    "stat_test_panel",
    "umap_overlay",
    # SPEC-L expansion
    "cci_heatmap",
    "metabolite_pathway_map",
    "pseudobulk_volcano",
    "spatial_neighborhood",
    "stacked_bar",
]
