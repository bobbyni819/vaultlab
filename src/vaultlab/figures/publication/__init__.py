"""Publication-grade figure helpers for vaultlab.

Low-level building blocks used by recipes and slide layouts:

    style.py       - rcParams + figure size presets + style_ax()
    color.py       - colorblind-safe palettes + Rule 14 neutral-grey defaults
    legend.py      - standalone legend export + density-aware positioning
    save.py        - multi-format figure save (PNG + PDF + provenance sidecar)
    coverage.py    - CoverageManifest JSON sidecar + footer validation
    bundle.py      - contract -> exports -> audit -> coverage -> provenance bundle
    stamp.py       - parameter_stamp() for --K CLI convention (P0.3 helper)

Convention (per AGENTS.md):
    - Defaults are PUBLICATION-TIGHT (Nature/Cell standard): minimal whitespace,
      compact typography, dense panels. PRESENTATION_LOOSE override exists in
      vaultlab.figures.layout.
    - Color discipline (Rule 14): neutral grey is the default for bars when row
      labels already carry the category; opt in to color only for sign,
      cross-panel tracking, or secondary axis.
    - Every figure save writes a sibling .provenance.json (Q14.5).

Ported from CODEX_MALDIIMS/lipid_annotations/ims_xgboost/figures/fig_style.py
(P0.1 metabolism lift, file 06 in the architecture grill).
"""

from __future__ import annotations

from vaultlab.figures.publication.bundle import (
    PublicationBundleResult,
    render_with_contract,
    save_publication_figure,
)
from vaultlab.figures.publication.color import (
    CB_PALETTE,
    EXT_PALETTE,
    NEUTRAL_GREY,
    SIG_COLOR_DOWN,
    SIG_COLOR_NS,
    SIG_COLOR_UP,
    PaletteRegistry,
    bar_fill,
    palette_for,
)
from vaultlab.figures.publication.coverage import CoverageAuditResult, CoverageManifest
from vaultlab.figures.publication.legend import (
    legend_position_for_density,
    save_legend,
)
from vaultlab.figures.publication.profile import (
    FontRegime,
    StyleProfile,
    apply_profile,
    default_profile,
    heatmap_kwargs,
    resolve_entity_palette,
)
from vaultlab.figures.publication.save import save_fig
from vaultlab.figures.publication.style import (
    ANNOT_SIZE,
    FIG_1COL,
    FIG_2COL,
    FIG_BARH,
    FIG_HEATMAP,
    FIG_HEATMAP_WIDE,
    FIG_TALL,
    FIG_TRIPLE,
    FIG_UMAP,
    FIG_VOLCANO,
    FIG_WIDE,
    LABEL_SIZE,
    LEGEND_SIZE,
    LINE_WIDTH,
    SMALL_SIZE,
    SPINE_WIDTH,
    TICK_SIZE,
    TITLE_SIZE,
    FIG_1p5COL,
    setup_rcparams,
    style_ax,
)

__all__ = [
    "ANNOT_SIZE",
    # color
    "CB_PALETTE",
    "EXT_PALETTE",
    # style
    "FIG_1COL",
    "FIG_2COL",
    "FIG_BARH",
    "FIG_HEATMAP",
    "FIG_HEATMAP_WIDE",
    "FIG_TALL",
    "FIG_TRIPLE",
    "FIG_UMAP",
    "FIG_VOLCANO",
    "FIG_WIDE",
    "LABEL_SIZE",
    "LEGEND_SIZE",
    "LINE_WIDTH",
    "NEUTRAL_GREY",
    "SIG_COLOR_DOWN",
    "SIG_COLOR_NS",
    "SIG_COLOR_UP",
    "SMALL_SIZE",
    "SPINE_WIDTH",
    "TICK_SIZE",
    "TITLE_SIZE",
    "FIG_1p5COL",
    "FontRegime",
    "PaletteRegistry",
    # bundle
    "PublicationBundleResult",
    "StyleProfile",
    # coverage
    "CoverageAuditResult",
    "CoverageManifest",
    "apply_profile",
    "bar_fill",
    "default_profile",
    "heatmap_kwargs",
    "legend_position_for_density",
    "palette_for",
    "resolve_entity_palette",
    # save
    "render_with_contract",
    "save_fig",
    "save_publication_figure",
    # legend
    "save_legend",
    "setup_rcparams",
    "style_ax",
]
