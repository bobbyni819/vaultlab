---
name: scvi-tools
description: Probabilistic models for single-cell omics — scVI, scANVI, totalVI, multiVI. Variational inference + GPU.
domains: [single-cell, scrnaseq, batch-correction, integration, deep-learning]
install: pip install scvi-tools
docs_url: https://scvi-tools.org
---

# scvi-tools


## Summary

Probabilistic models for single-cell omics (scVI, scANVI, totalVI, multiVI). Trains on raw counts (do NOT log-transform); returns latent representations + batch-corrected expression + Bayesian DE. Use when Harmony's PCA-space correction isn't enough — particularly for cross-protocol or cross-species integration. GPU strongly recommended.

Generative models for single-cell data. Trains on counts, gives back latent representations, batch-corrected expression, and per-gene posterior distributions.

## When to use

- Integrating scRNA-seq across batches / donors / studies
- Imputation / denoising
- Cell-type label transfer (scANVI)
- Multi-modal integration (totalVI for CITE-seq, multiVI for ATAC + RNA)
- When Harmony's PCA-space correction isn't enough

## Key functions

- `scvi.model.SCVI.setup_anndata(adata, batch_key='batch')` — register
- `model = scvi.model.SCVI(adata)` — instantiate
- `model.train(max_epochs=400)` — train (GPU strongly recommended)
- `latent = model.get_latent_representation()` — n_obs × n_latent embedding
- `adata.obsm['X_scVI'] = latent` — use downstream as you would PCA
- `scvi.model.SCANVI.from_scvi_model(model, labels_key='cell_type', unlabeled_category='Unknown')` — semi-supervised label transfer
- `model.differential_expression(group1='A', group2='B')` — Bayesian DE with effect-size posteriors

## Use-case examples

1. **Integrate two donors with different conditions:** train SCVI with `batch_key='donor'`; use the latent for clustering + UMAP.
2. **Label transfer from a reference:** train SCANVI with reference labels + unlabeled query; predict on query.
3. **Per-gene Bayesian DE:** `model.differential_expression(group1=..., group2=...)` returns posterior probability of differential expression.

## Notes for the LLM

- scVI expects raw counts in `adata.X` — DO NOT log-transform first.
- GPU not strictly required but training time goes from minutes to hours on CPU for >50k cells.
- Latent space is ~10D by default; sufficient for clustering. Don't try to interpret individual scVI dimensions like PCs.
