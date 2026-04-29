---
name: squidpy
description: Spatial omics analysis in Python — spatial graphs, neighborhood enrichment, ligand-receptor analysis. Companion to scanpy.
domains: [spatial, spatial-transcriptomics, spatial-omics, visium, xenium, codex]
install: pip install squidpy
docs_url: https://squidpy.readthedocs.io
---

# squidpy


## Summary

Spatial extension of scanpy for Visium / Xenium / MERFISH / CODEX. Builds spatial-neighbor graphs, computes neighborhood enrichment, co-occurrence at distance scales, Ripley's K, and Moran's I. Operates on AnnData with spatial coords in `.obsm['spatial']`.

Spatial extension of the scanpy / AnnData ecosystem. Built for Visium, Xenium, MERFISH, and related modalities.

## When to use

- Compute spatial-neighbor graphs from tissue coordinates
- Test for cell-type co-occurrence / spatial enrichment
- Ripley's K / pair-correlation analyses
- Spatial autocorrelation (Moran's I)
- Image-feature extraction (H&E adjacent to expression matrix)

## Key functions

- `sq.gr.spatial_neighbors(adata, coord_type='generic')` — build spatial kNN graph
- `sq.gr.nhood_enrichment(adata, cluster_key='leiden')` — neighborhood enrichment
- `sq.gr.co_occurrence(adata, cluster_key='cell_type')` — co-occurrence at distances
- `sq.gr.spatial_autocorr(adata, mode='moran')` — Moran's I per gene
- `sq.gr.ripley(adata, cluster_key='cell_type', mode='K')` — Ripley's K
- `sq.im.calculate_image_features(adata, img, features=['summary'])` — image features
- `sq.pl.spatial_scatter(adata, color='leiden')` — overlay clusters on tissue

## Use-case examples

1. **Visium niche detection:** `spatial_neighbors` → `nhood_enrichment` → cluster the enrichment matrix.
2. **CODEX cellular neighborhoods:** Schürch-style — kNN per cell, k-means on cell-type composition vectors. Squidpy's `nhood_enrichment` gives the building block.
3. **Cross-modality:** AnnData with `.obsm['spatial']` set; same object usable in scanpy.

## Notes for the LLM

- Spatial coordinates live in `adata.obsm['spatial']` (n × 2 array). Errors here cascade — verify shape first.
- `coord_type='generic'` for non-grid data (CODEX); `'grid'` for Visium hexagonal grid.
