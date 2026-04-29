"""Re-do image10 (TME suppressive mechanisms) with proper semantic reading.

Bobby's 2026-04-29 v3 review pointed out that for complex figures (image10,
image8, image13) my matchers picked wrong regions because they used generic
heuristics ("largest pink blob = tumor") rather than actually understanding
the figure.

This script re-does image10 with MANUALLY-AUTHORED bounding boxes derived
from actual semantic reading of the figure - the rigor protocol Bobby asked
for. These are not extracted; they are direct measurements based on what's
in the image.

Image10 is 2035x1676 pixels. The figure has these labeled callout circles:

  1. Suppressive cells (large top-center circle: MDSCs/Treg/TAM around CAR T)
  2. PD-1/PDL-1 + CTLA-4/CD86 (left circle: Cancer cell + DC interaction)
  3. Soluble inhibitors (top-right: IL-10, TGF-beta, chemokines)
  4. Tumor antigen heterogeneity (right circle)
  5. Central metabolic suppression (O2/pH/nutrients DOWN, toxic metabolites UP)
  6. Dysregulated vasculature (bottom-left circle: VCAM-1/ICAM-1 down)
  7. Physical barriers (bottom-right: ECM, CAF, IFP)
  8. Tumor mass (the central pink-cellular blob, NOT the vessel)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from vaultlab.figures.understand import ElementAnnotation
from vaultlab.figures.understand.render import render_annotated_figure_v3

INPUT = Path(r"C:\tmp\cart_figs_v13\image10.png")
OUT = Path(r"C:\tmp\cart_figs_v13_annotated_v3\v3_image10_FIXED.png")


# Manual bboxes from semantic reading of image10 (2035x1676).
# Each captures the labeled callout circle in the figure, with a small pad
# around the content so the box is visually centered on the labeled region.
ANNOTATIONS: list[ElementAnnotation] = [
    ElementAnnotation(
        label="Suppressive cells (MDSC, Treg, TAM around CAR T)",
        bbox_px=(420, 0, 1380, 510),
        motif_name="suppressive-cells",
        explanation=(
            "Top-center circle. Shows CAR T at the center being suppressed by "
            "MDSCs (yellow), Tregs, and TAMs (both purple) via inhibitory ligands. "
            "Tregs further secrete chemokines that recruit more suppressors."
        ),
        confidence=0.95,
    ),
    ElementAnnotation(
        label="PD-1/PDL-1 + CTLA-4/CD86 checkpoint detail",
        bbox_px=(20, 360, 720, 800),
        motif_name="checkpoint",
        explanation=(
            "Left circle. Shows Cancer cell + DC interaction with explicit "
            "checkpoint engagement: PD-1/PDL-1 and CTLA-4/CD86 - both "
            "therapeutic checkpoint targets."
        ),
        confidence=0.95,
    ),
    ElementAnnotation(
        label="Soluble inhibitors: IL-10, TGF-β",
        bbox_px=(1300, 60, 2030, 480),
        motif_name="soluble-inhibitors",
        explanation=(
            "Top-right callout. IL-10 and TGF-beta are immunosuppressive cytokines; "
            "Tregs secrete chemokines (green dots) that attract more suppressive "
            "cells. CAR T cells in this region receive inhibitory signaling."
        ),
        confidence=0.95,
    ),
    ElementAnnotation(
        label="Tumor antigen heterogeneity",
        bbox_px=(1330, 660, 2030, 1100),
        motif_name="antigen-heterogeneity",
        explanation=(
            "Right callout. Different tumor subclones express different surface "
            "antigens (varied colored dots). A single-target CAR loses efficacy "
            "as antigen-negative variants escape - drives need for multi-targeting."
        ),
        confidence=0.95,
    ),
    ElementAnnotation(
        label="Metabolic suppression: O2/pH/nutrients DOWN, toxic metabolites UP",
        bbox_px=(820, 670, 1270, 1010),
        motif_name="metabolic",
        explanation=(
            "Central blue ellipses. The TME's metabolic shield: hypoxia, low pH, "
            "nutrient depletion, accumulated lactate + adenosine. T cells suppressed "
            "by both substrate limitation and direct inhibition by metabolites."
        ),
        confidence=0.95,
    ),
    ElementAnnotation(
        label="Dysregulated vasculature: VCAM-1/ICAM-1 DOWN",
        bbox_px=(0, 1090, 820, 1530),
        motif_name="vasculature",
        explanation=(
            "Bottom-left circle. Tortuous, leaky tumor vessels with reduced "
            "adhesion molecules (VCAM-1/ICAM-1) - T cells fail to extravasate. "
            "CAR-T cells visible inside the vessel struggling to exit."
        ),
        confidence=0.95,
    ),
    ElementAnnotation(
        label="Physical barriers: ECM, CAF, IFP",
        bbox_px=(1260, 1040, 2030, 1620),
        motif_name="physical-barriers",
        explanation=(
            "Bottom-right circle. Dense extracellular matrix (ECM), cancer-associated "
            "fibroblasts (CAF), high interstitial fluid pressure (IFP) - mechanical "
            "exclusion of T cells from the tumor parenchyma."
        ),
        confidence=0.95,
    ),
    ElementAnnotation(
        label="Tumor mass (central cellular blob)",
        bbox_px=(420, 180, 1740, 1430),
        motif_name="tumor-mass",
        explanation=(
            "Central pink-cellular region (NOT the red vessel running through it). "
            "The actual tumor that all the surrounding suppressive mechanisms protect."
        ),
        confidence=0.90,
    ),
]


# Color mapping - each motif gets a visually distinct color
MOTIF_COLORS = {
    "suppressive-cells": (180, 60, 200),  # magenta
    "checkpoint": (220, 80, 60),  # red
    "soluble-inhibitors": (40, 160, 200),  # cyan
    "antigen-heterogeneity": (220, 100, 30),  # orange
    "metabolic": (50, 150, 150),  # teal
    "vasculature": (200, 30, 30),  # crimson
    "physical-barriers": (130, 90, 50),  # brown
    "tumor-mass": (220, 130, 150),  # tumor pink
}


def main() -> None:
    out = render_annotated_figure_v3(
        INPUT,
        ANNOTATIONS,
        OUT,
        motif_colors=MOTIF_COLORS,
        gutter_width_px=1100,  # wider for big labels
        label_max_chars=30,
    )
    print(f"Wrote -> {out}")
    print(f"\n{len(ANNOTATIONS)} annotations:")
    for i, ann in enumerate(ANNOTATIONS, start=1):
        x0, y0, x1, y1 = ann.bbox_px
        print(f"  {i}. {ann.label}")
        print(f"     bbox=({x0}, {y0}, {x1}, {y1}) area={x1 - x0}x{y1 - y0}")


if __name__ == "__main__":
    main()
