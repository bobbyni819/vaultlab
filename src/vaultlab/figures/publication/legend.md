---
module: vaultlab.figures.publication.legend
purpose: Standalone legend export + density-aware in-panel positioning
ported_from: CODEX_MALDIIMS/lipid_annotations/ims_xgboost/figures/fig_style.py
references:
  - figure-design-rules-learned.md §1 (legend overlay — Bobby's top complaint)
---

# Legend — positioning and standalone export

## What this provides

- `legend_position_for_density(x, y)` — Rule 1 quadrant-counting heuristic for in-panel legends
- `save_legend(handles, labels, out_path)` — standalone legend figure (PNG + PDF), useful when in-panel legends would obscure data

## When to use which

| Situation | Use |
|---|---|
| Sparse scatter / line plot with a clear empty quadrant | `legend_position_for_density()` → `ax.legend(loc=...)` |
| Dense scatter, no clear empty space | `save_legend(handles, labels, out_path)` and place externally |
| Multiple panels sharing a legend | `save_legend()` once; reference in figure assembly |
| Panel where legend MUST be inside | matplotlib `loc="best"` with smaller `fontsize` |

## Rule 1 (legend overlay)

From `figure-design-rules-learned.md` §1:

> Legend position depends on data density. For scatter plots, count points per
> quadrant and put the legend in the emptiest. For line plots, anchor on the
> left edge unless the line ends at the same x. For text annotations on a
> figure, pick the empty quadrant empirically.

`legend_position_for_density()` is the algorithmic encoding of this rule for scatter / cloud plots.

## Edge cases

- **All quadrants crowded** → returns the least-crowded quadrant, but the legend will still overlap. Prefer `save_legend()` in that case.
- **Empty data** → returns the first candidate (`"upper right"` by default).

## See also

- [`style.md`](style.md) — `LEGEND_SIZE` and font/spine constants
- [`save.md`](save.md) — multi-format figure save
- `vaultlab.figures.publication.color.PaletteRegistry` — for legend color consistency across figures
