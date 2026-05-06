# Recipe: marker_dot_plot

Per-cluster expression of N markers, rendered as a publication-tight dot plot
where dot size = fraction-of-cells expressing and dot color = mean expression.

## Primary anchor

Hickey JW, et al. *Front Immunol* 2021;12:727626 — "Spatial mapping of protein
composition and tissue organization: a primer for multiplexed antibody-based
imaging." The 47-marker × 25-cluster panel on Fig 4 is the canonical layout
this recipe reproduces.

## Public-repo cross-references

- `scanpy.pl.dotplot` — https://scanpy.readthedocs.io/en/stable/generated/scanpy.pl.dotplot.html
- `seaborn.scatterplot` with size/hue mapping — https://seaborn.pydata.org/generated/seaborn.scatterplot.html
- scverse `mudata` integration patterns

## Variants

- `portrait` (default) — markers on Y-axis, clusters on X-axis. Use when ≥10 clusters.
- `landscape` — markers on X-axis, clusters on Y-axis. Use when ≥10 markers.
- `with_dendrogram` — adds hierarchical clustering of markers (top) and clusters (right). Use when reader needs to see marker co-expression / cluster relatedness.

## Inputs

```python
render(
    df: pd.DataFrame,         # rows = (cluster, marker), columns = ['fraction_expressing', 'mean_expression']
    *,
    cluster_order: list[str] | None = None,
    marker_order: list[str] | None = None,
    variant: Literal["portrait", "landscape", "with_dendrogram"] = "portrait",
    palette: str = "viridis",
    output_path: Path | str,
) -> Path
```

`df` MUST have a MultiIndex (cluster, marker) and exactly two columns:
`fraction_expressing` (0-1) and `mean_expression` (any scale; will be z-score
normalized within marker if `normalize='z'`).

## Output

- `<output_path>.png` (300 DPI) + `<output_path>.pdf`
- `<output_path>.provenance.json` with input hash, palette, cluster/marker order, recipe version

## Two paper-published examples

1. Hickey 2021 Fig 4 — 47 markers × 25 immune clusters. Portrait variant. `viridis` palette. Dot-size scale 0-100% on legend.
2. Schurch 2020 Cell Fig 2C — 28 markers × 16 cellular neighbourhoods. Portrait variant. Custom diverging palette for high/low contrast.
3. Goltsev 2018 Cell Fig 4 — 51 markers × 12 follicular zones. Landscape variant.

## Auto-applied styling (from publication.color + publication.legend)

- Font: Helvetica/Arial fallback, 10pt for axis labels, 9pt for tick labels, 11pt for title
- Color: viridis_r (sequential) by default; user can override
- Dot size legend: bottom-right corner, white background, 1pt border
- Axes: spines top + right hidden; tick direction "out"; tick length 4pt

## Anti-patterns (recipe will warn if detected)

- More than 60 markers — illegible. Suggests user split into facets or use `with_dendrogram` to drop similar markers.
- More than 40 clusters — same.
- Non-comparable expression scales across markers — recipe defaults to z-score per marker; user can override.
