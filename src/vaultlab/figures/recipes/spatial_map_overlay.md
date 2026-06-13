# Recipe: spatial_map_overlay

Tissue image with cell-type / niche / signaling-density overlay. The
canonical spatial-omics figure: where in the tissue do these cells live?

## Primary anchor

Pentimalli & Rajewsky *Cell Systems* 2025 Figs 3D-F (3D-rendered niches
in NSCLC) + 4C-E (PDGFB / AREG / CCL19 spatial activity density).
Sorin 2023 IMC overlays.

## Public-repo cross-references

- `squidpy.pl.spatial_scatter` — https://squidpy.readthedocs.io/en/stable/api/squidpy.pl.spatial_scatter.html
- `scanpy.pl.spatial` for Visium-style overlays
- scverse spatial patterns

## Variants

- `tissue_bg_with_cells` (default) — H&E / DAPI background + cells colored by category
- `niche_overlay` — cells colored by multicellular-niche assignment with niche regions outlined
- `signaling_density` — continuous heatmap density overlay (ligand activity, etc.)

## Status

✅ **Implemented** (v0.1.0). `render()` produces the spatial overlay (PNG + PDF) and
returns the saved path; handles an optional background image + coordinate alignment.
Structural contract enforced by `tests/test_vaultlab_figures/test_recipe_invariants.py`.
