"""One-shot: save Bobby's 2026-04-29 grill-slide-construction answers to memory + decisions log."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from vaultlab.context.user_memory import remember
from vaultlab.kb.feedback import log_decision


def main() -> None:
    remember(
        category="preference",
        name="slide-template-rules",
        description="Slide template defaults from Bobby 2026-04-29 grill answers.",
        content=(
            "Slide template invariants for vaultlab.slides:\n\n"
            "**Title:** centered, content-descriptive (a takeaway sentence, not a topic name). "
            "Bobby: 'people can just read the title of slide and know exactly what you're talking "
            "about rather than being something baby like why are entering this problem'.\n\n"
            "**Footer:** page number (right-aligned). PLUS a section banner across the bottom: "
            "N rectangles spanning the full width, current section highlighted in cobalt with "
            "white bold text; others muted gray.\n\n"
            "**Theme:** ship `default` for now. Build `hickey-lab` and `duke` themes when needed.\n\n"
            "**Fonts:** body 20-24pt minimum (projector-readable). Title 26pt+. Caption 12-14pt. "
            "Footer 9pt. Marker numerals 11pt. Side label 11pt.\n\n"
            "**Captions on figure slides:** small footer caption (1 italic line) + optional bullet "
            "points on the side describing key takeaways when content warrants them. Configurable "
            "per slide.\n\n"
            "**Citations:** superscript [N] on slide matching reference list at end. Plus full "
            "reference in speaker notes."
        ),
    )

    remember(
        category="preference",
        name="slide-animation-rules",
        description="Animation defaults: bullet-per-click; marker+label paired; per-figure-type variations.",
        content=(
            "Animation defaults for vaultlab.slides:\n\n"
            "**Bullets:** one per click.\n\n"
            "**Annotations:** numbered marker on figure + corresponding side label in gutter "
            "MUST appear together (paired entrance). One pair per click.\n\n"
            "**Multi-panel figures:** mostly walk through annotation-by-annotation.\n\n"
            "**Cycle figures (e.g., 7-step cancer-immunity cycle):** each step appears in sequence "
            "with its number on click.\n\n"
            "**Schematic with sub-zooms:** numbered annotations + corresponding caption text "
            "appearing together; sub-zooms are inline within the figure PNG, so they animate as "
            "part of their parent annotation.\n\n"
            "**Slide transitions:** subtle (none or 0.5s fade); user choice."
        ),
    )

    remember(
        category="preference",
        name="speaker-notes-dual-format",
        description="Mental map (HOOK/KEY CLAIM/EVIDENCE/KEY TERMS/CLICK/TRANSITION) + dashed divider + detailed script.",
        content=(
            "Speaker notes always have TWO modes per slide separated by a divider:\n\n"
            "**Mental map** (for fluent presenters):\n"
            "  - HOOK: one phrase to open with\n"
            "  - KEY CLAIM: one sentence stating the slide's takeaway\n"
            "  - EVIDENCE: pointer to the figure / data on the slide\n"
            "  - KEY TERMS: exact terms to pronounce correctly\n"
            "  - CLICK: animation cue\n"
            "  - TRANSITION: one-sentence bridge to next slide\n\n"
            "**Divider:** `--- DETAILED SCRIPT ---` (matches existing bobby_slides._speaker convention)\n\n"
            "**Detailed script** (for first-time presenters): full first-person paragraphs, "
            "hedged voice maintained ('these data are consistent with X' not 'these data prove X'). "
            "Length: 200-400 words per slide; flex by complexity.\n\n"
            "**Implementation:** vaultlab.slides.notes.dual_format(slide_dict) returns string "
            "ready to drop into slide.notes_slide.notes_text_frame."
        ),
    )

    remember(
        category="feedback",
        name="annotation-marker-placement-flexibility",
        description="Marker positions are dynamic per figure - default top-left, offset to whitespace when overlapping or blocking content.",
        content=(
            "Per Bobby 2026-04-29 v3 review: when placing numbered markers on figure annotations, "
            "default top-left of the box is ONE option, not the rule. Always check whether:\n"
            "1. Two markers would overlap each other -> offset one to nearby whitespace.\n"
            "2. A marker would block important figure content -> shift to side/above/below.\n"
            "3. The element is small/narrow enough that the box wraps awkwardly -> drop the box "
            "(use_box=False) and just point a marker at the element.\n\n"
            "**Implementation:** ElementAnnotation has `use_box: bool = True` and "
            "`marker_offset_px: tuple[int, int] | None = None`.\n\n"
            "**Why:** Bobby 2026-04-29: '5 and 6 are overlapping with each other and they're blocking "
            "off the content. 2 and 3 are also blocking motif 4. 8 9 7 are also blocking off a huge "
            "part of the different motifs.'\n\n"
            "**How to apply:** When generating annotations, after placing all bboxes, do a collision "
            "check: for each pair of markers, if their default positions would overlap, offset one "
            "to clear whitespace. For dense receptor stacks, offset markers OUTSIDE the column."
        ),
    )

    kb = Path("G:/My Drive/Knowledge/vaultlab")
    log_decision(
        kb,
        "vaultlab",
        "Slide template: centered title, page-number footer, section banner",
        "Bobby 2026-04-29: takeaway-style centered titles; right-aligned page number; "
        "N-rect section banner with current highlighted in cobalt.",
        tags=["slides", "template", "footer"],
    )
    log_decision(
        kb,
        "vaultlab",
        "Animations: bullet-per-click; marker+label paired",
        "Bobby Q7 + Q8 2026-04-29: single-click reveals one bullet OR one annotation pair "
        "(on-figure marker + gutter label appear together).",
        tags=["slides", "animation"],
    )
    log_decision(
        kb,
        "vaultlab",
        "Speaker notes: dual-format always (mental map + detailed script + divider)",
        "Bobby 2026-04-29: every slide has both modes. Mental map uses HOOK/KEY CLAIM/EVIDENCE/"
        "KEY TERMS/CLICK/TRANSITION. Divider matches bobby_slides._speaker.",
        tags=["slides", "notes"],
    )
    log_decision(
        kb,
        "vaultlab",
        "Citations: superscript [N] on slide + full reference in notes + reference list slide",
        "Bobby Q6 2026-04-29: every figure attributed inline via superscript [N] matching "
        "ref list at end of deck.",
        tags=["slides", "citations"],
    )
    log_decision(
        kb,
        "vaultlab",
        "Marker placement is dynamic per figure (use_box, marker_offset_px)",
        "Bobby 2026-04-29 v3 review: default top-left is one option, not the rule. Override "
        "per annotation to avoid marker overlaps and clear figure motifs. ElementAnnotation "
        "now has use_box and marker_offset_px fields.",
        tags=["figures", "annotations", "rendering"],
    )
    print("4 memories + 5 decisions logged.")


if __name__ == "__main__":
    main()
