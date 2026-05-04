"""Practice-script + flashcard generators.

Bobby's 2026-05-04 ask: every prelim/defense rehearsal needs:

1. **Practice script**: printable markdown listing each slide with title +
   key_claim + script + per-slide TIME MARKER (so the speaker knows
   "at slide 7 you should be at minute 9").

2. **Flashcards**: Anki-importable pipe-separated front|back cards for
   memorizing key claims + terms.

Both consume a deck plan dict (the same shape ``build_from_plan`` takes).

Public API:

- :func:`render_practice_script(plan)` → str (markdown)
- :func:`write_practice_script(plan, deck_path)` → Path to sidecar
- :func:`render_flashcards(plan)` → str (Anki-pipe markdown)
- :func:`write_flashcards(plan, deck_path)` → Path
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from vaultlab.slides.time_budget import estimate_slide_minutes


def _format_time(minutes: float) -> str:
    """Format minutes as 'M:SS'."""
    m = int(minutes)
    s = int(round((minutes - m) * 60))
    if s == 60:
        m += 1
        s = 0
    return f"{m}:{s:02d}"


def render_practice_script(plan: dict[str, Any]) -> str:
    """Render the deck as a printable rehearsal-script markdown.

    Each slide gets:
    - Header with index + title
    - Time marker ("by end of this slide: 4:30")
    - Mental map (hook / key_claim / evidence / key_terms / transition)
    - Full script (the say-this version)
    - Optional extended walkthrough indicator (for unfamiliar topics)
    """
    deck_title = plan.get("title", "(untitled)")
    target_minutes = float(plan.get("_target_minutes", 0) or 0)
    slides = plan.get("slides") or []

    lines: list[str] = [
        f"# Practice script — {deck_title}",
        "",
        f"_Use-case: {plan.get('_use_case', '?')}  |  Target: {target_minutes:.0f} min  |  {len(slides)} slides_",
        "",
        "Print this and walk through each slide. Time markers tell you where you should be on the running clock.",
        "",
        "---",
        "",
    ]

    cumulative = 0.0
    for i, s in enumerate(slides, 1):
        title = (s.get("title") or "").strip() or f"(slide {i})"
        stype = s.get("type", "?")
        sn = s.get("speaker_notes") or {}
        per_slide_min = estimate_slide_minutes(s)
        cumulative += per_slide_min

        lines.append(f"## Slide {i}/{len(slides)} — {title}")
        lines.append(f"_type: `{stype}`  |  est: {per_slide_min:.1f} min  |  by end: **{_format_time(cumulative)}**_")
        lines.append("")

        hook = (sn.get("hook") or "").strip()
        key_claim = (sn.get("key_claim") or "").strip()
        evidence = (sn.get("evidence") or "").strip()
        key_terms = sn.get("key_terms") or []
        click = (sn.get("click") or "").strip()
        transition = (sn.get("transition") or "").strip()
        script = (sn.get("script") or "").strip()
        walkthrough = (sn.get("extended_walkthrough") or "").strip()

        if hook or key_claim or transition:
            lines.append("**Mental map** (eyeball reference)")
            if hook:        lines.append(f"- Hook: {hook}")
            if key_claim:   lines.append(f"- Key claim: {key_claim}")
            if evidence:    lines.append(f"- Evidence: {evidence}")
            if key_terms:   lines.append(f"- Key terms: {', '.join(str(t) for t in key_terms)}")
            if click:       lines.append(f"- Click: {click}")
            if transition:  lines.append(f"- Transition: {transition}")
            lines.append("")

        if script:
            lines.append("**Script** (deliver this):")
            lines.append("")
            lines.append(f"> {script}")
            lines.append("")

        if walkthrough:
            wlen = len(walkthrough.split())
            lines.append(f"_(Extended walkthrough available — {wlen} words. Reference if asked deeper questions.)_")
            lines.append("")

        lines.append("---")
        lines.append("")

    if target_minutes > 0:
        lines.append(f"## Pacing summary")
        lines.append(f"- Estimated total: **{cumulative:.1f} min**")
        lines.append(f"- Target: **{target_minutes:.0f} min**")
        lines.append(f"- Delta: **{cumulative - target_minutes:+.1f} min**")
    return "\n".join(lines).rstrip() + "\n"


def write_practice_script(plan: dict[str, Any], deck_path: Path | str) -> Path:
    """Write a practice-script.md sidecar next to the deck."""
    deck_path = Path(deck_path)
    out_path = deck_path.with_suffix("").with_name(deck_path.stem + ".practice-script.md")
    out_path.write_text(render_practice_script(plan), encoding="utf-8")
    return out_path


def render_flashcards(plan: dict[str, Any]) -> str:
    """Render flashcards as Anki-importable pipe-separated markdown.

    Format::

        front | back

    One card per content slide. Front = "Slide N: <title>". Back = key_claim
    + key_terms + transition.
    """
    slides = plan.get("slides") or []
    deck_title = plan.get("title", "")
    lines: list[str] = [
        f"# Flashcards — {deck_title}",
        "",
        "_Pipe-separated, Anki-importable. Front | Back._",
        "",
    ]
    skip_types = {"title", "section_divider", "references"}
    for i, s in enumerate(slides, 1):
        if s.get("type", "") in skip_types:
            continue
        title = (s.get("title") or f"Slide {i}").replace("|", "/")
        sn = s.get("speaker_notes") or {}
        kc = (sn.get("key_claim") or "").replace("|", "/").replace("\n", " ")
        kt = sn.get("key_terms") or []
        tr = (sn.get("transition") or "").replace("|", "/").replace("\n", " ")
        front = f"Slide {i}: {title}"
        back_parts = []
        if kc: back_parts.append(f"Claim: {kc}")
        if kt: back_parts.append(f"Terms: {', '.join(str(t) for t in kt)}")
        if tr: back_parts.append(f"Transition: {tr}")
        back = "  ".join(back_parts) or "(no notes)"
        lines.append(f"{front} | {back}")
    return "\n".join(lines) + "\n"


def write_flashcards(plan: dict[str, Any], deck_path: Path | str) -> Path:
    """Write a flashcards.md sidecar next to the deck."""
    deck_path = Path(deck_path)
    out_path = deck_path.with_suffix("").with_name(deck_path.stem + ".flashcards.md")
    out_path.write_text(render_flashcards(plan), encoding="utf-8")
    return out_path


__all__ = [
    "render_flashcards",
    "render_practice_script",
    "write_flashcards",
    "write_practice_script",
]
