# Sub-goal 5.5 — Granular custom-figure handling for single-plot figures

## Status: SHIPPED

## What

`vaultlab.figures.contract` (and adjacent panel-detection code) previously
assumed every figure was multi-panel. When a user submitted a single-plot
figure (one volcano, one UMAP, one bar chart) the layout pipeline tried to
subdivide it — splitting axis labels and corner legends into bogus
"panels". Sub-goal 5.5 adds a granular predicate plus a layout-dispatch
helper so single-plot figures flow through their own slide layouts and
never get cut into phantom sub-panels.

### Persona context

Per the strategic spec's persona-driven defaults: comp-bio PhDs and
wet-lab researchers frequently submit single-plot figures (a volcano plot,
a UMAP, a single bar chart). The contract must handle these correctly
without forcing them into multi-panel templates.

## New surface

| Symbol | Module | Purpose |
| --- | --- | --- |
| `detect_panels(image, *, max_depth=3)` | `vaultlab.figures.understand.whitespace` | Returns list of panel bboxes via recursive XY-cut on the whitespace mask. Length 1 for single-plot figures. |
| `is_single_plot(image)` | `vaultlab.figures.understand.whitespace` | Convenience: `len(detect_panels(image)) == 1`. |
| `suggest_figure_layout(image_path, *, has_bullets, has_caption, wide_aspect_threshold=2.0)` | `vaultlab.figures.contract` | Layout dispatcher. Returns one of `"figure_only"`, `"figure_with_bullets"`, `"figure_with_side_caption"`, `"figure_with_panels"`. |

## Algorithm — recursive XY-cut

1. Compute the **whitespace mask** (reused from
   `vaultlab.figures.understand.whitespace.whitespace_mask`). The mask is
   HSV `V > 0.92 AND S < 0.08` minus a 30-px edge-dilation zone around every
   detected glyph or axis line. Corner legends therefore do NOT carve out
   an interior gutter — the legend glyphs anchor an edge-zone that prevents
   the projection from registering a clean cut.
2. **Project** the mask onto X (column means) and Y (row means).
3. **Find gutters** — contiguous runs where the projection ≥ 99% (true
   whitespace) for ≥ 3% of the corresponding axis. Outer-edge gutters that
   touch row 0 / last row / col 0 / last col are filtered out (they're
   figure padding, not interior splits).
4. **Split** the bbox at interior gutter positions; reject segments
   smaller than 12% of the corresponding axis (sliver text / padding).
5. **Recurse** into each segment, swapping the axis preference each time.
   Cap depth at 3 so a 2×2 grid splits fully in one pass but no figure
   loops on degenerate splits.

## Layout dispatch routing

`suggest_figure_layout` composes the structural predicate with
caller-supplied context flags:

| Input | Output | Slide-layout call |
| --- | --- | --- |
| multi-panel image (any flags) | `"figure_with_panels"` | Caller routes to `add_figure_only_slide` and MUST NOT subdivide further |
| single-plot, `has_bullets=True` | `"figure_with_bullets"` | `add_figure_slide` (figure left, bullets right) |
| single-plot, aspect ≥ 2.0, no bullets | `"figure_only"` | `add_figure_only_slide` (hero) |
| single-plot, `has_caption=True`, normal aspect | `"figure_with_side_caption"` | (no dedicated primitive yet — caller routes via `add_figure_slide` with caption-only treatment) |
| single-plot, bare | `"figure_only"` | `add_figure_only_slide` |

Single-plot figures are *never* classed as `figure_with_panels` — the
regression test `test_suggest_layout_never_subdivides_single_plot`
enforces this across every combination of `has_bullets` × `has_caption`.

## How the predicate composes with existing code

- `vaultlab.figures.understand.layout_checks._check_recipe_conformance`
  already attempts `from ... import detect_panels` — it was previously
  caught by a `try/except (ImportError, Exception)` and downgraded to a
  warn. The import now succeeds, so layout-audit check 9 (recipe
  conformance) now functions for real when callers supply
  `expected_panel_count`.
- Slide-layout dispatch in `vaultlab.slides.deck.compile_deck_plan` reads
  `slide_spec.get("layout", "default")` and routes to
  `add_figure_only_slide`, `add_figure_above_bullets_slide`, or the
  default `add_figure_slide`. Callers can now precompute the layout via
  `suggest_figure_layout(image_path, has_bullets=..., has_caption=...)`
  and pass the result as `slide_spec["layout"]`.

