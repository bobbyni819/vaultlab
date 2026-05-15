"""Journal-club deck template (paper discussion).

10-12 slides for a 30-minute paper-discussion session, following Bobby's
required journal-club structure
(:doc:`/feedback/feedback_journal_club_deck_practices`):

1. Title (paper citation, presenter, date)
2. Why this paper (relevance + hook)
3. Lab context (how this connects to our work)
4. Field context (what other groups are doing here)
5. Section divider — Key figures
6-8. Figures with strengths and limits (one per key figure)
9. Take-home (a one-sentence quote from the paper + 3 bullets)
10. Discussion prompts (open questions for the group)
11. References

The slide-by-slide build rules from Bobby's feedback memory:
    - Spell out abbreviations on first use IN BULLETS (e.g.
      ``"CODEX (CO-Detection by indEXing)"``). The builder doesn't
      enforce this — caller is responsible — but the slide structure
      gives natural places for abbrev-on-first-use bullets.
    - Parallel ``"LABEL — detail"`` bullet structure for strengths/limits
      (caller passes pre-formatted bullets; ``format_label_bullet`` is a
      convenience).
    - Always write a companion ``READ_FIRST_*.md`` briefing (the caller's
      responsibility; ``READ_FIRST_PATH`` constant is the canonical
      template filename).

This is distinct from :mod:`vaultlab.slides.journal_club_arcs` — that's an
*arc-registry* (paper-type → slide-skeleton); this is a *full deck
builder* that takes Bobby's structured inputs and emits a complete
deck plan.

Hard slide rules:
    - Roboto, 28/24/18 min sizes.
    - Sentence-style titles (e.g. "Authors show that X reduces Y under Z").
    - No shape overlap.
"""

from __future__ import annotations

from typing import Any


READ_FIRST_PATH = "READ_FIRST_journal_club.md"


def format_label_bullet(label: str, detail: str) -> str:
    """Format a bullet in parallel ``LABEL — detail`` style.

    The em-dash is the canonical Bobby-style separator.
    """
    return f"{label} — {detail}"


def _figure_slide(entry: dict[str, Any]) -> dict[str, Any]:
    """Convert a figure entry into a figure slide with strengths/limits.

    Each figure entry should provide:
        - ``title``: sentence headline for the figure (e.g.
          "Figure 2 — CODEX panel resolves 28 markers across 4 donors").
        - ``image_path``: figure path.
        - ``caption``: figure caption.
        - ``strengths``: list[str] in ``"LABEL — detail"`` style.
        - ``limits``: list[str] in ``"LABEL — detail"`` style.
        - ``citation``: figure citation source (paper short cite).
    """
    title = entry.get("title", "")
    image_path = entry.get("image_path") or entry.get("figure", "")
    caption = entry.get("caption", "")
    strengths = entry.get("strengths") or []
    limits = entry.get("limits") or []
    citation = entry.get("citation") or entry.get("citation_source", "")

    # Render strengths + limits together as bullets so the audience sees
    # both per figure (this is the JC value-add).
    bullets: list[str] = []
    if strengths:
        bullets.append("Strengths:")
        bullets.extend(strengths)
    if limits:
        bullets.append("Limits:")
        bullets.extend(limits)

    return {
        "type": "figure",
        "title": title,
        "image_path": str(image_path),
        "caption": caption,
        "bullets": bullets,
        "citation_source": citation,
        "speaker_notes": {
            "hook": title,
            "key_claim": caption or title,
        },
    }


