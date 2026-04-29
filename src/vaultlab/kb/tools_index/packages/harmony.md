---
name: harmony
description: Fast batch-correction in PCA space. The lightweight alternative to scVI for batch integration.
domains: [single-cell, batch-correction, integration]
install: pip install harmony-pytorch  (or: pip install harmonypy)
docs_url: https://github.com/slowkow/harmonypy
---

# Harmony

Korsunsky 2019 (Nat. Methods). Batch-correct in PCA space iteratively. Fast, deterministic, no GPU. For most batch problems, Harmony is "good enough" before reaching for scVI.

## When to use

- Multi-batch / multi-donor scRNA-seq integration
- When training time + GPU constraints make scVI impractical
- Quick first-pass to see if "batches integrate well in PCA space"

## Key functions

```python
import harmonypy as hm
adata.obsm['X_pca'] = sc.tl.pca(adata)  # need PCA first
ho = hm.run_harmony(adata.obsm['X_pca'], adata.obs, ['batch'])
adata.obsm['X_pca_harmony'] = ho.Z_corr.T
sc.pp.neighbors(adata, use_rep='X_pca_harmony')
```

## Use-case examples

1. **Two-batch integration:** PCA → harmony on batch column → neighbors on `X_pca_harmony` → Leiden + UMAP. 95% of typical batch problems.
2. **Multi-covariate correction:** pass a list of columns: `hm.run_harmony(pca, obs, ['batch', 'donor'])`.
3. **Compare to scVI:** run both, compare neighborhood structure (e.g. silhouette by batch label — lower = better integrated).

## Notes for the LLM

- `harmonypy` is the pure-Python implementation; `harmony-pytorch` is GPU-accelerated. Most users want `harmonypy`.
- Output `Z_corr` is `(n_pcs, n_cells)` — TRANSPOSE before assigning to `obsm`.
- Harmony preserves PCA-space structure; for very dissimilar datasets (cross-species, very different protocols), scVI does better.
