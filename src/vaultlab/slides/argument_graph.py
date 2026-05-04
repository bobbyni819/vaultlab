"""Argument-graph sidecar — extract a deck's slide-claim chain into markdown.

Bobby's 2026-05-03 Phase-4 ask: every deck should produce an
``<deck>.argument-graph.md`` listing each slide's title + key_claim +
transition. This lets the speaker audit logical flow ("does each slide's
claim follow from the previous one?") without scrolling through
PowerPoint.

Output format::

    # Deck argument graph — <deck-stem>

    Generated 2026-05-03

    ## Slide 1 — Title slide
    - **Hook**: ...
    - **Key claim**: ...
    - **Transition**: ...

    ## Slide 2 — <descriptive title>
    - **Hook**: ...
    - **Key claim**: ...
    - **Transition**: ...
    ...

The argument graph is built from the deck plan dict (the in-memory plan)
rather than the rendered .pptx so it captures speaker_notes that don't
appear visually.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any


def render_argument_graph(plan: dict[str, Any]) -> str:
    """Render a deck plan as a markdown argument-graph document."""
    deck_title = plan.get("title", "(untitled deck)")
    today = datetime.date.today().isoformat()
    lines: list[str] = [
        f"# Deck argument graph — {deck_title}",
        "",
        f"Generated {today}",
        "",
        f"Topic: `{plan.get('topic', '?')}`  |  Speaker: `{plan.get('author', '?')}`",
        "",
        "Read this top-to-bottom. Each slide's KEY CLAIM should follow from the previous one's, ",
        "and each TRANSITION should set up the next.",
        "",
        "---",
        "",
    ]
    slides = plan.get("slides", [])
    for i, s in enumerate(slides, 1):
        stype = s.get("type", "?")
        title = s.get("title", "").strip() or "(no title)"
        sn = s.get("speaker_notes") or {}
        hook = (sn.get("hook") or "").strip()
        key_claim = (sn.get("key_claim") or "").strip()
        evidence = (sn.get("evidence") or "").strip()
        transition = (sn.get("transition") or "").strip()
        key_terms = sn.get("key_terms") or []

        lines.append(f"## Slide {i} — {title}")
        lines.append(f"_type: `{stype}`_")
        lines.append("")
        if hook:
            lines.append(f"- **Hook**: {hook}")
        if key_claim:
            lines.append(f"- **Key claim**: {key_claim}")
        if evidence:
            lines.append(f"- **Evidence**: {evidence}")
        if key_terms:
            terms_str = ", ".join(str(t) for t in key_terms)
            lines.append(f"- **Key terms**: {terms_str}")
        if transition:
            lines.append(f"- **Transition**: {transition}")
        if not (hook or key_claim or evidence or transition):
            lines.append("- (no speaker notes attached)")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_argument_graph(plan: dict[str, Any], deck_path: Path | str) -> Path:
    """Write the argument-graph markdown next to the deck file.

    Output path: ``<deck_path stem>.argument-graph.md`` in the same dir.
    """
    deck_path = Path(deck_path)
    out_path = deck_path.with_suffix("").with_name(
        deck_path.stem + ".argument-graph.md"
    )
    out_path.write_text(render_argument_graph(plan), encoding="utf-8")
    return out_path


__all__ = ["render_argument_graph", "write_argument_graph"]
