---
module: vaultlab.figures.publication.style
purpose: Publication-tight rcParams, figure-size presets, and axis styling
ported_from: CODEX_MALDIIMS/lipid_annotations/ims_xgboost/figures/fig_style.py
---

# Style — publication-tight defaults

## What this provides

- `setup_rcparams()` — Arial fonts, embeddable PDF/PS text (fonttype 42), regular mathtext
- Figure size presets aligned to Nature column widths: `FIG_1COL`, `FIG_1p5COL`, `FIG_2COL`, `FIG_WIDE`, `FIG_TALL`, `FIG_HEATMAP`, `FIG_HEATMAP_WIDE`, `FIG_VOLCANO`, `FIG_UMAP`, `FIG_BARH`, `FIG_TRIPLE`
- Font size constants: `TITLE_SIZE` (14), `LABEL_SIZE` (12), `TICK_SIZE` (10), `LEGEND_SIZE` (10), `ANNOT_SIZE` (9), `SMALL_SIZE` (8), `HEATMAP_ANNOT_SIZE` (7)
- Line / spine width constants: `SPINE_WIDTH` (1.5), `LINE_WIDTH` (1.5), `BAR_EDGE_WIDTH` (0.8), `MARKER_SIZE` (20), `MARKER_EDGE_WIDTH` (0.5)
- `style_ax(ax, title, xlabel, ylabel, ...)` — bold publication styling applied in place to a matplotlib axis

## When to use

- ALL figure recipes call `setup_rcparams()` at import time (or inside `render()`)
- Recipes pick figure size from the presets rather than hardcoding (`figsize=FIG_1COL`)
- Recipes call `style_ax()` after plotting to apply consistent styling

## Layout density (publication-tight vs presentation-loose)

This module IS the **publication-tight** default. For presentation contexts (slides, posters, lab meetings), wrap with `vaultlab.figures.layout.PRESENTATION_LOOSE` overrides — same primitives, looser margins and larger fonts.

## Reference

The defaults follow the Nature Methods + Cell figure-style conventions:
- Arial font (or DejaVu Sans / Helvetica fallback) for journal compatibility
- `fonttype=42` so reviewers can edit text in submitted PDFs
- Bold axis labels (publication standard; Excel-default thin labels look amateur)
- Despined top + right (standard since the late 2000s)

## See also

- [`color.md`](color.md) — palettes (Rule 14 neutral-grey defaults)
- [`legend.md`](legend.md) — density-aware legend positioning
- [`save.md`](save.md) — multi-format save with provenance
- `vaultlab.figures.layout` — density presets (PUBLICATION_TIGHT vs PRESENTATION_LOOSE)

## Pending P0 work

This module is part of P0.1 (figure-helper lift). The next P0 items are tracked at:
- P0.2 — `coverage.py` — CoverageManifest dataclass (placeholder lands in commit 3)
- P0.3 — `/figure-audit` slash command (lands once P0.2 + CoverageAuditor role exist)
