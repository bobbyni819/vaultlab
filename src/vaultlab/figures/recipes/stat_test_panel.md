# Recipe: stat_test_panel

Bar / box / violin plot with significance-bracket overlays. The canonical
Cell-paper-style "comparison across N groups" figure.

## Primary anchor

Sorin M, et al. *Nature* 2023;614:548 — 416-LUAD cohort cellular-neighbourhood
result panels. The bar-with-significance-bracket layout (per Fig 4) is the
canonical bar variant. Pentimalli 2025 Fig 5F (boxplot SHG by fibroblast state)
is the box variant anchor.

## Public-repo cross-references

- `seaborn.barplot` + `seaborn.boxplot` + `seaborn.violinplot`
- statannotations package (https://github.com/trevismd/statannotations) — for
  significance-bracket overlay rendering
- scanpy `sc.pl.violin` for marker-comparison panels

## Variants

- `bar_with_significance` (default) — N bars, significance brackets above
- `box_grouped` — boxplots grouped by category, optional stripplot overlay
- `violin_split` — violin per category, split-violin for two-condition compare

## Status

🚧 **Stub — not implemented yet.** API documented; render() raises NotImplementedError.
