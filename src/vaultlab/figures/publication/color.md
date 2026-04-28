---
module: vaultlab.figures.publication.color
purpose: Colorblind-safe palettes + Rule 14 neutral-grey discipline
ported_from: CODEX_MALDIIMS/lipid_annotations/ims_xgboost/figures/fig_style.py
references:
  - figure-design-rules-learned.md §14 (color as information, not decoration)
  - Paul Tol qualitative palettes (sron.nl/~pault)
---

# Color — palettes and Rule 14 discipline

## What this provides

| Symbol | Purpose |
|---|---|
| `CB_PALETTE` | 9-color colorblind-safe qualitative palette (Paul Tol) |
| `EXT_PALETTE` | 24-color extended palette (CB_PALETTE + 15 more) |
| `NEUTRAL_GREY` | `#888888` — the Rule 14 default for categorical bars |
| `SIG_COLOR_UP` / `_DOWN` / `_NS` | Red / blue / grey for signed-effect coloring |
| `PaletteRegistry` | Project-wide registry for cross-figure consistency |
| `palette_for(n)` | Get a CB-safe palette of length `n` |
| `bar_fill(labels, sign=, palette=)` | Rule 14-compliant bar coloring |

## Rule 14 (the rule that earned this module's place)

> **Default to neutral grey when the row label already names the category. Opt
> in to color ONLY for sign (up/down/ns), cross-panel tracking, or secondary
> axis.**

This rule survived rounds 12-14 of the metabolism review (figure-design-rules-learned.md). It exists because matplotlib's default categorical color cycle paints rainbow bar plots that look LLM-generated and hide signal.

`bar_fill()` enforces this:
1. If `sign=...` is provided → color by sign (the only opt-in for emphasis)
2. Else if `palette=...` provided AND the label maps → use it (cross-figure tracking)
3. Else → NEUTRAL_GREY for everything (the disciplined default)

## When to use which palette

| Situation | Use |
|---|---|
| Categorical bars where row labels carry the category name | `NEUTRAL_GREY` (via `bar_fill()` default) |
| Up/down regulation, log-fold-change | `bar_fill(..., sign=values)` |
| Cell-type / cluster identity across multiple panels | `bar_fill(..., palette=registry["cell_types"])` |
| Heatmap categorical legend | `palette_for(n)` for ≤24 categories |
| >24 categories | Reconsider — group, or use a different visualization |

## PaletteRegistry pattern

For cross-figure consistency, register project-specific palettes once and look them up by name:

```python
from vaultlab.figures.publication import PaletteRegistry, bar_fill

reg = PaletteRegistry()
reg.register("cell_types", {
    "T cell": "#5A89A7",
    "B cell": "#8B008B",
    "Macrophage": "#C4AED0",
})

# In every figure:
colors = bar_fill(labels, palette=reg["cell_types"])
```

This solves the "Cluster 3 was blue in Fig 1 and red in Fig 4" problem at the project level.

## Project-specific palettes are NOT vaultlab code

CODEX_MALDIIMS-specific palettes (`LIPID_CLASS_COLORS`, `cell_type_colors`, `community_colors`) are project-specific and do NOT migrate into vaultlab. They live in the user's `<kb>/.vaultlab/palettes/<project>.json` (or as Python constants in their analysis scripts).

vaultlab provides the *machinery* (`PaletteRegistry`, `bar_fill`); each project provides its own *content*.

## See also

- [`style.md`](style.md) — figure size presets + axis styling
- [`legend.md`](legend.md) — density-aware legend positioning
- [`figure-design-rules-learned.md`](https://drive.google.com/your-link) §14 — the full Rule 14 discussion in the KB
