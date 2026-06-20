---
module: vaultlab.figures.publication.profile
purpose: Project-configurable style profiles layered over publication style/color helpers
---

# Profile — one config drives every figure

`profile.py` provides a project-level style configuration for publication figures. It keeps the existing locked style engine intact: `setup_rcparams()` still owns Matplotlib defaults, `PaletteRegistry` still owns named palettes, and `palette_for()` remains the colorblind-safe fallback. The profile layer only decides which journal target, font regime, semantic colors, entity palettes, and heatmap conventions to apply for a project.

Defaults reproduce the current Nature manuscript look: Nature double-column width, manuscript typography, neutral-grey/sign semantic colors, and `RdBu_r` heatmaps without gridlines or cell annotations.

## Font regimes

`FontRegime.MANUSCRIPT` is for paper panels, with compact base text and a small-font floor for dense panels. It preserves the existing publication constants for titles, labels, ticks, and legends.

`FontRegime.TALK` is for slides and live presentation figures. It raises the active base font to at least 20 pt so figures remain readable when projected.

## Entity palettes

Entity palettes are project-specific identity colors, for example `cell_type` or `neighborhood`. Declare them once on `StyleProfile.entity_palettes`, then call:

```python
from vaultlab.figures.publication import default_profile, resolve_entity_palette

profile = default_profile()
colors = resolve_entity_palette(profile, "cell_type", 4)
```

If an entity palette is declared, it is used first. If it is not declared, `resolve_entity_palette()` falls back to `palette_for(n)`, the existing colorblind-safe default. It never invents rainbow colors.

`apply_profile()` also registers declared entity palettes into a `PaletteRegistry` using deterministic index labels (`"0"`, `"1"`, ...), and registers semantic colors under `semantic_colors`.

## Semantic colors

The default semantic colors follow the existing publication color discipline:

- `neutral_grey` — neutral categorical marks
- `positive` — signed positive/up color
- `negative` — signed negative/down color
- `emphasis` — a single restrained emphasis color

Override these only when a project has a documented palette convention.

## Heatmap conventions

`heatmap_kwargs(profile)` returns the convention bundle recipes should spread into plotting calls:

```python
kwargs = heatmap_kwargs(profile)
```

By default, heatmaps use `RdBu_r`, no gridlines, no cell annotations, and `bicluster=True` as a routing flag for recipes that choose clustered heatmap backends.

## TOML loading

Profiles load from a `[figure_profile]` TOML table via the stdlib `tomllib` reader:

```toml
[figure_profile]
journal = "nature"
width_mm = 177.8
font_regime = "manuscript"
entity_palettes = { cell_type = ["#332288", "#88CCEE"] }
semantic_colors = { emphasis = "#332288" }
heatmap = { cmap = "RdBu_r", gridlines = false, annotate_cells = false }
```

Missing keys fall back to `StyleProfile()` defaults.
