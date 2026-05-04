"""v2 figure-understanding prototype — uses vaultlab.figures.understand.

Replaces my eye-estimated coordinates with programmatically-extracted
color-motif regions. For figure 1, I extract neon-green / electric-blue /
orange / purple regions, run merge_regions to collapse fragments, then map
each merged region to a concept ("introduced TCR" = the largest neon-green
cluster in panel a, etc.).

Then renders the annotated overlay using render_annotated_figure and writes
a fresh PPTX with corrected figure 1.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make sure the local vaultlab is importable when run from the repo
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from vaultlab.figures.understand import (
    ColorMotif,
    ElementAnnotation,
    extract_regions,
    merge_regions,
)
from vaultlab.figures.understand.render import render_annotated_figure

INPUT = Path(r"C:\tmp\cart_figs_v13\image1.png")
OUT_DIR = Path(r"C:\tmp\cart_figs_v13_annotated_v2")
OUT_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Color motifs for figure 1 — calibrated by inspection of the actual figure
# ---------------------------------------------------------------------------

MOTIFS = [
    ColorMotif("introduced-tcr-green", (80, 140), 0.40, 0.40, 0.00003),
    ColorMotif("endogenous-tcr-blue", (195, 240), 0.30, 0.35, 0.00003),
    ColorMotif("cd3-orange", (15, 40), 0.45, 0.45, 0.00003),
    ColorMotif("mhc-tag-red", (340, 360), 0.35, 0.40, 0.00003),
    ColorMotif("mhc-body-purple", (260, 295), 0.18, 0.28, 0.00003),
]


def main() -> None:
    print(f"Processing {INPUT}")

    # Step 1: extract regions
    regions = extract_regions(INPUT, MOTIFS, opening_radius=2)
    print(f"\nExtracted {len(regions)} raw regions:")
    for motif_name in {r.motif_name for r in regions}:
        count = sum(1 for r in regions if r.motif_name == motif_name)
        print(f"  {motif_name}: {count} regions")

    # Step 2: merge fragments — BioRender outlines split each receptor into
    # multiple connected components. Aggressive dilation merges them.
    merged = merge_regions(regions, dilation_px=25)
    print(f"\nAfter merging (dilation=25): {len(merged)} regions")
    for motif_name in {r.motif_name for r in merged}:
        count = sum(1 for r in merged if r.motif_name == motif_name)
        print(f"  {motif_name}: {count} merged regions")

    # Step 3: pick the most relevant regions per panel — a, b, c
    # Image is 5513x3131. Panel a ~ x in [0, 1840]. Panel b ~ x in [1840, 3680].
    # Panel c ~ x in [3680, 5513]. (Approximate; verified by visual inspection.)
    img_width = 5513
    panel_a = lambda r: r.bbox_px[0] < img_width // 3
    panel_b = lambda r: img_width // 3 <= r.bbox_px[0] < 2 * img_width // 3
    panel_c = lambda r: r.bbox_px[0] >= 2 * img_width // 3

    def by_panel(motif: str, panel_filter):
        matches = [r for r in merged if r.motif_name == motif and panel_filter(r)]
        return matches

    # Pick concrete regions for each conceptual element
    annotations: list[ElementAnnotation] = []

    # PANEL A — TCR therapy
    a_blue = by_panel("endogenous-tcr-blue", panel_a)
    if a_blue:
        # Pick the LEFT-MOST blue region as endogenous TCR
        ann_target = min(a_blue, key=lambda r: r.bbox_px[0])
        annotations.append(
            ElementAnnotation(
                label="Endogenous TCR (panel a)",
                bbox_px=ann_target.bbox_px,
                motif_name="endogenous-tcr-blue",
                explanation=(
                    "Native αβ TCR (blue dimer) shown left-of-center in panel (a). "
                    "Competes with the introduced TCR for the same MHC-peptide complex."
                ),
                confidence=0.85,
            )
        )

    a_green = by_panel("introduced-tcr-green", panel_a)
    if a_green:
        # Pick the largest green region in panel a as the introduced TCR
        ann_target = max(a_green, key=lambda r: r.area_px)
        annotations.append(
            ElementAnnotation(
                label="Introduced TCR (panel a)",
                bbox_px=ann_target.bbox_px,
                motif_name="introduced-tcr-green",
                explanation=(
                    "Engineered TCR (green dimer). The therapeutic receptor in TCR therapy."
                ),
                confidence=0.90,
            )
        )

    a_purple = by_panel("mhc-body-purple", panel_a)
    if a_purple:
        # MHC class I — the largest purple region in panel a (sits above introduced TCR)
        ann_target = max(a_purple, key=lambda r: r.area_px)
        annotations.append(
            ElementAnnotation(
                label="MHC Class I + peptide (panel a)",
                bbox_px=ann_target.bbox_px,
                motif_name="mhc-body-purple",
                explanation=(
                    "MHC class I (purple block) presenting tumor peptide. "
                    "Sits directly on top of the introduced TCR in the figure."
                ),
                confidence=0.80,
            )
        )

    a_orange = by_panel("cd3-orange", panel_a)
    if a_orange:
        # CD3 chains — pick the union of orange regions in panel a (or just the largest)
        ann_target = max(a_orange, key=lambda r: r.area_px)
        annotations.append(
            ElementAnnotation(
                label="CD3 chains (panel a)",
                bbox_px=ann_target.bbox_px,
                motif_name="cd3-orange",
                explanation=(
                    "CD3 ε/γ/δ subunits (orange) — signal-transduction chains for "
                    "both endogenous + introduced TCR."
                ),
                confidence=0.80,
            )
        )

    # PANEL B — TAA therapy
    b_red = by_panel("mhc-tag-red", panel_b)
    if b_red:
        ann_target = max(b_red, key=lambda r: r.area_px)
        annotations.append(
            ElementAnnotation(
                label="TAA presented (panel b)",
                bbox_px=ann_target.bbox_px,
                motif_name="mhc-tag-red",
                explanation=(
                    "Tumor-associated antigen (red bar — aberrantly expressed protein) "
                    "presented via MHC class I to the endogenous TCR."
                ),
                confidence=0.75,
            )
        )

    b_blue = by_panel("endogenous-tcr-blue", panel_b)
    if b_blue:
        ann_target = max(b_blue, key=lambda r: r.area_px)
        annotations.append(
            ElementAnnotation(
                label="Endogenous TCR (panel b)",
                bbox_px=ann_target.bbox_px,
                motif_name="endogenous-tcr-blue",
                explanation=(
                    "In TAA therapy the endogenous TCR is the active receptor — "
                    "no exogenous construct, but antigen must be MHC-presentable."
                ),
                confidence=0.85,
            )
        )

    # PANEL C — CAR T
    c_blue = by_panel("endogenous-tcr-blue", panel_c)
    if c_blue:
        # The scFv has light-blue accents — pick a tall narrow blue region (the scFv)
        ann_target = max(c_blue, key=lambda r: r.area_px)
        annotations.append(
            ElementAnnotation(
                label="scFv (panel c, antigen recognition)",
                bbox_px=ann_target.bbox_px,
                motif_name="endogenous-tcr-blue",
                explanation=(
                    "Single-chain variable fragment — the antigen recognition domain of "
                    "the CAR. Binds surface antigen directly, MHC-independent."
                ),
                confidence=0.65,
            )
        )

    c_green = by_panel("introduced-tcr-green", panel_c)
    if c_green:
        # Find the LOWEST green region (intracellular signaling)
        ann_target = max(c_green, key=lambda r: r.bbox_px[1])  # largest y0 = lowest
        annotations.append(
            ElementAnnotation(
                label="Co-stim domain (panel c, intracellular)",
                bbox_px=ann_target.bbox_px,
                motif_name="introduced-tcr-green",
                explanation=(
                    "Co-stimulatory domain (CD28 / 4-1BB) — green portion of the "
                    "intracellular signaling cassette."
                ),
                confidence=0.70,
            )
        )

    c_orange = by_panel("cd3-orange", panel_c)
    if c_orange:
        ann_target = max(c_orange, key=lambda r: r.bbox_px[1])  # lowest = activation
        annotations.append(
            ElementAnnotation(
                label="CD3-ζ activation domain (panel c)",
                bbox_px=ann_target.bbox_px,
                motif_name="cd3-orange",
                explanation=(
                    "CD3-ζ-style activation domain (orange) — bottom of the CAR's "
                    "intracellular signaling stack. ITAM-bearing."
                ),
                confidence=0.70,
            )
        )

    print(f"\nGenerated {len(annotations)} concept annotations")
    for a in annotations:
        print(f"  [{a.confidence:.2f}] {a.label:<40s} bbox={a.bbox_px}")

    # Step 4: render annotated overlay
    out_png = OUT_DIR / "figure1_v2.png"
    render_annotated_figure(INPUT, annotations, out_png)
    print(f"\nAnnotated PNG -> {out_png}")

    # Also render a debug overlay showing every merged region (for tuning)
    from vaultlab.figures.understand import render_debug_overlay

    debug_png = OUT_DIR / "figure1_v2_debug.png"
    render_debug_overlay(INPUT, merged, debug_png)
    print(f"Debug overlay -> {debug_png}")


if __name__ == "__main__":
    main()
