# Recipe: multi_panel_composite

Composes N existing recipe outputs (or external figures) into an A-B-C-D
panel grid. The canonical Cell-paper main-figure layout.

## Primary anchor

Pentimalli & Rajewsky *Cell Systems* 2025 main figs (3-4 panel grids
per main figure). The 2×2 / 3×2 / 1×N layouts with panel-letter
annotations and shared colorbar / legend handling are the canonical
composition this recipe reproduces.

## Public-repo cross-references

- matplotlib `gridspec` + `subplot_mosaic`
- scverse multi-panel patterns (mudata + viz)
- `vaultlab.figures.collage` — already partially implements this; recipe wraps it

## Variants

- `2x2` (default) — 4 panels in a square. Most common Cell main-fig layout.
- `3x2` — 6 panels (3 wide, 2 tall) for 6-panel results.
- `1xN_row` — single-row strip (e.g., 4 panels in a row showing time series).
- `Nx1_col` — single-column stack.

## Status

🚧 **Stub — not implemented yet.** API documented; render() raises NotImplementedError.
Note: `vaultlab.figures.collage` already exists at the lower level; this recipe
will wrap it with publication-styling defaults + auto-panel-letter annotation.
