# pseudobulk_volcano

Differential abundance volcano plot. X-axis = log2 fold change between two groups; Y-axis = -log10(p-value); points colored by significance (gray = non-significant, red = up-regulated, blue = down-regulated). Top-N most-significant features labeled by name.

## When to use

- Differential gene expression between treated vs untreated (pseudobulk RNA-seq)
- Differential lipid abundance between disease vs control (lipidomics)
- Differential protein abundance between regions (proteomics, multiplex IF)
- Any two-group comparison where you need to surface the most-shifted features

## Anchor papers

- **Pentimalli TM et al.,** *Cell Systems* 2025; 16:101261 (Fig 4) — primary layout source for the lipid/cell-type pseudobulk pattern
- **scanpy gallery** — `sc.tl.rank_genes_groups` standard volcano (https://scanpy.readthedocs.io/)
- **decoupler-py** docs — differential abundance volcano convention (https://decoupler-py.readthedocs.io/)

## Inputs

```python
df: pd.DataFrame with columns:
  - feature  (str)   — gene / protein / metabolite identifier
  - log2_fc  (float) — log2 fold change
  - pvalue   (float) — p-value or FDR-corrected q-value
```

## Variants

- Default thresholds (`log2fc_threshold=1.0`, `pvalue_threshold=0.05`) work for most RNA-seq + lipidomics
- For high-noise data, raise `log2fc_threshold` to 2.0
- For protein-abundance with strong corrections already applied, lower `pvalue_threshold` to 0.01
- `top_n_label` controls labeling density — set to 0 to skip labels (when feature names are too long / overlap)

## Style notes

- Palette default is colorblind-safe (gray + Tableau red/blue). Avoid red-green.
- Threshold lines are dashed at 50% alpha — present for orientation, not as primary axis decoration.
- Non-significant points are rasterized in vector exports to keep file size down (volcanoes can have 10k+ points).

## Cross-references

- `vaultlab.figures.recipes.stat_test_panel` — when comparing N>2 groups instead of pairwise
- `vaultlab.figures.recipes.heatmap` — when the comparison is across many groups simultaneously
- `vaultlab/data/journal_guidelines/cell.yaml` — cell-family figure rules applied at save time
