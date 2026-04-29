"""Save the figure-annotation decision tree + theme-color rule to user_memory."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from vaultlab.context.user_memory import remember


def main() -> None:
    remember(
        category="feedback",
        name="figure-annotation-decision-tree",
        description="Mandatory per-figure decision tree before placing any annotation; semantic + whitespace.",
        content=(
            "BEFORE placing any annotation on a figure, run this decision tree. Per Bobby "
            "2026-04-29 v4 review: I was placing markers without actually checking what's at "
            "the destination. That has to stop.\n\n"
            "**Step 1 - SEMANTIC READ.** Open the figure and describe in detail every element "
            "that matters: panels, motifs, labels, arrows, callouts, sub-zooms, color codes. "
            "Write the description down (in script comments OR in slide notes) before any coords.\n\n"
            "**Step 2 - WHITESPACE MAP.** Programmatically identify whitespace zones in the image "
            "(low saturation + high value in HSV; or pixels close to white). Cache these zones "
            "as candidate marker positions.\n\n"
            "**Step 3 - PER-ANNOTATION DECISION:**\n"
            "  a. **Use a box?** Only if the element has clear extent and a box won't crowd "
            "neighbors. For narrow / small elements, drop the box (use_box=False) and use just "
            "a numbered marker pointing at the element.\n"
            "  b. **Marker position?** Default top-left of the bbox is ONE option. ALWAYS check:\n"
            "     - Would default placement collide with another marker? -> offset.\n"
            "     - Would default placement land on important figure content? -> offset.\n"
            "     - Where is the NEAREST whitespace zone (from Step 2)? Offset toward it.\n"
            "  c. **Color match?** Marker + side label color = motif color. White halo around "
            "marker for visibility.\n\n"
            "**Step 4 - VERIFY (multimodal).** Render the annotated overlay, READ IT BACK via "
            "the multimodal Read tool, walk each box and marker, confirm:\n"
            "  - Box is on the right element\n"
            "  - Marker is in whitespace, not blocking content\n"
            "  - Markers don't overlap each other\n"
            "  - Side labels in correct order top-to-bottom\n"
            "If any fail, adjust + re-render. DO NOT ship without this verification.\n\n"
            "**Step 5 - SCRIPT YOUR REASONING.** Comments in the matcher / annotation list "
            "should say WHY each marker is placed where it is, in concept terms (not 'because "
            "I picked offset (-280, 50)' but 'placed left of construct in panel-c whitespace, "
            "below #7 to avoid overlap')."
        ),
    )

    remember(
        category="feedback",
        name="theme-aware-font-color",
        description="Always pick text color based on slide background, not a fixed RGB.",
        content=(
            "Text colors must adapt to the slide's background, not be hardcoded. Per Bobby "
            "2026-04-29 v4 review: 'the slide background is black but you're using a gray font "
            "so it's hard to see'.\n\n"
            "**Rule:** every text-color decision starts by asking 'what's behind this text?'\n"
            "  - Dark slide background (luminance < 100): use light text (white or near-white)\n"
            "  - Light slide background (luminance > 180): use dark text (near-black)\n"
            "  - Mid-tone background: use the highest-contrast option\n\n"
            "**Implementation:** vaultlab.slides should expose a `text_color_for_bg(bg_rgb)` "
            "helper that returns the correct text RGBColor. Section banner, footer, caption, "
            "and title all use it.\n\n"
            "**Why:** Hickey Lab template defaults to dark masters; my hardcoded gray (120,120,120) "
            "for page numbers + (110,115,125) muted slate for inactive section pills are "
            "INVISIBLE on the dark template.\n\n"
            "**How to apply:** detect master background via the master's slide layout / "
            "background fill, OR accept a `theme_variant: 'dark' | 'light'` parameter and switch "
            "the entire text palette accordingly."
        ),
    )

    remember(
        category="preference",
        name="hickey-template-logo-zones",
        description="Hickey Lab masters have Duke + Hickey logos at bottom; banner must avoid them.",
        content=(
            "The Hickey Lab template's slide masters have lab logos and Duke logo flanking the "
            "bottom of every slide. Per Bobby 2026-04-29 v4 review: section banner must SHRINK "
            "horizontally so it sits between the logos, not overlap them.\n\n"
            "**Approximate logo zones (verify by inspecting the master):**\n"
            "  - Bottom-left ~1.0 inch reserved for Hickey lab logo\n"
            "  - Bottom-right ~1.0 inch reserved for Duke logo\n"
            "  - Banner safe zone: x in [1.0, 12.333] roughly (slide is 13.333 wide)\n\n"
            "**Implementation:** add a `theme_safe_zones` parameter or detect the logo positions "
            "via the master's shape inventory. For now, when `theme='hickey-lab'`, set banner "
            "margin = 1.1 in (instead of 0.4 in default).\n\n"
            "**Why:** Bobby 2026-04-29: 'with the Hickey Lab background you can see that the "
            "bottom is flanked by the Hickey lab logo and then Duke logo. So the part where "
            "you're writing kind of like the progression needs to be shrinked a bit more.'"
        ),
    )

    print("3 memories saved: figure-annotation-decision-tree, theme-aware-font-color, "
          "hickey-template-logo-zones")


if __name__ == "__main__":
    main()
