---
title: vaultlab.analysis — result-analysis pipeline
type: skill
slug: analysis-pipeline
applies_to:
  - "tidy result tables: .csv, .parquet, .tsv"
rejects:
  - "raw data: .fastq, .bam, .h5ad, .nd2, .czi, .mzml, .fcs, etc."
---

# vaultlab.analysis — consume tidy results, produce figures + methods + audit

## When to use this

Use `vaultlab.analysis.run_pipeline` when you have a project directory
holding **pre-computed tidy result tables** (CSV / Parquet / TSV) and you
want vaultlab to produce:

1. A per-column statistical description of every input table.
2. A small number of figures driven by a JSON config (`bar`, `scatter`,
   `histogram`, `line` — anything fancier belongs in
   `vaultlab.figures.recipes`).
3. A draft Methods paragraph that cites each file, each column, and each
   figure with column-level sample sizes.
4. Provenance sidecars (`.provenance.json` + `.method.md`) per AGENTS.md
   Red Line #2 (Reproducibility receipts).

## Scope discipline — what this does NOT do

**vaultlab is the layer ABOVE analysis.** This pipeline never:

- Fits models (no scikit-learn / xgboost / pytorch training).
- Runs DE / cluster / dimensionality-reduction algorithms.
- Reads raw sequencing / microscopy / mass-spec / flow data.
- Computes hypothesis tests (no t-tests, ANOVAs, FDR correction).

If you find yourself wanting any of the above, the work belongs in your
project's analysis code. Run that code first, write its outputs as tidy
CSV / Parquet, then point `run_pipeline` at the directory.

The pipeline enforces this discipline at runtime: if it finds any file
with an extension in `RAW_DATA_EXTENSIONS` (`.fastq`, `.bam`, `.h5ad`,
`.nd2`, `.czi`, `.tif/.tiff`, `.mzml`, `.fcs`, etc.) in the project's
top-level, `inputs/`, or `data/` directory, it raises `ValueError` with
a message that names the offending files and points back here.

## Inputs

```
my-project/
  inputs/
    expression_per_donor.csv   # tidy: one row per (donor, gene, group)
    qc_metrics.parquet         # tidy: one row per cell
  vaultlab-analysis.json       # optional figures config
```

`vaultlab-analysis.json` schema (all fields under `figures` are passed
straight to the renderer):

```json
{
  "figures": {
    "fig1_expression_by_group": {
      "kind": "bar",
      "source": "expression_per_donor.csv",
      "x": "group",
      "y": "expression",
      "title": "Mean gene-X expression by treatment group"
    },
    "fig2_qc_n_genes": {
      "kind": "histogram",
      "source": "qc_metrics.parquet",
      "x": "n_genes_by_counts",
      "bins": 30
    }
  }
}
```

You can also pass `figures_config` programmatically as a dict.

## Outputs

```
my-project/out/
  fig1_expression_by_group.png
  fig1_expression_by_group.png.provenance.json
  fig1_expression_by_group.png.method.md
  fig2_qc_n_genes.png
  fig2_qc_n_genes.png.provenance.json
  fig2_qc_n_genes.png.method.md
  methods.md
  methods.md.provenance.json
  methods.md.method.md
  stats_summary.json
  .vaultlab-provenance.jsonl   # append-only audit index
```

## Quick reference

```python
from vaultlab.analysis import run_pipeline

result = run_pipeline(
    project_dir="my-project/",
    out_dir="my-project/out/",          # optional, defaults to <project>/out
    figures_config=None,                 # if None, reads vaultlab-analysis.json
    project_name="Tonsil CODEX cohort",  # appears in methods header
)

print(result.stats_summary)        # {filename: {col: {dtype, n, ...}}}
print(result.figures)              # list[Path]
print(result.methods_md)           # Path to methods.md
print(result.manifest_paths)       # provenance sidecars + index
```

## Composing with other vaultlab primitives

The pipeline is intentionally narrow. Pair it with:

- `vaultlab.citations.audit_file(result.methods_md)` — verify any citations
  that you (or a later LLM polish) added to the methods draft.
- `vaultlab.manuscript.polish` — run the polish rules over the methods
  text to fix common phrasing tics before submission.
- `vaultlab.slides.layouts.add_figure_slide` — drop one of `result.figures`
  into a deck.
- `vaultlab.figures.recipes.*` — for anything more complex than a single
  bar / scatter / histogram / line plot.
