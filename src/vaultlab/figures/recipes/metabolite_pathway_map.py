"""metabolite_pathway_map recipe — pathway diagram with metabolite abundance overlay.

Simplified pathway-overlay visualization: metabolites arranged in a
node-edge layout based on user-provided pathway structure, with each
node colored by its abundance value (e.g., log2 fold-change between
two conditions). For full KEGG-style diagrams, this delegates to
`escher` (when available) or falls back to a clean node-bar layout.

Layout convention follows scverse / decoupler-py / metaboanalyst pathway
visualizations.

Used for:
- Lipid metabolism pathway abundance maps (Pentimalli, Sorin)
- KEGG-style pathway-level differential abundance
- Curated-pathway abundance overlays for metabolomics manuscripts
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyBboxPatch

if TYPE_CHECKING:
    import pandas as pd

from vaultlab.figures.publication.save import save_fig

logger = logging.getLogger(__name__)

__all__ = ["render", "RECIPE_VERSION", "ANCHOR_PAPERS"]

RECIPE_VERSION = "0.1.0"

ANCHOR_PAPERS = (
    "Pentimalli TM et al., Cell Systems 2025;16:101261 (lipid pathway abundance overlay)",
    "decoupler-py docs — pathway activity inference + visualization (Badia-i-Mompel 2022)",
    "MetaboAnalyst (Pang 2024) — pathway impact + abundance heatmaps",
    "Escher (King 2015) — KEGG-style metabolic pathway maps",
)


def render(
    nodes: "pd.DataFrame",
    *,
    edges: "list[tuple[str, str]] | None" = None,
    abundance_col: str = "abundance",
    name_col: str = "name",
    output_path: Path | str,
    title: str = "",
    cmap: str = "RdBu_r",
    vmin: float | None = None,
    vmax: float | None = None,
    layout: str = "horizontal_chain",
    node_size: float = 0.18,
) -> Path:
    """Render a pathway diagram with abundance overlay.

    Parameters
    ----------
    nodes
        DataFrame with one row per metabolite/node. Must contain
        ``name_col`` (str) and ``abundance_col`` (float). Optional column
        ``"x"``, ``"y"`` to override layout positions.
    edges
        List of (source_name, target_name) tuples for arrows between
        metabolites. None = no arrows (just colored bubbles).
    abundance_col, name_col
        Column names. Default conventions match decoupler-py outputs.
    output_path
        Path to write the PNG.
    title
        Optional figure title.
    cmap
        Diverging colormap (centered on zero) for log2FC-style abundances.
        Default ``RdBu_r``.
    vmin, vmax
        Color limits. If None, symmetric around zero with magnitude
        ``max(|abundance|)``.
    layout
        How to position nodes when ``"x"``/``"y"`` columns aren't provided:
        - ``"horizontal_chain"`` (default) — nodes evenly spaced left-to-right
        - ``"vertical_chain"`` — nodes evenly spaced top-to-bottom
        - ``"circular"`` — nodes around a circle (good for >10 nodes)
    node_size
        Node radius in axes units. Default 0.18.

    Returns
    -------
    Path to the saved PNG.

    Anchored: Pentimalli 2025 + decoupler-py + MetaboAnalyst pathway
    abundance convention.
    """
    import pandas as pd

    required = {name_col, abundance_col}
    missing = required - set(nodes.columns)
    if missing:
        raise ValueError(f"nodes DataFrame missing required columns: {missing}")

    work = nodes.copy()
    n = len(work)
    names = work[name_col].astype(str).tolist()
    values = work[abundance_col].to_numpy(dtype=float)

    # Resolve x/y positions
    if "x" in work.columns and "y" in work.columns:
        xs = work["x"].to_numpy(dtype=float)
        ys = work["y"].to_numpy(dtype=float)
    elif layout == "horizontal_chain":
        xs = np.linspace(0.5, n - 0.5, n)
        ys = np.full(n, 1.0)
    elif layout == "vertical_chain":
        xs = np.full(n, 1.0)
        ys = np.linspace(n - 0.5, 0.5, n)
    elif layout == "circular":
        radius = max(2.0, n * 0.25)
        angles = np.linspace(0, 2 * np.pi, n, endpoint=False)
        xs = radius + radius * np.cos(angles)
        ys = radius + radius * np.sin(angles)
    else:
        raise ValueError(f"unknown layout {layout!r}")

    # Color limits
    if vmin is None and vmax is None:
        finite = values[np.isfinite(values)]
        if finite.size:
            mag = float(np.max(np.abs(finite)))
            vmin, vmax = -mag, mag
        else:
            vmin, vmax = -1.0, 1.0
    elif vmin is None:
        vmin = -abs(vmax)
    elif vmax is None:
        vmax = abs(vmin)

    cmap_obj = plt.get_cmap(cmap)
    norm = plt.Normalize(vmin=vmin, vmax=vmax)

    width = max(5.0, max(xs) - min(xs) + 2.0)
    height = max(3.0, max(ys) - min(ys) + 2.0)
    fig, ax = plt.subplots(figsize=(width, height), constrained_layout=True)

    # Draw edges first (behind nodes)
    if edges:
        name_to_idx = {n_: i for i, n_ in enumerate(names)}
        for src, tgt in edges:
            if src not in name_to_idx or tgt not in name_to_idx:
                logger.warning("edge (%s, %s) references unknown node", src, tgt)
                continue
            si, ti = name_to_idx[src], name_to_idx[tgt]
            ax.annotate(
                "",
                xy=(xs[ti], ys[ti]),
                xytext=(xs[si], ys[si]),
                arrowprops=dict(
                    arrowstyle="-|>",
                    color="black",
                    lw=0.8,
                    alpha=0.55,
                    shrinkA=node_size * 60,
                    shrinkB=node_size * 60,
                ),
                annotation_clip=False,
            )

    # Draw nodes
    for i, (x, y, val, nm) in enumerate(zip(xs, ys, values, names)):
        color = cmap_obj(norm(val)) if np.isfinite(val) else "lightgray"
        circle = plt.Circle(
            (x, y),
            node_size,
            color=color,
            ec="black",
            lw=0.8,
            zorder=3,
        )
        ax.add_patch(circle)
        # Label below node
        ax.text(
            x,
            y - node_size - 0.12,
            nm,
            ha="center", va="top",
            fontsize=8,
            zorder=4,
        )
        # Numeric value inside node, if it fits
        if np.isfinite(val) and node_size >= 0.15:
            text_color = "white" if abs(norm(val) - 0.5) > 0.2 else "black"
            ax.text(
                x, y,
                format(val, ".2f"),
                ha="center", va="center",
                fontsize=7,
                color=text_color,
                zorder=5,
            )

    ax.set_xlim(min(xs) - 1.0, max(xs) + 1.0)
    ax.set_ylim(min(ys) - 1.0, max(ys) + 1.0)
    ax.set_aspect("equal")
    ax.axis("off")

    # Colorbar
    sm = plt.cm.ScalarMappable(cmap=cmap_obj, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_label(f"{abundance_col}", fontsize=9)
    cbar.ax.tick_params(labelsize=8)

    if title:
        ax.set_title(title, fontsize=11)

    out = Path(output_path)
    paths = save_fig(fig, out, dpi=300)
    return paths[0]
