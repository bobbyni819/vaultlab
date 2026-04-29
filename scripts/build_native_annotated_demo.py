"""Demo: native-shape annotated PPTX.

Per Bobby 2026-04-29: each annotation must be a separate PowerPoint object
so it can be animated, moved, edited, or removed without re-rendering.

This script builds a deck with:
- Title slide (explanation)
- image1 (TCR/TAA/CAR) - 9 annotations, each as native shapes
- image10 (TME) - 8 annotations from the rigor-protocol redo

In PowerPoint, every annotation appears in the Selection pane as named
shapes (ann1_box, ann1_marker, ann1_label, ann1_side_marker etc.) so user
can apply entrance animations from the Animations tab.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

from vaultlab.figures.understand import ElementAnnotation
from vaultlab.slides.annotated_figure_slide import add_annotated_figure_slide


# ---------------------------------------------------------------------------
# Image1 annotations - 9 elements (lifted from v3 script with corrections)
# ---------------------------------------------------------------------------

IMAGE1 = Path(r"C:\tmp\cart_figs_v13\image1.png")

IMAGE1_ANNOTATIONS = [
    ElementAnnotation(
        label="Endogenous TCR (panel a, competing)",
        bbox_px=(295, 1827, 419, 2094),
        motif_name="endo-tcr",
        explanation="",
    ),
    ElementAnnotation(
        label="Introduced TCR (panel a)",
        bbox_px=(998, 1853, 1192, 2188),
        motif_name="intro-tcr",
        explanation="",
    ),
    ElementAnnotation(
        label="MHC Class I (panel a)",
        bbox_px=(1072, 1666, 1185, 1848),
        motif_name="mhc",
        explanation="",
    ),
    ElementAnnotation(
        label="CD3 chains (panel a)",
        bbox_px=(1206, 2100, 1261, 2392),
        motif_name="cd3",
        explanation="",
    ),
    ElementAnnotation(
        label="TAA (aberrantly expressed protein, panel b)",
        bbox_px=(2627, 1820, 2770, 1900),
        motif_name="taa",
        explanation="",
    ),
    ElementAnnotation(
        label="Endogenous TCR (panel b, primary receptor)",
        bbox_px=(2728, 1857, 3309, 2124),
        motif_name="endo-tcr",
        explanation="",
    ),
    ElementAnnotation(
        label="scFv / antigen recognition (panel c)",
        bbox_px=(4558, 1837, 4715, 2430),
        motif_name="endo-tcr",
        explanation="",
    ),
    ElementAnnotation(
        label="Co-stim domain (panel c)",
        bbox_px=(4558, 2436, 4614, 2589),
        motif_name="intro-tcr",
        explanation="",
    ),
    ElementAnnotation(
        label="CD3-zeta activation (panel c)",
        bbox_px=(4558, 2624, 4620, 2746),
        motif_name="cd3",
        explanation="",
    ),
]

IMAGE1_COLORS = {
    "endo-tcr": (40, 110, 220),  # electric blue
    "intro-tcr": (60, 200, 60),  # neon green
    "mhc": (130, 70, 180),  # purple
    "cd3": (220, 110, 30),  # orange
    "taa": (210, 50, 70),  # red-magenta
}


# ---------------------------------------------------------------------------
# Image10 annotations - rigor-protocol manual bboxes (image is 2035x1676)
# ---------------------------------------------------------------------------

IMAGE10 = Path(r"C:\tmp\cart_figs_v13\image10.png")

IMAGE10_ANNOTATIONS = [
    ElementAnnotation(
        label="Suppressive cells (MDSC, Treg, TAM)",
        bbox_px=(420, 0, 1380, 510),
        motif_name="suppressive-cells",
        explanation="",
    ),
    ElementAnnotation(
        label="PD-1/PDL-1 + CTLA-4/CD86 detail",
        bbox_px=(20, 360, 720, 800),
        motif_name="checkpoint",
        explanation="",
    ),
    ElementAnnotation(
        label="Soluble inhibitors: IL-10, TGF-beta",
        bbox_px=(1300, 60, 2030, 480),
        motif_name="soluble-inhibitors",
        explanation="",
    ),
    ElementAnnotation(
        label="Tumor antigen heterogeneity",
        bbox_px=(1330, 660, 2030, 1100),
        motif_name="antigen-heterogeneity",
        explanation="",
    ),
    ElementAnnotation(
        label="Metabolic suppression (low O2/pH/nutrients)",
        bbox_px=(820, 670, 1270, 1010),
        motif_name="metabolic",
        explanation="",
    ),
    ElementAnnotation(
        label="Dysregulated vasculature: VCAM/ICAM down",
        bbox_px=(0, 1090, 820, 1530),
        motif_name="vasculature",
        explanation="",
    ),
    ElementAnnotation(
        label="Physical barriers: ECM, CAF, IFP",
        bbox_px=(1260, 1040, 2030, 1620),
        motif_name="physical-barriers",
        explanation="",
    ),
    ElementAnnotation(
        label="Tumor mass (central pink blob, NOT vessel)",
        bbox_px=(420, 180, 1740, 1430),
        motif_name="tumor-mass",
        explanation="",
    ),
]

IMAGE10_COLORS = {
    "suppressive-cells": (180, 60, 200),
    "checkpoint": (220, 80, 60),
    "soluble-inhibitors": (40, 160, 200),
    "antigen-heterogeneity": (220, 100, 30),
    "metabolic": (50, 150, 150),
    "vasculature": (200, 30, 30),
    "physical-barriers": (130, 90, 50),
    "tumor-mass": (220, 130, 150),
}


# ---------------------------------------------------------------------------
# Notes content (concise; expanded later with the dual-format speaker notes
# once Bobby has answered Q10-Q13 in the slide-construction grill)
# ---------------------------------------------------------------------------

IMAGE1_NOTES = (
    "Three-panel comparison of how engineered T cells recognize tumor antigens. "
    "Each annotation is a separate PowerPoint shape - try right-clicking any "
    "numbered marker and 'Add Animation > Appear' to sequence them.\n\n"
    "Panel a (TCR therapy): introduced TCR (#2) competes with endogenous TCR "
    "(#1) for MHC-presented peptide (#3); CD3 chains (#4) handle signaling.\n\n"
    "Panel b (TAA therapy): aberrantly expressed protein (#5) presented via MHC; "
    "endogenous TCR (#6) is the active receptor.\n\n"
    "Panel c (CAR T): scFv (#7) binds antigen MHC-independently; "
    "co-stim (#8) + CD3-zeta (#9) inside the cell."
)

IMAGE10_NOTES = (
    "Tumor microenvironment suppressive mechanisms - 8 distinct callout regions. "
    "Each is a separate shape; you can hide individual ones by toggling visibility "
    "in the Selection pane.\n\n"
    "Numbered annotations correspond to the labeled circles in the figure: "
    "Suppressive cells (#1), checkpoint detail (#2), soluble inhibitors (#3), "
    "antigen heterogeneity (#4), metabolic suppression (#5), dysregulated "
    "vasculature (#6), physical barriers (#7), and the central tumor mass (#8) "
    "- which is the cellular blob, NOT the red blood vessel running through it.\n\n"
    "Animation suggestion: stagger entrances by 0.5s so each callout enters in "
    "panel-reading order (suppressive cells -> checkpoint -> soluble inhibitors -> "
    "antigen heterogeneity -> metabolic -> vasculature -> physical barriers -> "
    "tumor mass)."
)


def add_title_slide(pres: Presentation) -> None:
    blank = pres.slide_layouts[6]
    s = pres.slides.add_slide(blank)
    box = s.shapes.add_textbox(Inches(0.5), Inches(2.0), Inches(12.3), Inches(2.0))
    tf = box.text_frame
    tf.word_wrap = True
    from pptx.enum.text import PP_ALIGN

    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    run = p.add_run()
    run.text = "VaultLab - Native-Shape Annotations"
    run.font.name = "Arial"
    run.font.size = Pt(40)
    run.font.bold = True

    sub = s.shapes.add_textbox(Inches(0.5), Inches(4.2), Inches(12.3), Inches(2.5))
    sf = sub.text_frame
    sf.word_wrap = True
    text = (
        "Each numbered marker, bounding box, and side label is a SEPARATE "
        "PowerPoint shape - right-click any of them in the Selection pane "
        "(View > Selection Pane) to:\n\n"
        "  - Add entrance animations from Animations tab\n"
        "  - Move them around the slide\n"
        "  - Edit the text directly\n"
        "  - Delete individual ones\n\n"
        "Naming: ann1_box / ann1_marker / ann1_label / ann1_side_marker so all "
        "shapes for one annotation can be selected together."
    )
    for i, line in enumerate(text.split("\n\n")):
        p = sf.paragraphs[0] if i == 0 else sf.add_paragraph()
        run = p.add_run()
        run.text = line
        run.font.name = "Arial"
        run.font.size = Pt(15)
        run.font.color.rgb = RGBColor(60, 60, 60)


SECTIONS = [
    "Background",
    "Antigen recognition",
    "TME challenges",
    "Engineering strategies",
    "Outlook",
]


def main() -> None:
    pres = Presentation()
    pres.slide_width = Inches(13.333)
    pres.slide_height = Inches(7.5)

    add_title_slide(pres)

    add_annotated_figure_slide(
        pres,
        IMAGE1,
        IMAGE1_ANNOTATIONS,
        title="Engineered T cells recognize antigens via 3 mechanisms: TCR, TAA, CAR",
        caption="Three-panel comparison from VanNoy 2025 (BioRender). "
        "Each numbered annotation is a native PowerPoint shape.",
        motif_colors=IMAGE1_COLORS,
        notes=IMAGE1_NOTES,
        page_number=2,
        sections=SECTIONS,
        current_section_idx=1,  # "Antigen recognition"
    )

    add_annotated_figure_slide(
        pres,
        IMAGE10,
        IMAGE10_ANNOTATIONS,
        title="The TME suppresses CAR-T via 7 converging mechanisms around the tumor",
        caption="8 labeled callouts surrounding the central tumor. "
        "Try View > Selection Pane to see all shapes.",
        motif_colors=IMAGE10_COLORS,
        notes=IMAGE10_NOTES,
        page_number=3,
        sections=SECTIONS,
        current_section_idx=2,  # "TME challenges"
    )

    out = Path(r"C:\Users\bobby\Downloads\car_t_decks\figure_understanding_native_v2.pptx")
    pres.save(out)
    print(f"Wrote -> {out}")


if __name__ == "__main__":
    main()
