"""Generic example deck — runnable demo of vaultlab.slides.

Builds a 5-slide deck showcasing the four most common slide layouts:
title / text / figure_only / quote / references. Outputs a `.pptx` plus
the auto-generated `argument-graph.md` sidecar so users can see what
vaultlab produces without needing a KB or any literature corpus.

Run::

    python examples/sample_deck/build_sample_deck.py

Output: examples/sample_deck/sample.pptx (+ sample.argument-graph.md)

Replace the figure path with any local PNG to see how the figure layout
adapts to your image's aspect ratio.
"""

from __future__ import annotations

from pathlib import Path

# Use this directory's own placeholder figure so the demo is self-contained
HERE = Path(__file__).parent
FIGURE = HERE / "placeholder_figure.png"


def _ensure_placeholder_figure() -> None:
    """Generate a small placeholder PNG so the demo runs out of the box."""
    if FIGURE.exists():
        return
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return
    img = Image.new("RGB", (1200, 700), color=(245, 246, 248))
    draw = ImageDraw.Draw(img)
    # Draw a simple bar chart as a placeholder "figure"
    # Each bar: (x0, y_top, x1, y_bottom)
    bars = [(150, 200, 250, 500), (300, 280, 400, 500), (450, 150, 550, 500),
            (600, 350, 700, 500), (750, 220, 850, 500), (900, 320, 1000, 500)]
    colors = [(80, 130, 200), (220, 95, 75), (100, 180, 110),
              (210, 165, 60), (150, 100, 180), (80, 175, 195)]
    for (x0, y_top, x1, y_bot), c in zip(bars, colors):
        draw.rectangle((x0, y_top, x1, y_bot), fill=c)
    draw.line((100, 500, 1100, 500), fill=(40, 40, 40), width=3)
    draw.line((100, 100, 100, 500), fill=(40, 40, 40), width=3)
    draw.text((400, 50), "Sample data — 6 conditions", fill=(40, 40, 40))
    img.save(FIGURE)


def plan() -> dict:
    return {
        "title": "vaultlab demo deck",
        "subtitle": "Five slides, five primitives",
        "topic": "vaultlab-demo",
        "author": "vaultlab example",
        "kb": "demo",
        "theme": "dark",
        "template": "plain",
        "slides": [
            {
                "type": "title",
                "title": "vaultlab — slide-deck demo",
                "subtitle": "Generated from a Python plan dict",
                "author": "Replace with your name",
                "speaker_notes": {
                    "hook": "Open with the system pitch: research-paper-driven decks.",
                    "key_claim": "Every slide is data + speaker notes, not just a layout.",
                    "transition": "Outline first.",
                },
            },
            {
                "type": "text",
                "title": "What this deck shows",
                "bullets": [
                    "Adaptive layout dispatch based on figure aspect + bullet count",
                    "Three-tier speaker notes (mental_map + script + walkthrough)",
                    "Audit-driven quality gates (overflow / overlap / off-slide)",
                    "Argument-graph + practice-script sidecars per deck",
                ],
                "speaker_notes": {
                    "hook": "Quick map of what's coming.",
                    "key_claim": "Four content slides + one references slide demonstrate the core layouts.",
                    "transition": "Next: a figure slide that picks its layout from the image aspect.",
                },
            },
            {
                "type": "figure",
                "title": "Auto-layout adapts to figure aspect ratio",
                "image_path": str(FIGURE),
                "caption": "Six placeholder bars; aspect 1.71 → routed to figure_top_caption_br.",
                "citation_source": "vaultlab demo (placeholder data) | 2026",
                "bullets": [
                    "Wide-aspect figures get the top-caption-bottom-right layout",
                    "Square figures default to side-caption (caption in right gutter)",
                    "Tall-aspect figures use figure-above-bullets",
                    "All preserve aspect ratio — figure never stretched",
                ],
                "speaker_notes": {
                    "hook": "How does layout adapt?",
                    "key_claim": "The dispatcher reads image aspect + bullet count and picks one of 6 layouts.",
                    "evidence": "See vaultlab.slides.deck._auto_pick_figure_layout for the rule table.",
                    "key_terms": ["aspect ratio", "auto-layout", "layout dispatcher"],
                    "transition": "Quote slides give the deck an emotional beat.",
                    "script": (
                        "vaultlab decides slide layout dynamically. For each figure slide, the "
                        "dispatcher reads three signals: the figure's aspect ratio, the number of "
                        "bullets you provided, and (optionally) the content density of the figure. "
                        "From those signals it picks one of six layouts: figure-only (no bullets, "
                        "centered hero), figure-with-side-caption (square + bullets, caption + "
                        "citation in right gutter), figure-above-bullets (extreme aspect), "
                        "figure-top-caption-BR (wide-flat with caption tucked bottom-right), "
                        "figure-with-bullets (default), or two-figure-compare. The goal is to "
                        "give every figure as much canvas as possible without crowding text."
                    ),
                },
            },
            {
                "type": "quote",
                "quote": "If you can't show your data, you can't tell your story.",
                "attribution": "Folk wisdom in slide design",
            },
            {
                "type": "references",
                "title": "References",
                "references": [
                    "Replace these with your own citations.",
                    "Each line becomes one entry on the references slide.",
                    "vaultlab auto-switches to a 2-column layout when references > 7.",
                ],
            },
        ],
    }


def main() -> int:
    from vaultlab.slides.deck import build_from_plan

    _ensure_placeholder_figure()
    out_dir = HERE / "expected_outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "sample.pptx"
    print(f"Building {out_path.name} ...")
    plan_dict = plan()
    result = build_from_plan(plan_dict, out_path, write_marp=False)
    print(f"  built: {result['pptx']}")
    n_slides = len(plan_dict["slides"])
    print(f"  {n_slides} slides")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
