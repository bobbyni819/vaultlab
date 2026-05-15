# /goal: deferred-followups bundle — three small followups from prior agents

_Created: 2026-05-15_
_Working dir: `C:/Users/bobby/Downloads/vaultlab`_

## CONTEXT

A bundle of small followups left over from earlier sub-goal agent reports:

1. **4.2 (HTML consumers)** — the earlier slice agent (commit `6bd6dc6`) added four new HTML consumers (`weekly_status_html`, `state_dashboard_html`, `feature_flag_editor`, `approaches_compare_html`) but did NOT wire them into `vaultlab.report.dispatch.render_artifact_html` because another agent was modifying that file at the time.
2. **5.4 (slide self-review)** — the earlier 5.4 agent shipped the composite review pass but deferred a WCAG color-contrast check ("does any text shape fall below 4.5:1 against the slide background?").
3. **5.5 (single-plot edge cases)** — the earlier 5.5 agent noted "inset axes — reported as 1 panel; needs LLM-side awareness" as a known limitation.

## SUCCESS CRITERIA

1. `_detect_kind` / `render_artifact_html` route `WeeklyStatusReport`, `StateDashboard`, `FeatureFlagConfig`, and `ApproachesCompare` to their respective consumers. ✅
2. `vaultlab.slides.self_review` flags low-contrast text as `critical` (<3.0:1) or `warning` (3.0–4.5:1), with NO false positives on themed colors. ✅
3. `vaultlab.figures.understand.whitespace.classify_panel_layout` returns `"single_plot_with_inset"` for a single plot with corner inset_axes, and `"single_plot"` / `"multi_panel"` otherwise. ✅
4. Layout dispatch for inset figures STILL routes to single-plot layouts (never `figure_with_panels`). ✅
5. Test counts: dispatch +6 new tests, self_review +5 new tests, single_plot +9 new tests. ✅
6. Existing tests stay green (`tests/test_vaultlab_report` + `tests/test_vaultlab_slides` + `tests/test_vaultlab_figures` + `tests/test_vaultlab_invariants`). ✅

## PROGRESS

### Item 1 — dispatch wiring

- `src/vaultlab/report/dispatch.py`
  - Added 4 new `ArtifactKind` literals: `"weekly-status"`, `"state-dashboard"`, `"feature-flag-editor"`, `"approaches-compare"`.
  - `_detect_kind`: fast-path isinstance check for the new dataclasses (avoids guess-by-shape when callers pass real objects). Dict-shape detection uses unique field pairs:
    - WeeklyStatusReport → `week_label` + `tldr`
    - StateDashboard → `status_summary` + `module_map`
    - ApproachesCompare → `approaches` + `decision_rationale`
    - FeatureFlagConfig → `groups` + `title` − `slides` (so a deck plan with `title` + `slides` still routes to `deck-audit`)
  - `render_artifact_html`: four new branches construct the dataclass from a dict if needed, then call `build_<name>_html(dc)`. `**extra` is ignored for these consumers (their builders take their dataclass only — caller mutates the input to customize).
- `tests/test_vaultlab_report/test_dispatch.py` (+6 tests)
  - Round-trip via `write_artifact_html` for each of the 4 dataclasses.
  - Dict-shape detection test for `WeeklyStatusReport`.
  - Regression: deck plan with `title` + `slides` keys must NOT be classified as `feature-flag-editor`.

### Item 2 — WCAG color-contrast check

- `src/vaultlab/slides/self_review.py`
  - Added `_luminance`, `_contrast_ratio`, `_rgb_color_from_color_format`, `_resolve_shape_background_rgb`, `_check_color_contrast` helpers.
  - WCAG-correct relative-luminance formula (sRGB → linear → weighted sum).
  - Per text run, only flags when BOTH the run color and resolved background are concrete RGB. Theme/scheme colors, gradients, picture fills, and `MSO_FILL_TYPE.BACKGROUND` (inherit-from-slide) all skip silently. Default background = `#FFFFFF` when the shape's fill is inherited.
  - Thresholds: `<3.0:1` → `critical`, `3.0:1 ≤ ratio < 4.5:1` → `warning`. Reports the worst-offending ratio + the hex colors so the user knows what to change.
  - Wired into `_review_one_slide` alongside the existing audits.
