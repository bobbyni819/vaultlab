"""Generate the synthetic demo figures bundled with vaultlab.

The bundled PNGs in ``figures/`` are produced by running this script once
and committing the outputs so the demo command does NOT need matplotlib at
first run (matplotlib lives behind the optional ``figures`` extra).

Re-run with::

    python -m vaultlab.data.demo._generate_demo_figures

after editing the synthesis logic. Outputs deterministic-seeded PNGs.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

FIG_DIR = Path(__file__).parent / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

# Lab-aesthetic palette (matches vaultlab.slides.themes defaults loosely)
PALETTE = [
    "#2E5C8A",  # navy
    "#C76A5C",  # rust
    "#7AAE6D",  # sage
    "#D9B36C",  # ochre
    "#8C6BB1",  # plum
    "#56B4B5",  # teal
]


def _save(fig: plt.Figure, name: str) -> Path:
    out = FIG_DIR / name
    fig.savefig(out, dpi=110, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out


def figure_1_cell_neighborhoods() -> Path:
    """Figure 1 — synthetic 'spatial map of cell neighborhoods'.

    Six color-coded cell types scattered over a tissue rectangle with
    visible motif-like clusters. Mimics the visual flavor of a CODEX
    cellular-neighborhood plot without copying any source figure.
    """
    rng = np.random.default_rng(seed=42)
    fig, ax = plt.subplots(figsize=(6.4, 4.2))

    # Five "motif" centers; cells cluster around them
    centers = np.array(
        [
            [2.0, 2.5],
            [5.5, 2.0],
            [3.5, 4.5],
            [7.5, 4.5],
            [1.5, 5.5],
        ]
    )
    motif_palette = PALETTE
    for i, c in enumerate(centers):
        n = rng.integers(28, 55)
        x = rng.normal(c[0], 0.6, n)
        y = rng.normal(c[1], 0.55, n)
        ax.scatter(x, y, s=22, c=motif_palette[i % len(motif_palette)], alpha=0.85,
                   edgecolor="white", linewidth=0.3, label=f"Motif {i + 1}")

    # Scattered "uncommitted" cells
    n_bg = 60
    ax.scatter(
        rng.uniform(0, 9, n_bg),
        rng.uniform(0.5, 6.5, n_bg),
        s=14,
        c="#bcbcbc",
        alpha=0.45,
        edgecolor="white",
        linewidth=0.2,
        label="Uncommitted",
    )

    ax.set_xlim(0, 9)
    ax.set_ylim(0, 7)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_xlabel("x (tissue, mm)", fontsize=9)
    ax.set_ylabel("y (tissue, mm)", fontsize=9)
    ax.set_title(
        "Figure 1 — Synthetic cellular neighborhoods (demo)",
        fontsize=11,
        loc="left",
        pad=8,
    )
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(
        loc="upper right",
        fontsize=7,
        frameon=False,
        ncol=2,
        handletextpad=0.3,
        columnspacing=0.7,
    )

    return _save(fig, "fig1_neighborhoods.png")


def figure_2_motif_frequencies() -> Path:
    """Figure 2 — synthetic motif-frequency bar chart by tissue type.

    Side-by-side bars for two tissues (normal vs. tumor) across five
    motifs, illustrating the paper's claim that tumors selectively
    reweight pre-existing motifs.
    """
    rng = np.random.default_rng(seed=7)
    motifs = ["M1: T-rich", "M2: B-zone", "M3: Myeloid", "M4: Stromal", "M5: Vascular"]
    normal = np.array([0.22, 0.18, 0.20, 0.18, 0.22]) + rng.normal(0, 0.01, 5)
    tumor = np.array([0.10, 0.06, 0.34, 0.12, 0.38]) + rng.normal(0, 0.015, 5)
    # Normalize so each row sums to 1.0
    normal = normal / normal.sum()
    tumor = tumor / tumor.sum()

    x = np.arange(len(motifs))
    width = 0.36

    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    bars1 = ax.bar(x - width / 2, normal, width, label="Normal tissue", color=PALETTE[0])
    bars2 = ax.bar(x + width / 2, tumor, width, label="Tumor", color=PALETTE[1])

    for bars in (bars1, bars2):
        for b in bars:
            h = b.get_height()
            ax.text(
                b.get_x() + b.get_width() / 2,
                h + 0.005,
                f"{h:.2f}",
                ha="center",
                va="bottom",
                fontsize=7,
                color="#444",
            )

    ax.set_xticks(x)
    ax.set_xticklabels(motifs, fontsize=8, rotation=0)
    ax.set_ylabel("Motif frequency", fontsize=9)
    ax.set_ylim(0, max(normal.max(), tumor.max()) + 0.08)
    ax.set_title(
        "Figure 2 — Motif frequency rewires in tumor (demo)",
        fontsize=11,
        loc="left",
        pad=8,
    )
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(loc="upper left", fontsize=8, frameon=False)

    return _save(fig, "fig2_motif_frequencies.png")


def main() -> list[Path]:
    paths = [figure_1_cell_neighborhoods(), figure_2_motif_frequencies()]
    for p in paths:
        print(f"wrote {p} ({p.stat().st_size / 1024:.1f} KB)")
    return paths


if __name__ == "__main__":
    main()
