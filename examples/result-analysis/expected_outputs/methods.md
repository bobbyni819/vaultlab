# Methods (draft)

Result tables for result-analysis demo were summarized and visualized with `vaultlab.analysis.run_pipeline`. The pipeline consumes pre-computed tidy result tables (CSV / Parquet / TSV) and emits figure exports plus this draft methods paragraph; it does **not** re-run upstream analyses.

## Result tables

- `results.csv` — 50 rows × 5 columns (3 numeric, 2 categorical / non-numeric).

## Column-level statistics

From `results.csv`:

- `sample_id` — categorical (`object`), n=50, 50 unique values; top: `S001` (1), `S038` (1), `S028` (1).
- `group` — categorical (`object`), n=50, 3 unique values; top: `control` (17), `low_dose` (17), `high_dose` (16).
- `replicate` — numeric (`int64`), n=50, mean 8.84±4.86, range [1, 17].
- `gene_x_expression` — numeric (`float64`), n=50, mean 6.68±2.19, range [1.9, 11.3].
- `qc_score` — numeric (`float64`), n=50, mean 0.925±0.0405, range [0.85, 0.987].

## Figures

- `fig1_expression_by_group` — bar plot of `gene_x_expression` by `group` from `results.csv`, n=50 → `fig1_expression_by_group.png`.
- `fig2_expression_histogram` — histogram of `gene_x_expression` from `results.csv`, n=50 → `fig2_expression_histogram.png`.
- `fig3_qc_vs_expression` — scatter of `gene_x_expression` vs `qc_score` from `results.csv`, n=50 → `fig3_qc_vs_expression.png`.

## Interpretation note

The summaries above describe the structure of the supplied result tables and may indicate where downstream interpretation is warranted; they are consistent with the columns reported by the upstream analysis and do not constitute new statistical inference.