- `tests/test_vaultlab_slides/test_self_review.py` (+5 tests)
  - `#DDDDDD on #FFFFFF` (ratio ≈ 1.6) → critical.
  - `#888888 on #FFFFFF` (ratio ≈ 3.5) → warning, NOT critical.
  - Black on white (ratio = 21) → silent.
  - Unset run color (theme inherited) → silent (no false positive).
  - WCAG formula sanity: black-on-white = 21.0 ± 0.01, same-color = 1.0, symmetric.

### Item 3 — inset-axes detection

- `src/vaultlab/figures/understand/whitespace.py`
  - Added `has_corner_inset(image)` — connected-component-based detection of a small rectangular frame in any of the four corner halves.
    - Binarize: `gray < 0.5`.
    - Label connected components, filter by bbox size (10–50% of each axis), bbox extent (≤0.20 — frames are mostly hollow), and full-bbox containment in one of the four outer-half quadrants.
    - Local import of `skimage.measure` (heavyweight).
  - Added `classify_panel_layout(image)` — composes XY-cut + `has_corner_inset`:
    - `len(detect_panels) ≥ 2` → `"multi_panel"`.
    - Else if `has_corner_inset` → `"single_plot_with_inset"`.
    - Else → `"single_plot"`.
  - `is_single_plot` is unchanged: inset-bearing figures STILL return `True` so the layout dispatcher routes to a single-plot layout (no subdivision).
- The heuristic was tuned against `mpl_toolkits.axes_grid1.inset_locator.inset_axes(width="30%", height="30%", loc=...)` fixtures at all four corners. The first attempt (corner-density ratio) registered too weak a signal because the main plot fills the entire canvas; the connected-component frame approach was robust.
- `tests/test_vaultlab_figures/test_single_plot.py` (+9 tests)
  - True for inset_axes at all four loc=`upper left|upper right|lower left|lower right`.
  - False for plain single plot.
  - False for in-axes corner legend (the legend's bbox is too far inboard to satisfy the strict corner test).
  - `classify_panel_layout` returns the three expected labels.
  - Regression: `is_single_plot` returns True for inset-bearing figures; `suggest_figure_layout` never returns `figure_with_panels` for an inset-bearing figure.

## DECISIONS

- **No `**extra` plumbing for new consumers.** The four new builders take a typed dataclass only; nothing forwards through to a second-level subcomponent. Keeping the dispatch branches minimal (no extra kwargs) avoids spurious `TypeError` if a caller passes hints. If a future consumer ever takes a kwarg, the branch already has the `**extra` variable in scope to plumb through.
- **Conservative contrast check.** The skip-on-theme behavior means we'll never accidentally flag a deck whose body color is themed but rendered correctly. False-negative > false-positive.
- **Inset detection uses skimage.measure.** Tried a faster corner-density ratio first; abandoned because the densest corner of a full-canvas plot is still ~1.1× the average. Connected-component analysis is the right tool here even if it's slightly heavier.
- **Default slide background = white.** Reading the actual slide background through python-pptx requires walking the theme XML and resolving inheritance — too brittle for a "no false positives" audit. `#FFFFFF` is the universal default for the lab template and matches what `python-pptx` produces with a blank layout.

## VERIFICATION

- `pytest tests/test_vaultlab_report/test_dispatch.py -q` → 19 passed (was 13).
- `pytest tests/test_vaultlab_slides/test_self_review.py -q` → 16 passed (was 11).
- `pytest tests/test_vaultlab_figures/test_single_plot.py -q` → 22 passed (was 13).
- `pytest tests/test_vaultlab_report/ tests/test_vaultlab_slides/ tests/test_vaultlab_figures/ -q` → 508 passed.
- `pytest tests/test_vaultlab_invariants/ -q` → 8 passed (unchanged).

## NOT DEFERRED FURTHER

All three items shipped cleanly with tests. Nothing is half-shipped.
