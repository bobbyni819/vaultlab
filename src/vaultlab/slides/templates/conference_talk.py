"""Conference-talk deck template (12 min talk + 3 min Q&A).

12-15 slides for a standard biomedical / comp-bio conference talk
(e.g. AACR, ISMB, ICML for ML-bio, BMES). Mirrors the manuscript arc but
*not* the manuscript section order — the talk's job is to land one claim
backed by 4-6 results figures.

Structure:

1. Title (talk title, authors, affiliations, conference)
2. Motivation (why this matters, in one sentence + 3 bullets)
3. Prior work (what the field has tried)
4. Gap (what's still missing — the talk's wedge)
5. Approach overview (methods at a glance — one figure)
6-10. Results (4-6 figure slides, each driving a single claim)
11. Synthesis / model (the take-home figure or schematic)
12. Limits and what's next
13. Conclusions (3-4 sentence-style bullets)
14. Acknowledgments (grid)
15. References (auto)

Hard slide rules:
    - Roboto, 28/24/18 mins.
    - Descriptive sentence titles (caller passes "headlines").
    - No shape overlap.
"""

from __future__ import annotations

from typing import Any


def _result_slide(entry: dict[str, Any]) -> dict[str, Any]:
    """Convert a result entry into a figure or text slide spec.

    Entry keys:
        - ``title`` (required): headline (one sentence claim).
        - ``figure`` / ``image_path`` (optional but recommended for talks).
        - ``caption``, ``bullets``, ``citation``, ``notes`` — passthrough.
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


def build_conference_talk(
    *,
    talk_title: str,
    authors: str,
    conference: str,
    motivation_headline: str,
    motivation_bullets: list[str],
    prior_work_headline: str,
    prior_work_bullets: list[str],
    gap_headline: str,
    gap_bullets: list[str],
    approach_entry: dict[str, Any],
    results_entries: list[dict[str, Any]],
    synthesis_entry: dict[str, Any] | None = None,
    limits_headline: str = "",
    limits_bullets: list[str] | None = None,
    conclusions_bullets: list[str] | None = None,
    acknowledgments: list[tuple[str, str, str]] | None = None,
    references: list[str] | None = None,
    theme: str = "dark",
) -> dict[str, Any]:
    """Build a 12-15 slide conference-talk deck plan.

    Args:
        talk_title: Talk title (sentence-style, descriptive).
        authors: Authors + affiliations line.
        conference: Conference + date (e.g. "ISMB 2026, Berkeley").
        motivation_headline: One-sentence motivation
            (e.g. "Single-cell spatial-proteomics analysis is the
            rate-limiting step in translational immunology").
        motivation_bullets: 3-4 supporting bullets.
        prior_work_headline: Sentence summarizing what's been done.
        prior_work_bullets: 3-5 prior-work bullets (cite shorthand:
            "Goltsev 2018", "Schurch 2020").
        gap_headline: The wedge — what's still missing.
        gap_bullets: 2-4 bullets making the gap concrete.
        approach_entry: Methods-at-a-glance slide spec (see
            :func:`_result_slide`). Should reference your method figure.
        results_entries: 4-6 result-slide specs (each with a figure).
        synthesis_entry: Optional take-home figure / model schematic.
        limits_headline / limits_bullets: Limits + future-work content.
        conclusions_bullets: 3-4 conclusion-statement bullets.
        acknowledgments: ``[(name, role, affiliation)]`` for the closing
            grid slide.
        references: Optional reference list.
        theme: ``"dark"`` (default) or ``"light"``.

    Returns:
        Deck-plan dict for :func:`vaultlab.slides.build_from_plan`.
    """
    if not results_entries:
        raise ValueError(
            "conference_talk requires at least one results entry"
        )

    slides: list[dict[str, Any]] = []

    # 1. Title
    slides.append(
        {
            "type": "title",
            "title": talk_title,
            "subtitle": conference,
            "author": authors,
            "speaker_notes": {
                "hook": talk_title,
                "key_terms": [conference],
            },
        }
    )

    # 2. Motivation
    slides.append(
        {
            "type": "text",
            "title": motivation_headline,
            "bullets": list(motivation_bullets),
            "speaker_notes": {
                "hook": "Why this matters.",
                "key_claim": motivation_headline,
            },
        }
    )

    # 3. Prior work
    slides.append(
        {
            "type": "text",
            "title": prior_work_headline,
            "bullets": list(prior_work_bullets),
            "speaker_notes": {
                "hook": "What's been done.",
                "key_claim": prior_work_headline,
            },
        }
    )

    # 4. Gap
    slides.append(
        {
            "type": "text",
            "title": gap_headline,
            "bullets": list(gap_bullets),
            "speaker_notes": {
                "hook": "What's missing.",
                "key_claim": gap_headline,
            },
        }
    )

    # 5. Approach overview
    slides.append(_result_slide(approach_entry))

    # 6-10. Results (4-6 slides)
    for entry in results_entries:
        slides.append(_result_slide(entry))

    # 11. Synthesis / model (optional)
    if synthesis_entry is not None:
        slides.append(_result_slide(synthesis_entry))

    # 12. Limits + what's next (optional)
    limits_bullets = limits_bullets or []
    if limits_headline or limits_bullets:
        slides.append(
            {
                "type": "text",
                "title": limits_headline or "Limits and what's next",
                "bullets": list(limits_bullets),
                "speaker_notes": {
                    "hook": "Where it breaks.",
                    "key_claim": "Be honest about limits.",
                },
            }
        )

    # 13. Conclusions
    conclusions_bullets = conclusions_bullets or [
        "Result 1 in one sentence.",
        "Result 2 in one sentence.",
        "Takeaway in one sentence.",
    ]
    slides.append(
        {
            "type": "text",
            "title": "Conclusions",
            "bullets": list(conclusions_bullets),
            "speaker_notes": {
                "hook": "The take-home.",
                "key_claim": "What I want you to remember.",
            },
        }
    )

    # 14. Acknowledgments
    acknowledgments = acknowledgments or []
    if acknowledgments:
        slides.append(
            {
                "type": "acknowledgments_grid",
                "title": "Acknowledgments",
                "people": list(acknowledgments),
                "speaker_notes": {
                    "hook": "Co-authors and funders.",
                    "key_claim": "Thanks.",
                },
            }
        )

    # 15. References
    references = references or []
    if references:
        slides.append(
            {
                "type": "references",
                "title": "References",
                "references": list(references),
            }
        )

    return {
        "title": talk_title,
        "subtitle": conference,
        "author": authors,
        "topic": "conference-talk",
        "theme": theme,
        "template": "lab",
        "slides": slides,
    }


__all__ = ["build_conference_talk"]