def build_journal_club(
    *,
    paper_citation: str,
    paper_doi: str,
    presenter: str,
    presented_on: str,
    why_this_paper_bullets: list[str],
    lab_context_bullets: list[str],
    field_context_bullets: list[str],
    figures: list[dict[str, Any]],
    take_home_quote: str,
    take_home_attribution: str,
    take_home_bullets: list[str],
    discussion_prompts: list[str],
    references: list[str] | None = None,
    why_title: str = "",
    lab_context_title: str = "",
    field_context_title: str = "",
    figures_section_title: str = "Key figures, strengths, and limits",
    discussion_title: str = "Discussion prompts",
    theme: str = "dark",
) -> dict[str, Any]:
    """Build a 10-12 slide journal-club deck plan.

    Args:
        paper_citation: Short citation
            (e.g. "Goltsev et al., Cell 2018").
        paper_doi: DOI of the paper.
        presenter: Presenter line (e.g. "Bobby Ni").
        presented_on: Date label (e.g. "2026-05-15").
        why_this_paper_bullets: 3-4 bullets — why we're reading this
            now. Spell out abbreviations on first use here.
        lab_context_bullets: 3-4 bullets — how this connects to lab work.
        field_context_bullets: 3-4 bullets — what other groups are doing.
        figures: 2-4 figure entries (see :func:`_figure_slide`). Each
            becomes one slide with strengths and limits as bullets.
        take_home_quote: A direct quote from the paper that captures
            the take-home.
        take_home_attribution: Quote attribution
            (e.g. "Goltsev et al. 2018, Cell").
        take_home_bullets: 2-3 bullets in addition to the quote.
        discussion_prompts: 3-5 prompts to drive group discussion.
        references: Optional list of references (defaults to the paper
            alone).
        why_title / lab_context_title / field_context_title: Optional
            title overrides — defaults preserve the standard JC arc.
        figures_section_title: Section-divider title before figure slides.
        discussion_title: Title for the discussion-prompts slide.
        theme: ``"dark"`` (default) or ``"light"``.

    Returns:
        Deck-plan dict for :func:`vaultlab.slides.build_from_plan`.

    Notes:
        Per Bobby's journal-club practice, callers should also write a
        companion :data:`READ_FIRST_PATH` briefing alongside the deck.
        That's outside the deck-build scope but documented here so the
        rule survives a fresh session.
    """
    if not figures:
        raise ValueError(
            "journal_club requires at least one figure entry"
        )

    slides: list[dict[str, Any]] = []

    # 1. Title
    slides.append(
        {
            "type": "title",
            "title": paper_citation,
            "subtitle": f"Journal club — {presented_on}",
            "author": presenter,
            "speaker_notes": {
                "hook": paper_citation,
                "key_terms": [paper_citation, paper_doi],
            },
        }
    )

    # 2. Why this paper
    slides.append(
        {
            "type": "text",
            "title": why_title or "Why we are reading this paper now",
            "bullets": list(why_this_paper_bullets),
            "speaker_notes": {
                "hook": "Relevance to us right now.",
                "key_claim": "This is why we're spending 30 min on it.",
            },
        }
    )

    # 3. Lab context
    slides.append(
        {
            "type": "text",
            "title": lab_context_title or "How this connects to our lab's work",
            "bullets": list(lab_context_bullets),
            "speaker_notes": {
                "hook": "Where this fits in our arc.",
                "key_claim": "Lab-context connections.",
            },
        }
    )

    # 4. Field context
    slides.append(
        {
            "type": "text",
            "title": field_context_title
            or "What other groups are doing in this space",
            "bullets": list(field_context_bullets),
            "speaker_notes": {
                "hook": "The broader field.",
                "key_claim": "Adjacent work.",
            },
        }
    )

    # 5. Section divider before figures
    slides.append(
        {
            "type": "section_divider",
            "title": figures_section_title,
        }
    )

    # 6-8. Figure slides (one per key figure, with strengths/limits)
    for entry in figures:
        slides.append(_figure_slide(entry))

    # 9. Take-home — use the quote layout
    slides.append(
        {
            "type": "quote",
            "title": "Take-home",
            "quote": take_home_quote,
            "attribution": take_home_attribution,
            "speaker_notes": {
                "hook": "The one sentence to remember.",
                "key_claim": take_home_quote,
            },
        }
    )

    # 9b. Take-home bullets (separate slide for the practical implications)
    if take_home_bullets:
        slides.append(
            {
                "type": "text",
                "title": "Practical implications for us",
                "bullets": list(take_home_bullets),
                "speaker_notes": {
                    "hook": "What we do with this.",
                    "key_claim": "Concrete take-home for the lab.",
                },
            }
        )

    # 10. Discussion prompts
    slides.append(
        {
            "type": "text",
            "title": discussion_title,
            "bullets": list(discussion_prompts),
            "speaker_notes": {
                "hook": "Open the floor.",
                "key_claim": "Guide the discussion.",
            },
        }
    )

    # 11. References
    refs = list(references) if references else [
        f"{paper_citation}. DOI: {paper_doi}"
    ]
    slides.append(
        {
            "type": "references",
            "title": "References",
            "references": refs,
        }
    )

    return {
        "title": paper_citation,
        "subtitle": f"Journal club — {presented_on}",
        "author": presenter,
        "topic": f"journal-club-{paper_doi}",
        "theme": theme,
        "template": "lab",
        "slides": slides,
    }


__all__ = [
    "READ_FIRST_PATH",
    "build_journal_club",
    "format_label_bullet",
]
