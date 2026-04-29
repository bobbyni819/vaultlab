# Example: 10x mouse brain Visium (30-min spatial transcriptomics tutorial)

Demonstrates spatial transcriptomics analysis on a public 10x Genomics Visium dataset.

> **Status:** scaffold. Real demo lands at v0.1.0.

## What this demonstrates

- Visium data ingest (10x SpaceRanger output)
- Spatial QC + tissue mask extraction
- Joint clustering with spatial context (`squidpy`)
- Cellular neighborhoods detection (Schürch et al. 2020 CN methodology)
- Spatial overlay figures with `vaultlab.figures.recipes.spatial_overlay`
- LLM-aided spatial-pattern interpretation

## Running

```bash
cd vaultlab
vaultlab demo visium_brain
```

Target runtime: **~30 minutes** (download + analysis).

## Dataset

10x Genomics public Visium mouse brain coronal section. ~2700 spots, ~32k genes. ~1 GB.

## Expected outputs

To be added at v0.1.0.

## See also

- [`../pbmc3k`](../pbmc3k/) — 5-minute Hello World
- [`../codex_hubmap_tonsil`](../codex_hubmap_tonsil/) — flagship CODEX demo
- [`docs/architecture.md`](../../docs/architecture.md) — vaultlab architecture
