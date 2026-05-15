"""Lab-meeting deck template (weekly progress update).

7-10 slides for a 20-30 minute weekly lab meeting (including
discussion). Pattern follows Hickey-lab convention:

1. Title (project, week-of, presenter)
2. Last-week recap (what we said we'd do; what we actually did)
3-5. This-week progress (one slide per result, ideally with a figure)
6. Open questions (the *real* meeting content — what to discuss)
7. Next-week plan (what we'll do, what we'd need)
8. Asks (what the lab can help with — reagents, advice, time)

The "progress" section is variable-length: pass 3-5 progress entries.
Each progress entry can be a figure slide (with image_path + caption +
bullets) or a text slide (when there's no figure yet).

Hard slide rules:
    - Roboto, 28/24/18 min sizes (layout primitives enforce).
    - Sentence-style titles encouraged (the builder takes "headlines",
      not labels).
    - No shape overlap.
"""

from __future__ import annotations

from typing import Any


def _progress_slide(entry: dict[str, Any]) -> dict[str, Any]:
    """Turn a progress entry into a slide spec.

    A progress entry is a dict with:
        - ``title`` (required): sentence headline for the result.
        - ``bullets`` (optional): list of takeaway bullets.
        - ``figure`` (optional): path to a result figure.
        - ``caption`` (optional): figure caption.
        - ``citation`` (optional): citation source for the figure.
        - ``notes`` (optional): speaker-notes dict.
    """
    title = entry.get("title", "")
    bullets = entry.get("bullets") or []
    figure = entry.get("figure") or entry.get("image_path")
    caption = entry.get("caption", "")
    citation = entry.get("citation") or entry.get("citation_source", "")
    notes = entry.get("notes") or {
        "hook": title,
        "key_claim": caption or title,
    }

    if figure:
        return {
            "type": "figure",
            "title": title,
            "image_path": str(figure),
            "caption": caption,
            "bullets": list(bullets),
            "citation_source": citation,
            "speaker_notes": notes,
        }
    return {
        "type": "text",
        "title": title,
        "bullets": list(bullets),
        "speaker_notes": notes,
    }


def build_lab_meeting(
    *,
    project: str,
    week_of: str,
    presenter: str,
    recap_bullets: list[str],
    progress_entries: list[dict[str, Any]],
    open_questions: list[str],
    next_week_bullets: list[str],
    ask_bullets: list[str] | None = None,
    recap_title: str = "",
    next_week_title: str = "",
    asks_title: str = "",
    theme: str = "dark",
) -> dict[str, Any]:
    """Build a 7-10 slide weekly lab-meeting deck plan.

    Args:
        project: Project / arc name (e.g. "Phospholipid programs in IBD").
        week_of: Week-of label (e.g. "Week of 2026-05-12").
        presenter: Presenter line (e.g. "Bobby Ni").
        recap_bullets: Last week's commitments + outcomes. Each bullet
            should pair a commitment with what actually happened
            (e.g. "Said: re-run B12 donor with new mask. Did: done,
            mask flagged 3 misregistered ROIs").
        progress_entries: 3-5 progress dicts (see ``_progress_slide``).
            Each becomes one figure or text slide.
        open_questions: Discussion-prompts for the lab — 2-5 bullets.
            These drive the meeting; keep them concrete.
        next_week_bullets: 3-5 next-week deliverables.
        ask_bullets: Optional asks (reagent, reagent prep, time, advice).
        recap_title: Optional override for the recap-slide title.
        next_week_title: Optional override for the next-week-slide title.
        asks_title: Optional override for the asks-slide title.
        theme: ``"dark"`` (default) or ``"light"``.

    Returns:
        A deck-plan dict for :func:`vaultlab.slides.build_from_plan`.
    """
    if not progress_entries:
        raise ValueError(
            "lab_meeting requires at least one progress entry — "
            "the whole point of the meeting"
        )

    slides: list[dict[str, Any]] = []

    # 1. Title
    slides.append(
        {
            "type": "title",
            "title": project,
            "subtitle": f"Lab meeting — {week_of}",
            "author": presenter,
            "speaker_notes": {
                "hook": f"Weekly update on {project}.",
                "key_terms": [project],
            },
        }
    )

    # 2. Last-week recap
    slides.append(
        {
            "type": "text",
            "title": recap_title or "Last week — what we said vs what we did",
            "bullets": list(recap_bullets),
            "speaker_notes": {
                "hook": "Where we left off.",
                "key_claim": "Commitments and outcomes.",
            },
        }
    )

    # 3-5. Progress slides
    for entry in progress_entries:
        slides.append(_progress_slide(entry))

    # 6. Open questions (discussion driver)
    slides.append(
        {
            "type": "text",
            "title": "Open questions for discussion",
            "bullets": list(open_questions),
            "speaker_notes": {
                "hook": "Where I need help thinking.",
                "key_claim": "These are the live questions.",
            },
        }
    )

    # 7. Next-week plan
    slides.append(
        {
            "type": "text",
            "title": next_week_title or "Plan for next week",
            "bullets": list(next_week_bullets),
            "speaker_notes": {
                "hook": "Next week's commitments.",
                "key_claim": "What I'll bring back.",
            },
        }
    )

    # 8. Asks (optional but recommended)
    ask_bullets = ask_bullets or []
    if ask_bullets:
        slides.append(
            {
                "type": "text",
                "title": asks_title or "Asks for the lab",
                "bullets": list(ask_bullets),
                "speaker_notes": {
                    "hook": "Here's where the lab can help.",
                    "key_claim": "Concrete asks.",
                },
            }
        )

    return {
        "title": project,
        "subtitle": f"Lab meeting — {week_of}",
        "author": presenter,
        "topic": f"lab-meeting-{week_of}",
        "theme": theme,
        "template": "lab",
        "slides": slides,
    }


__all__ = ["build_lab_meeting"]
