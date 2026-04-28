# Example: 3k PBMCs scRNA-seq (5-minute Hello World)

The canonical "Hello World" for vaultlab. Demonstrates the full pipeline on the 3k PBMC dataset (the MNIST of scRNA-seq).

> **Status:** scaffold. Real demo lands at v0.1.0. For now this directory is a placeholder.

## What this demonstrates

- Data ingest (10x format → AnnData)
- QC + normalization + Leiden clustering
- LLM-aided cluster annotation (with hedged voice)
- Three publication-quality figures via `vaultlab.figures.recipes`
- A 5-slide journal-club deck with auto-generated speaker notes
- Auto-written KB summary note linking everything

## Running

```bash
cd vaultlab
vaultlab demo pbmc3k
```

Target runtime: **<2 minutes on a laptop**.

## Expected outputs

After running, you'll find:

```
Knowledge/demo/Output/figures/cluster_umap.png
Knowledge/demo/Output/figures/marker_dotplot.png
Knowledge/demo/Output/figures/cluster_composition.png
Knowledge/demo/Output/decks/pbmc3k_journal_club.pptx
Knowledge/demo/Wiki/Concepts/pbmc3k_analysis_summary.md
Knowledge/demo/.vaultlab/runs/<timestamp>/manifest.json
Knowledge/demo/.vaultlab/runs/<timestamp>/trace.jsonl
```

Sample expected figures will be in `expected_outputs/` (added at v0.1.0).

## Without an Anthropic API key

```bash
vaultlab demo pbmc3k --no-llm
```

Runs the full pipeline using canned annotations + captions. Useful for first impressions.

## What this does NOT demonstrate

- Spatial analysis (see [`../visium_brain`](../visium_brain/) and [`../codex_hubmap_tonsil`](../codex_hubmap_tonsil/))
- Manuscript drafting (see the architecture docs)
- Citation verification (see [`../codex_hubmap_tonsil`](../codex_hubmap_tonsil/))
