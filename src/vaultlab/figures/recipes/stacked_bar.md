# stacked_bar

Relative cell-type / lipid-class / niche frequency across cohort groups, displayed as proportional segments stacked to 100% within each group.

## When to use

- Cell-type frequency across patient groups (CODEX, multiplex IF)
- Lipid-class frequency across donor cohorts (MALDI IMS)
- Niche-composition comparison
- Treatment-response stratification

## Anchor papers

- **Hickey JW et al.,** *Nature Methods* 2021; 18:1265 (Fig 4) — primary layout source (immune cell-type frequencies across multiplex-IF cohorts)
- **Schurch CM et al.,** *Cell* 2020; 182:1341 (Fig 2) — CCI frequency comparisons across patient groups
- **scanpy gallery** — grouped abundance plot convention

## Inputs

```python
df: pd.DataFrame in long form:
  - group_col     (str)   — donor / cohort / treatment label
  - category_col  (str)   — cell_type / lipid_class / niche label
  - value_col     (float) — counts or abundances (optional;
                            if None, treats each row as 1)
```

## Variants

- `normalize_to_100=True` (default) — bars sum to 100% per group
- `normalize_to_100=False` — absolute counts (use when group sizes are themselves the message)
- `horizontal=True` — flip to horizontal layout when group names are long
- `legend_loc="bottom"` — place legend below for square aspect ratios

## Style notes

- Default palette is `tab20` (20 categorical hues; matplotlib default for many-category data). For >20 categories, group conceptually before plotting.
- Bar edges use white separators (0.4pt) to keep adjacent segments distinguishable.
- Y-axis (or x-axis if horizontal) clipped to [0, 100] when normalized — prevents floating bars when cohort missingness is uneven.

## Cross-references

- `vaultlab.figures.recipes.stat_test_panel` — for pairwise group comparisons of a single category
- `vaultlab.figures.recipes.heatmap` — for category × category co-occurrence (instead of category-per-group)
- `vaultlab.figures.recipes.cci_heatmap` — for cell-cell interaction frequencies
- `vaultlab/data/journal_guidelines/_common.yaml` — cross-journal palette/accessibility rules
