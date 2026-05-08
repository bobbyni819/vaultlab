# cci_heatmap

Cell-cell interaction strength heatmap. Square matrix with cell types on both axes, color = interaction strength (or co-occurrence count), optional numeric annotations on each cell.

## When to use

- CellChat / CellPhoneDB output — receptor-ligand pair strength matrices
- Squidpy neighborhood enrichment matrices
- Co-occurrence matrices (which cell types appear together in spatial niches)
- Any directional or symmetric pairwise relationship between cell types

## Anchor papers

- **Jin S et al.,** *Nature Communications* 2021; 12:1088 (CellChat — Fig 2 standard layout)
- **Palla G et al.,** *Nature Methods* 2022; 19:171 (Squidpy — neighborhood enrichment heatmap)
- **scverse/squidpy** gallery — interaction matrix examples

## Inputs

```python
matrix: np.ndarray (n_types, n_types) OR pd.DataFrame indexed by cell type
```

## Variants

- `cmap="viridis"` (default) — perceptually uniform, colorblind-safe
- `cmap="rocket"` for warmer-tone interaction strengths
- `cmap="RdBu_r"` for diverging (when the matrix has both positive + negative; e.g., enrichment z-scores)
- `annotate_threshold=0.3` — only annotate strong interactions, hide weak ones (matrix legibility for >12×12)
- `diagonal_mask=True` — mask self-interactions when not meaningful (e.g., spatial neighborhood where same-type-clustering is trivial)

## Style notes

- Default annotation font is 7pt — works for matrices up to ~15×15. For larger matrices, set `annotate=False` and let the colorbar carry the information.
- Text color auto-flips between black/white based on cell value (50% threshold of color range) for legibility.
- White minor grid separates cells visually (matches Cell + Nature heatmap convention).

## Cross-references

- `vaultlab.figures.recipes.heatmap` — generic heatmap (for non-square matrices, e.g., gene × cluster)
- `vaultlab.figures.recipes.spatial_neighborhood` — when the input is a spatial proximity matrix specifically (uses different default colorbar and z-score handling)
- `vaultlab/data/journal_guidelines/_common.yaml` — palette accessibility rules (avoid rainbow/jet)
