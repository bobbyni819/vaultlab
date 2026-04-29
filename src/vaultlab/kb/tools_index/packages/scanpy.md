---
name: scanpy
description: Single-cell analysis in Python — preprocessing, clustering, embeddings, visualization for AnnData-backed scRNA-seq data.
domains: [single-cell, scrnaseq, clustering, dimensionality-reduction]
install: pip install scanpy
docs_url: https://scanpy.readthedocs.io
---

# scanpy


## Summary

Single-cell RNA-seq analysis on AnnData objects: preprocessing (filter, normalize, HVG, scale), embeddings (PCA, UMAP, t-SNE), graph-based clustering (Leiden), differential expression, and standard QC plots. The default Python toolkit for scRNA-seq pipelines.

Canonical Python toolkit for single-cell RNA-seq analysis. Operates on AnnData objects.

## When to use

- scRNA-seq preprocessing (filtering, normalization, HVG selection)
- Clustering (Leiden / Louvain) + UMAP/t-SNE
- Marker-gene discovery + differential expression
- Standard QC plots (violin, scatter, heatmap)

## Key functions

- `sc.pp.filter_cells(adata, min_genes=200)` — cell-level QC
- `sc.pp.filter_genes(adata, min_cells=3)` — gene-level QC
- `sc.pp.normalize_total(adata, target_sum=1e4)` — total-count normalization
- `sc.pp.log1p(adata)` — log transform
- `sc.pp.highly_variable_genes(adata, n_top_genes=2000)` — HVG selection
- `sc.pp.scale(adata, max_value=10)` — zero-mean unit-variance scale
- `sc.tl.pca(adata, n_comps=50)` — PCA
- `sc.pp.neighbors(adata, n_neighbors=15)` — kNN graph
- `sc.tl.leiden(adata, resolution=0.5)` — Leiden clustering
- `sc.tl.umap(adata)` — UMAP embedding
- `sc.tl.rank_genes_groups(adata, groupby='leiden')` — DE per cluster
- `sc.pl.umap(adata, color='leiden')` — plot UMAP

## Use-case examples

1. **PBMC3k tutorial pipeline:** load 10x → QC → normalize → HVG → PCA → neighbors → Leiden → UMAP → marker genes.
2. **Cell-type annotation:** `sc.tl.rank_genes_groups()` then look up top markers in PanglaoDB / CellMarker.
3. **Integration with squidpy:** `sc.read()` an AnnData with spatial coords; squidpy then uses the same object.

## Notes for the LLM

- ALWAYS check `adata.shape` and `adata.obs.columns` before any operation — the analysis depends on which fields exist.
- The `inplace=True` default for most preprocessing functions modifies `adata`; not always desirable mid-pipeline.
- For QC, `sc.pp.calculate_qc_metrics()` is more comprehensive than ad-hoc filtering.
