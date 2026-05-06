# Recipe: heatmap

Two-axis matrix visualization with color encoding. Three primary
specializations: cell-by-feature expression, cluster-by-marker mean
expression, and cell-cell co-occurrence (cellular-neighbourhood matrix).

## Primary anchor

Schurch CM, et al. *Cell* 2020;182:1341 — Fig 5 (cellular-neighbourhood
co-occurrence matrix). The diverging-palette + permutation-test-z-score
encoding is the canonical layout this recipe reproduces.

Pentimalli & Rajewsky *Cell Systems* 2025 Fig 4B (niche × ligand
spatial-activity heatmap) is the second canonical layout for the
sequential-palette variant.

## Public-repo cross-references

- `scanpy.pl.matrixplot` — https://scanpy.readthedocs.io/en/stable/generated/scanpy.pl.matrixplot.html
- `seaborn.heatmap` + `seaborn.clustermap` — https://seaborn.pydata.org/generated/seaborn.heatmap.html
- bioconductor `ComplexHeatmap` — gold standard for clustered heatmaps; this recipe ports the layout philosophy

## Variants

- `cell_by_feature` (default) — rows = cells (or cell groups), columns = features. Values = expression / score / count.
- `cluster_by_marker` — rows = clusters, columns = markers. Values = mean expression. Z-score per marker by default.
- `co_occurrence` — symmetric matrix (rows = columns = cell types). Values = log2 fold-change vs permutation null. **Diverging palette by default** (red = enriched, blue = depleted, white = chance).

## Inputs

```python
render(
    df: pd.DataFrame,         # square or rectangular numerical matrix
    *,
    variant: Literal["cell_by_feature", "cluster_by_marker", "co_occurrence"] = "cluster_by_marker",
    palette: str | None = None,  # auto-pick: viridis (sequential), RdBu_r (diverging)
    row_order: list[str] | None = None,
    col_order: list[str] | None = None,
    cluster_rows: bool = False,
    cluster_cols: bool = False,
    significance_mask: pd.DataFrame | None = None,  # optional p-value mask (overlays asterisks where significant)
    output_path: Path | str,
    title: str = "",
) -> Path
```

## Output

- `<output_path>.png` (300 DPI) + `<output_path>.pdf`
- `<output_path>.provenance.json` with input hash, palette, ordering, recipe version

## Three paper-published examples

1. Schurch 2020 Fig 5 — co_occurrence variant, RdBu_r diverging palette, white at zero, asterisks for permutation-significant pairs.
2. Pentimalli 2025 Fig 4B — cluster_by_marker variant, viridis palette, z-score normalization, hierarchical row clustering (CCL19, CXCL9, etc).
3. Hickey 2021 Fig 4 supplementary — cluster_by_marker variant, sequential palette, no clustering, alphabetical marker order.

## Auto-applied styling

- Palette default by variant: `viridis` for sequential, `RdBu_r` for `co_occurrence`
- Cell border: 0.3pt white edge between cells (separates them visually without overwhelming)
- Colorbar: right side, fraction=0.025, label = scale type
- Significance overlay: `*` (p<0.05), `**` (p<0.01), `***` (p<0.001) — placed in cell center
- Diverging palette: zero centered on white explicitly (vmin=-vmax)

## Anti-patterns (recipe will warn if detected)

- More than 80 rows or columns — illegible at typical figure size. Suggests sub-setting or hierarchical clustering with cuttree.
- Mixed sign data with sequential palette — recipe auto-switches to diverging.
- Co-occurrence variant with non-symmetric matrix — error.
