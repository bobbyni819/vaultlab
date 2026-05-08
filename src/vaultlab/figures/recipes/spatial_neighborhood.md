# spatial_neighborhood

Spatial neighborhood enrichment heatmap. Square cell-type × cell-type matrix where color = z-score enrichment (positive = cells co-localize more than chance; negative = cells avoid each other). Significant cells marked with `*`.

## When to use

- Squidpy `sq.gr.nhood_enrichment` output (spatial co-occurrence z-scores)
- Schurch-style neighborhood templates from CODEX / multiplex IF
- "Do these cell types live together?" analyses for tissue architecture papers
- Niche-relationship z-score visualizations

## Anchor papers

- **Palla G et al.,** *Nature Methods* 2022; 19:171 (Squidpy — Fig 3 spatial neighborhood enrichment)
- **Schurch CM et al.,** *Cell* 2020; 182:1341 (Fig 4 — CCI spatial neighborhoods in colorectal cancer)
- **scverse/squidpy docs** — `sq.gr.nhood_enrichment` + `sq.pl.nhood_enrichment`

## Inputs

```python
z_matrix: np.ndarray (n_types, n_types) OR pd.DataFrame indexed by cell type
  — values are z-scores from neighborhood enrichment analysis
```

## Variants

- `cmap="RdBu_r"` (default) — diverging, intuitive (red = enriched, blue = avoidant)
- `cmap="seismic"` — alternative diverging
- `cluster_axes=True` — hierarchically cluster cell types so similar-co-occurring types group together (requires scipy)
- `diagonal_mask=True` (default) — mask self-co-occurrence (trivially positive)
- `significance_threshold=2.0` — z-score threshold for `*` markers (~95% CI)

## Style notes

- Vmin/vmax default to symmetric ±max(|z|) — keeps zero in the middle of the diverging colormap
- Colorbar label includes "(z-score)" to avoid ambiguity vs raw counts (cci_heatmap shows raw strength; this shows enrichment)
- White minor grid separates cells (Cell + Nature heatmap convention)

## Cross-references

- `vaultlab.figures.recipes.cci_heatmap` — for raw interaction strength (not z-scores)
- `vaultlab.figures.recipes.heatmap` — generic heatmap for non-square matrices
- `vaultlab.figures.recipes.spatial_map_overlay` — to visualize the actual spatial layout that produces these enrichments
- `vaultlab/data/journal_guidelines/_common.yaml` — palette + z-score axis labeling rules
