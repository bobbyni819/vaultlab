---
name: figure-contract
description: >-
  Force a figure contract — core conclusion, evidence chain, archetype,
  backend, export targets — BEFORE writing matplotlib/ggplot2 code. Use
  whenever you're about to plot a publication-quality figure. Failing
  the contract is a rigor-audit issue, not a stylistic preference.
---

# Figure contract — discipline before plotting

Lifted and adapted from the upstream nature-figure skill (Yuan Yizhe, SJTU)
at `nature-skills/skills/nature-figure/`. The contract is the first move,
not the last QA pass.

## The 5 commitments

Before any `plt.subplot(...)` or `ggplot(...)`:

1. **Core conclusion** — one sentence the figure must defend. If you can't
   state it, you don't know what you're plotting.
2. **Evidence chain** — for each planned panel, write the unique piece of
   evidence it carries. Drop panels that don't pull their weight.
3. **Archetype** — pick one:
   * `quantitative_grid` — multi-panel grid, all data.
   * `schematic_led_composite` — schematic frames the argument; data
     panels support.
   * `image_plate_and_quant` — microscopy/volume on one side, quants on
     the other. Usually dark background.
   * `asymmetric_mixed_modality` — one hero + subordinate panels at
     differing weights.
4. **Backend** — `python` (matplotlib/seaborn) or `r` (ggplot2/patchwork).
   Once selected, no cross-rendering.
5. **Export contract** — `svg + pdf + tiff` by default. TIFF at 600 DPI.
   Width capped at 183mm (Nature double column).

## Color policy

Use `NMI_PASTEL` (low-saturation 8-color) for dense ML/NMI-style pages.
Reserve saturated green (`SIGNAL_GAIN`) and red (`SIGNAL_LOSS`) for
directional cues (gains, drops, regression direction) — never as default
categorical colors.

## Mandatory rcParams (Python)

```python
from vaultlab.figures.contract import apply_rcparams
apply_rcparams()  # sets the 8 mandatory params
```

Equivalent: `Arial` sans-serif, `svg.fonttype=none` (editable text),
`pdf.fonttype=42` (TrueType), 7pt body, no right/top spines, 0.8pt axes.

## Workflow

```python
from vaultlab.figures.contract import (
    FigureContract, FigureArchetype, validate_contract,
    apply_rcparams, triple_export,
)

# 1. Author the contract before plotting code.
contract = FigureContract(
    conclusion="Method X recovers ground-truth cell types in 5/6 tissues.",
    evidence_chain={
        "a": "UMAP of 60k cells colored by ground truth",
        "b": "UMAP colored by method X cluster id",
        "c": "ARI vs ground truth across tissues, bar plot",
        "d": "Per-cell-type sensitivity in the worst-performing tissue",
    },
    archetype=FigureArchetype.QUANTITATIVE_GRID,
    backend="python",
    width_mm=183, height_mm=120,
    stats_block="ARI computed on held-out 20% of cells; n=5000 per tissue.",
)

# 2. Validate. Soft warnings are advisory; hard errors raise.
warnings = validate_contract(contract)
for w in warnings:
    print(f"WARN: {w}")

# 3. Apply rcParams and plot.
apply_rcparams()
import matplotlib.pyplot as plt
fig, axs = plt.subplots(2, 2, figsize=(7.2, 4.7))
# ... plotting code ...

# 4. Triple-export.
triple_export(fig, "output/figs/figure_2", contract=contract)
# Writes: figure_2.svg, figure_2.pdf, figure_2.tiff (600 DPI)
```

## When to load

- Manuscript figures targeting Nature/Science/Cell/eLife/NeurIPS/ICLR.
- Any "publication-grade", "SCI figure", "Nature style", "submission
  figure", "main figure", or "Fig. N" request.
- When the user pastes existing plotting code and asks for journal polish.

## When NOT to load

- Plotly / Altair / Bokeh / interactive web plotting.
- Pure EDA with no publication target.
- 3D scientific visualization beyond matplotlib's reach.
- Illustrator / Figma-first composition where Python only renders panels.

## Single-plot vs multi-panel handling

Comp-bio PhDs and wet-lab researchers regularly submit single-plot figures
(one volcano, one UMAP, one bar chart). The previous panel-detection step
incorrectly tried to subdivide these — splitting axis labels and corner
legends into bogus "panels". Sub-goal 5.5 fixes this with a granular
predicate plus a layout-dispatch helper:

```python
from vaultlab.figures.understand.whitespace import detect_panels, is_single_plot
from vaultlab.figures.contract import suggest_figure_layout

# Predicate — True iff the figure has exactly one detected panel.
is_single_plot("path/to/volcano.png")  # True

# Bbox list — length 1 for single-plot figures, ≥2 for multi-panel.
detect_panels("path/to/4_panel_grid.png")  # [(x0, y0, x1, y1), ...]

# Layout dispatch — picks a slide-layout name for the deck planner.
suggest_figure_layout(
    "path/to/volcano.png",
    has_bullets=True,
    has_caption=False,
)  # "figure_with_bullets"
```

### Algorithm — recursive XY-cut on the whitespace mask

The detector projects the whitespace mask (the same edge-dilated mask used
by `find_marker_offset`) onto X and Y axes, finds contiguous "gutter" runs
where ≥99% of pixels are true whitespace for ≥3% of the corresponding
axis, then recurses into each segment. The whitespace mask already
excludes a 30-px edge-dilation zone around every glyph and axis line, so
corner legends do NOT carve out an interior gutter — only structural
splits between subplots survive.

Recursion depth is capped at 3 (so a 2×2 grid splits in one pass but we
don't keep slicing inside each cell forever).

### Layout dispatch routing

`suggest_figure_layout` composes the predicate with caller-supplied
context flags:

| Input | Returned layout |
| --- | --- |
| multi-panel image (any flags) | `"figure_with_panels"` (caller must NOT subdivide further; route to `add_figure_only_slide`) |
| single-plot, `has_bullets=True` | `"figure_with_bullets"` (`add_figure_slide` — figure left, bullets right) |
| single-plot, wide aspect ≥2.0, no bullets | `"figure_only"` (`add_figure_only_slide` — hero) |
| single-plot, `has_caption=True`, normal aspect | `"figure_with_side_caption"` |
| single-plot, bare | `"figure_only"` |

Single-plot figures are *never* classed as `figure_with_panels` — that's
the regression the sub-goal addresses.

## Related

- `vaultlab.figures.recipes` — 11 specific chart recipes (heatmap,
  volcano, UMAP overlay, …) that implement these rules.
- `vaultlab.figures.publication.{color, legend, save, stamp, style}` —
  publication helpers consumed by recipes.
- `vaultlab.figures.understand.whitespace` — panel detection + whitespace
  primitives (`detect_panels`, `is_single_plot`, `whitespace_mask`,
  `find_marker_offset`).
- nature-figure upstream skill — `nature-skills/skills/nature-figure/`.
