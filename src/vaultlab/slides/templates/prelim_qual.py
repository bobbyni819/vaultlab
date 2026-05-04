"""PhD prelim / qualifying-exam deck template.

Canonical 30-35 slide structure for a 30-45 minute prelim talk + 30-45
minute committee Q&A. Adds a fourth speaker-notes tier
(``committee_qa``) for pre-rehearsed answers to anticipated questions.

The outline places section dividers between Aims, with a roadmap slide
near the front that the speaker returns to between sections (committee
needs to see structure).

Usage::

    from vaultlab.slides.templates.prelim_qual import build_outline, AimSpec

    plan = build_outline(
        title="Multiscale tissue simulation for lung infection",
        subtitle="PhD Preliminary Exam",
        speaker="Bobby Y.X. Ni",
        advisor="John W. Hickey",
        committee=["Chair Smith", "Member Jones", "Member Brown", "Member Lee"],
        program="Biomedical Engineering",
        institution="Duke University",
        date="2026-06-15",
        big_problem="Lung infection lacks a multiscale-modeling stack",
        thesis_question="Can CODEX × Vivarium × ABM be translated to lung infection?",
        background_slides=[...],  # list of figure slide_specs
        aims=[
            AimSpec(
                number=1,
                title="Validate the alveolus ABM against CODEX ground truth",
                aim_statement="...",
                approach="...",
                preliminary_results=[...],
                expected_outcomes="...",
                anticipated_challenges="...",
            ),
            ...
        ],
        timeline=[...],
        broader_impacts="...",
        acknowledgments=[...],
        references=[...],
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


_DEFAULT_DURATION_MIN = 35  # talk portion before Q&A


@dataclass
class AimSpec:
    """One Specific Aim for the prelim."""

    number: int
    title: str          # short descriptive ("Aim 1: Validate ...")
    aim_statement: str  # 1-2 sentence formal aim
    approach: str       # how you'll do it
    preliminary_results: list[dict[str, Any]] = field(default_factory=list)
    """List of figure slide_specs for preliminary data showing this aim is feasible."""
    expected_outcomes: str = ""
    anticipated_challenges: str = ""
    success_criteria: str = ""


@dataclass
class CommitteeQA:
    """One pre-rehearsed committee question + answer."""

    question: str  # how the member would actually phrase it
    answer: str    # 1-2 sentence rehearsed reply
    member: str = "any"  # name of likely asker, or "any"
    references: list[str] = field(default_factory=list)


def _committee_qa_str(qas: list[CommitteeQA]) -> str:
    """Render Q&A bank into a speaker-notes appendix string."""
    if not qas:
        return ""
    out = ["", "", "--- COMMITTEE Q&A ANTICIPATOR ---", ""]
    for qa in qas:
        out.append(f"Q ({qa.member}): {qa.question}")
        out.append(f"A: {qa.answer}")
        if qa.references:
            out.append(f"   refs: {', '.join(qa.references)}")
        out.append("")
    return "\n".join(out)


def _title_slide(
    title: str,
    subtitle: str,
    speaker: str,
    advisor: str,
    committee: list[str],
    institution: str,
    program: str,
    date: str,
) -> dict[str, Any]:
    members = " · ".join(committee) if committee else ""
    body_lines = [
        f"{speaker}",
        f"Advisor: {advisor}",
        f"Committee: {members}" if members else "",
        f"{program}, {institution}" if program or institution else institution,
        date,
    ]
    body = "\n".join(line for line in body_lines if line)
    return {
        "type": "title",
        "title": title,
        "subtitle": subtitle,
        "author": body,
        "speaker_notes": {
            "hook": "Open with the title; set the room's expectations.",
            "key_claim": title,
            "transition": "Acknowledge the committee briefly, then walk the roadmap.",
        },
    }


def _committee_ack_slide(committee: list[str], advisor: str) -> dict[str, Any]:
    bullets = [f"Advisor: {advisor}"] + [f"Member: {m}" for m in committee]
    return {
        "type": "text",
        "title": "Thank you to my committee",
        "bullets": bullets,
        "speaker_notes": {
            "hook": "Acknowledge committee in the room.",
            "key_claim": "I'm grateful for committee guidance and Q&A engagement.",
            "transition": "Now the roadmap for today's talk.",
            "_estimated_minutes": 0.5,
        },
    }


def _roadmap_slide(
    aims: list[AimSpec],
    background_count: int,
) -> dict[str, Any]:
    bullets = [
        f"1. Background — the field's lineage ({background_count} slides)",
        "2. Thesis question — the empty cell of the matrix",
    ]
    for aim in aims:
        bullets.append(f"{aim.number + 2}. Aim {aim.number}: {aim.title.split(':')[-1].strip()[:60]}")
    bullets.append(f"{len(aims) + 3}. Anticipated challenges + timeline + broader impacts")
    return {
        "type": "text",
        "title": "Roadmap for today",
        "bullets": bullets,
        "speaker_notes": {
            "hook": "Quick map. I'll come back to this between sections.",
            "key_claim": "Three Aims, framed by a background lineage and a thesis question.",
            "transition": "Background first.",
            "_estimated_minutes": 1.0,
        },
    }


def _aim_section_divider(aim: AimSpec) -> dict[str, Any]:
    return {
        "type": "section_divider",
        "title": f"Aim {aim.number}: {aim.title.split(':')[-1].strip()}",
    }


def _aim_statement_slide(aim: AimSpec) -> dict[str, Any]:
    bullets = []
    if aim.approach:
        bullets.append(f"Approach: {aim.approach}")
    if aim.expected_outcomes:
        bullets.append(f"Expected: {aim.expected_outcomes}")
    if aim.success_criteria:
        bullets.append(f"Success: {aim.success_criteria}")
    return {
        "type": "text",
        "title": aim.title,
        "bullets": [aim.aim_statement] + bullets,
        "speaker_notes": {
            "hook": f"Aim {aim.number} statement — hold on this slide for ~30 seconds.",
            "key_claim": aim.aim_statement,
            "transition": f"Now the preliminary work for Aim {aim.number}.",
            "_estimated_minutes": 1.0,
        },
    }


def _challenges_slide(aims: list[AimSpec]) -> dict[str, Any]:
    bullets = []
    for aim in aims:
        if aim.anticipated_challenges:
            bullets.append(f"Aim {aim.number}: {aim.anticipated_challenges[:90]}")
    if not bullets:
        bullets = ["Listed per-aim above; happy to discuss specific risks."]
    return {
        "type": "text",
        "title": "Anticipated challenges and mitigations",
        "bullets": bullets,
        "speaker_notes": {
            "hook": "Pre-empt committee challenge questions here.",
            "key_claim": "Each aim has a known risk; I have alternatives planned.",
            "transition": "Timeline now.",
            "_estimated_minutes": 2.0,
        },
    }


def _timeline_slide(timeline: list[dict[str, Any]]) -> dict[str, Any]:
    if not timeline:
        bullets = ["Timeline TBD — see thesis prospectus draft."]
    else:
        bullets = [f"{t.get('date', '?')}: {t.get('milestone', '?')}" for t in timeline]
    return {
        "type": "text",
        "title": "Timeline + milestones",
        "bullets": bullets,
        "speaker_notes": {
            "hook": "Concrete dates — committee likes to see realism.",
            "key_claim": "Plan is achievable in the remaining program window.",
            "transition": "Broader impacts.",
            "_estimated_minutes": 1.5,
        },
    }


def _broader_impacts_slide(text: str) -> dict[str, Any]:
    return {
        "type": "text",
        "title": "Broader impacts",
        "bullets": [b.strip() for b in text.split("\n") if b.strip()][:5],
        "speaker_notes": {
            "hook": "Why this work matters beyond the dissertation.",
            "key_claim": "Methods generalise; results inform clinical/translational direction.",
            "transition": "Acknowledgments + thanks.",
            "_estimated_minutes": 1.0,
        },
    }


def _acknowledgments_slide(acks: list[str]) -> dict[str, Any]:
    return {
        "type": "text",
        "title": "Acknowledgments",
        "bullets": acks or ["Lab + collaborators + funding listed in handout."],
        "speaker_notes": {
            "hook": "Quick thanks — keep brief.",
            "key_claim": "Lab + collaborators + funding made this possible.",
            "transition": "Open for questions.",
            "_estimated_minutes": 0.5,
        },
    }


def build_outline(
    *,
    title: str,
    subtitle: str = "PhD Preliminary Examination",
    speaker: str,
    advisor: str,
    committee: list[str] | None = None,
    program: str = "",
    institution: str = "",
    date: str = "",
    big_problem: str = "",
    thesis_question: str = "",
    background_slides: list[dict[str, Any]] | None = None,
    aims: list[AimSpec] | None = None,
    timeline: list[dict[str, Any]] | None = None,
    broader_impacts: str = "",
    acknowledgments: list[str] | None = None,
    references: list[str] | None = None,
    target_minutes: int = _DEFAULT_DURATION_MIN,
) -> dict[str, Any]:
    """Build a prelim/qual deck plan dict.

    Returns a plan ready for ``vaultlab.slides.deck.build_from_plan``.
    """
    committee = committee or []
    background_slides = background_slides or []
    aims = aims or []
    timeline = timeline or []
    acknowledgments = acknowledgments or []
    references = references or []

    slides: list[dict[str, Any]] = []

    # Front matter
    slides.append(_title_slide(
        title=title, subtitle=subtitle, speaker=speaker, advisor=advisor,
        committee=committee, institution=institution, program=program, date=date,
    ))
    slides.append(_committee_ack_slide(committee, advisor))
    slides.append(_roadmap_slide(aims, len(background_slides)))

    # Big-picture motivation
    if big_problem:
        slides.append({
            "type": "text",
            "title": big_problem[:80],
            "bullets": [],
            "speaker_notes": {
                "hook": "Open with the big-picture problem.",
                "key_claim": big_problem,
                "transition": "Background — how the field got here.",
                "_estimated_minutes": 1.5,
            },
        })

    # Background lineage
    slides.append({"type": "section_divider", "title": "Background"})
    slides.extend(background_slides)

    # Thesis question
    if thesis_question:
        slides.append({
            "type": "text",
            "title": "The thesis question",
            "bullets": [thesis_question],
            "speaker_notes": {
                "hook": "Slow down — committee takes notes here.",
                "key_claim": thesis_question,
                "transition": f"Three aims address this. Aim 1 first.",
                "_estimated_minutes": 1.5,
            },
        })

    # Aims
    for aim in aims:
        slides.append(_aim_section_divider(aim))
        slides.append(_aim_statement_slide(aim))
        slides.extend(aim.preliminary_results)

    # Closing matter
    slides.append({"type": "section_divider", "title": "Wrap-up"})
    slides.append(_challenges_slide(aims))
    slides.append(_timeline_slide(timeline))
    if broader_impacts:
        slides.append(_broader_impacts_slide(broader_impacts))
    slides.append(_acknowledgments_slide(acknowledgments))
    if references:
        slides.append({
            "type": "references",
            "title": "References",
            "references": references,
        })

    return {
        "title": title,
        "subtitle": subtitle,
        "topic": f"prelim-{speaker.lower().replace(' ', '-')}",
        "author": speaker,
        "kb": "vaultlab",
        "theme": "dark",
        "template": "plain",
        "_use_case": "prelim_qual",
        "_target_minutes": target_minutes,
        "slides": slides,
    }


def attach_committee_qa(
    slide_spec: dict[str, Any],
    qas: list[CommitteeQA],
) -> dict[str, Any]:
    """Append a committee Q&A bank to a slide's extended_walkthrough.

    Returns a NEW slide_spec with committee_qa appended. Used to load
    pre-rehearsed answers to anticipated questions for any content slide.
    """
    new_spec = dict(slide_spec)
    notes = dict(new_spec.get("speaker_notes") or {})
    walk = notes.get("extended_walkthrough", "")
    notes["extended_walkthrough"] = walk + _committee_qa_str(qas)
    new_spec["speaker_notes"] = notes
    return new_spec


__all__ = [
    "AimSpec",
    "CommitteeQA",
    "attach_committee_qa",
    "build_outline",
]
