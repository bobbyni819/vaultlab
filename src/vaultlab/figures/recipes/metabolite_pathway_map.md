# metabolite_pathway_map

Pathway diagram with metabolite abundance overlay. Each metabolite is a colored circle (color = abundance value, e.g., log2FC), arranged in a pathway layout (horizontal chain, vertical chain, circular, or user-supplied x/y), with optional directional arrows for pathway flow.

Falls back to a simplified node-arrow visualization when full KEGG-style diagrams aren't justified for the figure context. For dense biochemical maps with hundreds of nodes, delegate to `escher` directly and use this recipe only for the publication figure capturing the key sub-pathway.

## When to use

- Lipid metabolism pathway abundance overlays (sphingolipid → ceramide → SM cascade)
- Curated KEGG-pathway differential abundance
- Pentimalli-style lipid-class flow diagrams
- Treatment-vs-control pathway-level comparison

## Anchor papers

- **Pentimalli TM et al.,** *Cell Systems* 2025; 16:101261 — lipid pathway abundance overlay convention
- **decoupler-py** (Badia-i-Mompel et al., Bioinformatics Advances 2022) — pathway activity + visualization
- **MetaboAnalyst** (Pang et al., Nucleic Acids Res 2024) — pathway impact + abundance heatmaps
- **Escher** (King et al., PLOS Comp Bio 2015) — full KEGG-style metabolic maps (used when this recipe's simplified layout is insufficient)

## Inputs

```python
nodes: pd.DataFrame:
  - name        (str)   — metabolite name
  - abundance   (float) — abundance value (log2FC, mean abundance, etc.)
  - x, y        (float, optional) — explicit position; otherwise layout used

edges: list[tuple[str, str]] OR None
  - (source_name, target_name) for each pathway flow
```

## Variants

- `layout="horizontal_chain"` (default) — left-to-right; good for ≤10 metabolites in a linear cascade
- `layout="vertical_chain"` — top-to-bottom; same as horizontal but rotated
- `layout="circular"` — radial arrangement; better for >10 nodes or when no clear linear flow
- User-supplied `x`, `y` columns override layout entirely (use this for KEGG-faithful coordinates)
- `cmap="RdBu_r"` (default) — diverging, intuitive for log2FC
- `cmap="viridis"` — sequential, for non-diverging abundance values

## Style notes

- Default node radius is 0.18 axes-units; values inside the node when readable
- Arrows shrink to terminate just outside the node circle so they don't overlap text
- Color limits default to symmetric ±max(|abundance|) — keeps zero in the middle of diverging colormaps
- For >20 metabolites, increase figsize via the layout (which scales with node range)

## Cross-references

- `vaultlab.figures.recipes.heatmap` — when comparing many metabolites × many conditions
- `vaultlab.figures.recipes.pseudobulk_volcano` — when surfacing the most-shifted metabolites overall (precedes pathway visualization)
- `vaultlab.figures.recipes.stat_test_panel` — when comparing a single metabolite across groups
- `vaultlab/data/journal_guidelines/_common.yaml` — palette accessibility (avoid rainbow even for pathway maps)
