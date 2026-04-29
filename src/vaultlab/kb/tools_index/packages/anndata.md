---
name: anndata
description: Annotated data matrix — the canonical container for single-cell + spatial data in the scverse ecosystem.
domains: [single-cell, spatial, data-container]
install: pip install anndata
docs_url: https://anndata.readthedocs.io
---

# anndata


## Summary

The annotated data-matrix container that scanpy / squidpy / scvi-tools all share. Holds `.X` (cells × genes), `.obs` (cell-level annotations), `.var` (gene-level), `.obsm` (embeddings), `.layers` (alternative matrices). Read/write `.h5ad`. Slicing returns views — `.copy()` to materialize.

Matrix-with-annotations container. The substrate for scanpy, squidpy, scvi-tools, and most scverse-aligned analyses.

## When to use

- Load / save scRNA-seq + spatial datasets as `.h5ad`
- Subset by cells (`adata[mask, :]`) or genes (`adata[:, gene_list]`)
- Inspect what's in a file before running heavy pipelines

## Key fields

- `adata.X` — primary expression matrix (n_obs × n_vars)
- `adata.obs` — cell-level annotations (DataFrame, n_obs rows)
- `adata.var` — gene-level annotations (DataFrame, n_vars rows)
- `adata.obsm` — multi-column embeddings keyed by name (`'X_pca'`, `'spatial'`)
- `adata.varm` — gene-level multi-column annotations
- `adata.uns` — unstructured metadata (any dict)
- `adata.layers` — alternative matrices (e.g. raw counts vs normalized)

## Key functions

- `anndata.read_h5ad(path)` — load
- `adata.write_h5ad(path)` — save
- `anndata.concat([a1, a2], join='outer')` — concatenate datasets
- `adata.copy()` — necessary before destructive operations on a slice

## Notes for the LLM

- Slicing with bool masks returns a *view* — write operations may surprise you. `.copy()` to materialize.
- `adata.X` may be sparse (CSR) or dense — check `type(adata.X)` before numpy operations.
