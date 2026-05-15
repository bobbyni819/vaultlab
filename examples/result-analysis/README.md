# Result Analysis

**What this does:** Take a tidy CSV of analysis results (50 rows ×
5 columns of synthetic gene-expression-by-treatment-group data) and run
`vaultlab.analysis.run_pipeline` to produce three figures, a draft
Methods paragraph, and full provenance receipts — no LLM call required.

**Primitives composed:**

- `vaultlab.analysis.run_pipeline(project_dir, ...)` — top-level entry.
- `vaultlab.analysis.stats.summarize_dataframe(df)` — per-column dtype,
  n, n_missing, mean / std / min / max for numerics; unique count +
  top values for categoricals.
- `vaultlab.analysis.methods.compose_methods_paragraph(...)` —
  template-based methods text that cites every column with its sample
  size (per SPEC-A success criterion #3).
- `vaultlab.figures.contract.apply_rcparams()` — publication-grade
  matplotlib rcParams shared with the rest of vaultlab's figure
  pipeline.
- `vaultlab.provenance.write_receipts(...)` — emits
  `<output>.provenance.json` + `<output>.method.md` per AGENTS.md
  Red Line #2.

**Scope discipline:** `vaultlab.analysis` is the layer **above** your
analysis. It consumes pre-computed tidy results (CSV / Parquet / TSV)
and produces figures, methods text, and audit. It does not fit models,
run statistical tests, or read raw data — that all lives in your
project's analysis code. The pipeline rejects raw-data formats
(`.fastq`, `.bam`, `.h5ad`, `.nd2`, `.czi`, `.mzml`, `.fcs`, etc.) at
the door with a `ValueError`.

**Run:**

```bash
python run.py
```

**Outputs land in:** `./out/` (created on first run; not committed).

`./out/` contains:

- `fig1_expression_by_group.png` — bar plot of mean gene-X expression
  per treatment group (control / low_dose / high_dose).
- `fig2_expression_histogram.png` — histogram of gene-X expression
  across all 50 samples.
- `fig3_qc_vs_expression.png` — scatter of QC score vs gene-X
  expression.
- `methods.md` — drafted Methods paragraph (column-by-column
  description; figure references; hedged closing per the AGENTS.md
  "hedged voice" quality bar).
- `stats_summary.json` — per-column dict (dtype / n / mean / std /
  min / max for numerics; unique_count + top_values for categoricals).
- Per-artifact `<file>.provenance.json` + `<file>.method.md` sidecars.
- `.vaultlab-provenance.jsonl` — append-only audit index.

**Inputs:** synthetic — see [`inputs/results.csv`](inputs/results.csv).

Columns:

| Column | Type | Description |
| --- | --- | --- |
| `sample_id` | string | Synthetic sample ID `S001`–`S050`. |
| `group` | categorical | `control` / `low_dose` / `high_dose`. |
| `replicate` | int | Replicate index within group. |
| `gene_x_expression` | float | Log2 expression of "gene X". Means vary by group; 50 rows. |
| `qc_score` | float | Synthetic per-sample QC score in [0.85, 0.99]. |

**Config:** [`vaultlab-analysis.json`](vaultlab-analysis.json) — names
the three figures and the columns they cite.

**Adapt this:**

- Swap `inputs/results.csv` for your own tidy results table (CSV /
  Parquet / TSV).
- Edit `vaultlab-analysis.json` to point at your columns. Figure kinds
  supported in this iteration: `bar`, `scatter`, `histogram`, `line`.
- Pair the resulting `methods.md` with
  `vaultlab.manuscript.polish` for an LLM-driven polish pass, or with
  `vaultlab.citations.audit_file` to verify any citations you add.
- For multi-panel composites and journal-specific recipes, see
  `vaultlab.figures.recipes`.

**Reference output:** see `expected_outputs/` — fixed sample of what
`run.py` produces with the bundled inputs.
