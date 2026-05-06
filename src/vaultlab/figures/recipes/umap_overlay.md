# Recipe: umap_overlay

2D projection of N cells colored by cluster, marker, or metadata. The
canonical exploratory single-cell figure.

## Primary anchor

Pentimalli & Rajewsky *Cell Systems* 2025 Fig 1C — 340 644 cells × 18
cell types on a UMAP embedding. The cluster-color-encoded global UMAP
is the canonical layout this recipe reproduces.

## Public-repo cross-references

- `scanpy.pl.umap` — https://scanpy.readthedocs.io/en/stable/generated/scanpy.pl.umap.html
- squidpy spatial UMAP variants
- scverse multi-modal embedding patterns

## Variants

- `by_cluster` (default) — categorical cluster labels, distinct colors per cluster
- `by_marker` — continuous expression of one marker, sequential colormap
- `by_metadata_continuous` — continuous metadata (pseudotime, age, etc.)

## Status

🚧 **Stub — not implemented yet.** API documented; render() raises NotImplementedError.
Will implement after the 2 anchor recipes (marker_dot_plot, heatmap) settle.
