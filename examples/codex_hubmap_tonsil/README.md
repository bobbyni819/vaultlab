# Example: HuBMAP tonsil CODEX (30-min flagship demo)

The flagship demonstration of vaultlab's wet-lab → manuscript pipeline on a public CODEX dataset.

> **Status:** scaffold. Real demo lands at v0.1.0.

## What this demonstrates

The full vaultlab differentiator:
1. **Multi-channel imaging ingest** — OME-TIFF, channel calibration, tile QC
2. **Cell segmentation** — Mesmer (default for multiplex IF)
3. **Marker normalization + clustering** — per-channel z-score + Leiden
4. **Hybrid LLM cell typing** — canonical lineage rules + KB-grounded LLM interpretation
5. **Spatial neighborhoods** — CN methodology (Schürch et al. 2020)
6. **Publication-quality spatial overlay figures** — `vaultlab.figures.recipes.spatial_overlay` with publication-tight layout
7. **Citation-verified Methods section draft** — auto-drafted, semantic citation audit, NotebookLM-style evidence
8. **12-slide journal-club deck** — `vaultlab.slides` flagship demo

## Running

```bash
cd vaultlab
vaultlab demo codex_hubmap_tonsil
```

Target runtime: **~30 minutes** (download + analysis).

## Dataset

Public CODEX dataset from HuBMAP (Human BioMolecular Atlas Program). Tonsil tissue with ~35-marker antibody panel. ~5 GB.

License: CC BY 4.0 (HuBMAP public data).

## Expected outputs

To be added at v0.1.0. Will include:
- Spatial overlay figure (CN visualization)
- Marker dotplot per cluster
- Tissue region segmentation
- Auto-drafted Methods section with verified `[N]` citations
- 12-slide journal-club deck with speaker notes

## Why this matters

This demo exercises the full end-to-end path: imaging data → cell segmentation → clustering → manuscript-bound figure + methods text + journal-club deck. PaperQA covers literature. scanpy covers clustering. FutureHouse skips the bench. vaultlab covers the whole loop with one set of slash commands and one knowledge base.

## Reference

If your CODEX panel differs, see:
- [`../../docs/architecture.md`](../../docs/architecture.md) for how recipes adapt to panel variation
- `vaultlab.data.codex.panel.suggest_clustering_params(panel)` for per-panel parameter recommendations

## Coming with v0.1.0

- Pre-rendered expected outputs in `expected_outputs/`
- A walkthrough notebook
- A retrospective comparison: how this would have differed in a manual workflow