## Files

- `src/vaultlab/figures/understand/whitespace.py` — added `detect_panels`,
  `is_single_plot`, `_project_whitespace`, `_find_gutters`,
  `_split_by_gutters`, `_xy_cut`. `__all__` extended.
- `src/vaultlab/figures/contract.py` — added `suggest_figure_layout`.
  `__all__` extended.
- `src/vaultlab/figures/contract.md` — documented the single-plot vs
  multi-panel distinction and the dispatch table.
- `src/vaultlab/figures/understand/layout_checks.py` — removed stale
  `# type: ignore` on the `detect_panels` import (now resolves cleanly).
- `tests/test_vaultlab_figures/test_single_plot.py` — 13 unit tests
  covering predicate, panel-count, corner-legend edge case, layout
  dispatch, regression guard, and wide-aspect routing.

## Tests (13 new)

`pytest tests/test_vaultlab_figures/test_single_plot.py -q`:

1. `test_detect_panels_returns_one_bbox_for_single_plot` — single bar
   chart → 1 panel covering ≥30% of figure area.
2. `test_detect_panels_returns_multiple_bboxes_for_4_panel` — 2×2 grid → ≥ 2 panels.
3. `test_detect_panels_finds_two_panels_in_two_panel_figure` — 1×2 row → ≥ 2 panels.
4. `test_detect_panels_legend_corner_does_not_create_phantom_panel` —
   single chart with upper-right legend → exactly 1 panel.
5. `test_is_single_plot_true_for_single_bar_chart`
6. `test_is_single_plot_false_for_4_panel`
7. `test_is_single_plot_true_for_chart_with_corner_legend`
8. `test_suggest_layout_routes_single_plot_with_bullets_to_figure_with_bullets`
9. `test_suggest_layout_routes_single_plot_with_caption_to_side_caption`
10. `test_suggest_layout_routes_bare_single_plot_to_figure_only`
11. `test_suggest_layout_routes_multi_panel_to_figure_with_panels`
12. `test_suggest_layout_never_subdivides_single_plot` — regression
    guard across every combination of `has_bullets` × `has_caption`.
13. `test_suggest_layout_for_very_wide_single_plot_prefers_figure_only` —
    10×3 aspect → `"figure_only"` even if caption flag is set later.

Fixtures are generated on the fly with matplotlib into `tmp_path`; no
binary PNGs are committed.

## Edge cases that REMAIN un-handled (with reason)

- **Inset axes** — a parent plot with an in-corner inset (e.g. a UMAP
  with a kernel-density inset in the bottom-left) is reported as one
  panel. Reason: the inset shares its parent's axes whitespace; the
  gutter projection has no way to distinguish "inset" from "bg
  annotation". An LLM-based step (see `understand.understand_figure`)
  would be the right place to add inset awareness — out of scope for
  this sub-goal.
- **Letter labels (A/B/C/D)** — the predicate ignores them. Reason:
  the XY-cut whitespace projection is the load-bearing signal; if there
  are no gutters there are no panels regardless of glyph labels.
  Conversely, if there ARE gutters, the structural cue already commits
  the figure to multi-panel routing and OCR adds no information.
  Letter-glyph detection might be useful for *ordering* panels (the A→B
  reading order vs the bbox `(y0, x0)` reading order) but that's a
  different problem.
- **Schematic-led composites** (`SCHEMATIC_LED_COMPOSITE` archetype) —
  hand-drawn / Illustrator-style schematics often lack the clean
  white-gutters that the XY-cut needs. Such figures are typically routed
  via the archetype field on `FigureContract` rather than the
  image-only predicate; callers who know the archetype should bypass
  `suggest_figure_layout` and pick the layout directly.
- **Dark-background image plates** (`IMAGE_PLATE_AND_QUANT` archetype) —
  the whitespace mask requires `V > 0.92 AND S < 0.08`, which excludes
  black/very-dark backgrounds. Image-plate composites with dark
  microscopy backdrops will report 1 panel even when they contain
  multiple sub-plates. Same fix as above: caller selects layout from the
  archetype, not from pixel analysis. A dark-background extension
  (`V < 0.05` mask for "dark whitespace") is a future enhancement.

## Verify

```bash
cd C:/Users/bobby/Downloads/vaultlab
python -m pytest tests/test_vaultlab_figures/test_single_plot.py -q
# 13 passed

python -m pytest tests/test_vaultlab_invariants/ -q
# 8 passed
```
