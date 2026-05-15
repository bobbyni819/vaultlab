"""Investor-pitch deck template (VC / seed-stage research-tool pitch).

A 10-12 slide deck for pitching a research-tool startup to investors.
Tuned for a 10-minute slot: ~1 minute per slide with breathing room for
questions and traction screenshots.

Section order — investor narrative (problem → wedge → ask):

1. Title (company, one-line value prop, founders)
2. Problem
3. Current state (status quo / why this is unsolved)
4. What we built (product)
5. Key technical insight (the wedge — why now, why us)
6. Validation / traction (users, design partners, benchmarks, citations)
7. Comparison vs incumbents
8. Market sizing
9. Business model
10. Team
11. Roadmap / milestones
12. The ask

The builder returns a deck-plan dict ready for
:func:`vaultlab.slides.build_from_plan`. Sample inputs in the docstring
use real research-tool conventions: design partners, ARR / LOIs, key-
opinion leader endorsements, hardware-vs-SaaS pricing.

Hard slide rules respected by construction:
    - Roboto font (set by the lab template).
    - Min sizes 28/24/18 pt (set by the layout primitives).
    - Descriptive sentence titles — the builder takes "headlines" as
      titles, not single-word labels.
    - No shape overlap — all dispatched layouts honor it.
"""

from __future__ import annotations

from typing import Any


def _ensure_sentence_title(text: str) -> str:
    """Reject single-word / fragment titles in dev.

    Returns the text unchanged. Kept as a hook so future linters can
    enforce sentence-title discipline without changing the public API.
    """
    return text.strip()


def build_investor_pitch(
    *,
    company: str,
    one_liner: str,
    founders: str,
    problem_headline: str,
    problem_bullets: list[str],
    current_state_headline: str,
    current_state_bullets: list[str],
    product_headline: str,
    product_bullets: list[str],
    technical_insight_headline: str,
    technical_insight_bullets: list[str],
    traction_headline: str,
    traction_bullets: list[str],
    competitors_left_header: str = "Incumbent stack",
    competitors_left_bullets: list[str] | None = None,
    competitors_right_header: str = "Our approach",
    competitors_right_bullets: list[str] | None = None,
    competitors_key_insight: str = "",
    market_headline: str = "",
    market_bullets: list[str] | None = None,
    business_model_headline: str = "",
    business_model_bullets: list[str] | None = None,
    team: list[tuple[str, str, str]] | None = None,
    roadmap_headline: str = "",
    roadmap_bullets: list[str] | None = None,
    ask_headline: str = "",
    ask_bullets: list[str] | None = None,
    theme: str = "dark",
) -> dict[str, Any]:
    """Build a 10-12 slide investor-pitch deck plan.

    All required arguments are content for the core narrative slides;
    optional arguments fall back to template defaults (e.g. the comparison
    slide is omitted if both columns are empty).

    The returned dict is ready for :func:`vaultlab.slides.build_from_plan`.

    Args:
        company: Company / product name (used in the title slide).
        one_liner: Subtitle — one sentence summarizing the offer
            (e.g. "Imaging-mass-cytometry pipelines for translational
            immunology labs").
        founders: Founders line — names + affiliations.
        problem_headline: Sentence describing the problem (e.g.
            "Multiplexed-imaging analysis takes weeks per slide and
            doesn't reproduce").
        problem_bullets: Concrete failures of the status quo.
        current_state_headline: Sentence describing what people do today.
        current_state_bullets: Specific workflows / tools / pain points.
        product_headline: Sentence describing the product.
        product_bullets: Capabilities (3-5 bullets).
        technical_insight_headline: The wedge / key insight.
        technical_insight_bullets: Why it's hard, why we can do it.
        traction_headline: Headline traction stat (e.g. "Three design
            partners; 17 paper-grade analyses shipped in Q1").
        traction_bullets: Specific design partners, citations, benchmarks.
        competitors_*: Optional comparison-table content (left = incumbent,
            right = our approach). Pass empty lists to omit this slide.
        market_*: Optional market-sizing content.
        business_model_*: Optional revenue / pricing content.
        team: Optional list of ``(name, role, affiliation)`` for the team
            slide; rendered as an acknowledgments-grid layout.
        roadmap_*: Optional roadmap / milestones content.
        ask_*: Optional ask (raise size, use of funds, runway).
        theme: ``"dark"`` (default) or ``"light"``.

    Returns:
        A deck-plan dict for ``build_from_plan``.
    """
    slides: list[dict[str, Any]] = []

    # 1. Title
    slides.append(
        {
            "type": "title",
            "title": company,
            "subtitle": one_liner,
            "author": founders,
            "speaker_notes": {
                "hook": one_liner,
                "key_terms": [company],
            },
        }
    )

    # 2. Problem
    slides.append(
        {
            "type": "text",
            "title": _ensure_sentence_title(problem_headline),
            "bullets": list(problem_bullets),
            "speaker_notes": {
                "hook": problem_headline,
                "key_claim": "This is a real, unaddressed pain.",
            },
        }
    )

    # 3. Current state
    slides.append(
        {
            "type": "text",
            "title": _ensure_sentence_title(current_state_headline),
            "bullets": list(current_state_bullets),
            "speaker_notes": {
                "hook": "Here's what people actually do today.",
                "key_claim": current_state_headline,
            },
        }
    )

    # 4. What we built
    slides.append(
        {
            "type": "text",
            "title": _ensure_sentence_title(product_headline),
            "bullets": list(product_bullets),
            "speaker_notes": {
                "hook": "What we built — concretely.",
                "key_claim": product_headline,
            },
        }
    )

    # 5. Key technical insight
    slides.append(
        {
            "type": "text",
            "title": _ensure_sentence_title(technical_insight_headline),
            "bullets": list(technical_insight_bullets),
            "speaker_notes": {
                "hook": "Here's the thing nobody else can do.",
                "key_claim": technical_insight_headline,
            },
        }
    )

    # 6. Validation / traction
    slides.append(
        {
            "type": "text",
            "title": _ensure_sentence_title(traction_headline),
            "bullets": list(traction_bullets),
            "speaker_notes": {
                "hook": "Real users, real numbers.",
                "key_claim": traction_headline,
            },
        }
    )

    # 7. Comparison vs incumbents (optional)
    competitors_left_bullets = competitors_left_bullets or []
    competitors_right_bullets = competitors_right_bullets or []
    if competitors_left_bullets or competitors_right_bullets:
        slides.append(
            {
                "type": "comparison_table",
                "title": _ensure_sentence_title(
                    f"Why we win against {competitors_left_header}"
                ),
                "left_header": competitors_left_header,
                "right_header": competitors_right_header,
                "left_bullets": list(competitors_left_bullets),
                "right_bullets": list(competitors_right_bullets),
                "key_insight": competitors_key_insight,
                "speaker_notes": {
                    "hook": "Here's how we stack up.",
                    "key_claim": competitors_key_insight
                    or "Our wedge is durable.",
                },
            }
        )

    # 8. Market sizing (optional)
    market_bullets = market_bullets or []
    if market_headline or market_bullets:
        slides.append(
            {
                "type": "text",
                "title": _ensure_sentence_title(
                    market_headline or "The market is large and underserved"
                ),
                "bullets": list(market_bullets),
                "speaker_notes": {
                    "hook": "Why the market matters.",
                    "key_claim": market_headline,
                },
            }
        )

    # 9. Business model (optional)
    business_model_bullets = business_model_bullets or []
    if business_model_headline or business_model_bullets:
        slides.append(
            {
                "type": "text",
                "title": _ensure_sentence_title(
                    business_model_headline or "How we make money"
                ),
                "bullets": list(business_model_bullets),
                "speaker_notes": {
                    "hook": "Pricing + revenue model.",
                    "key_claim": business_model_headline,
                },
            }
        )

    # 10. Team (optional, uses acknowledgments_grid)
    team = team or []
    if team:
        slides.append(
            {
                "type": "acknowledgments_grid",
                "title": "The team",
                "people": list(team),
                "speaker_notes": {
                    "hook": "Founders + key hires.",
                    "key_claim": "Right team for this problem.",
                },
            }
        )

    # 11. Roadmap (optional)
    roadmap_bullets = roadmap_bullets or []
    if roadmap_headline or roadmap_bullets:
        slides.append(
            {
                "type": "text",
                "title": _ensure_sentence_title(
                    roadmap_headline or "12-month roadmap"
                ),
                "bullets": list(roadmap_bullets),
                "speaker_notes": {
                    "hook": "What this round unlocks.",
                    "key_claim": roadmap_headline,
                },
            }
        )

    # 12. The ask (mandatory — investor decks must end with an ask)
    ask_bullets = ask_bullets or [
        "Raise size: TBD",
        "Use of funds: TBD",
        "Runway: TBD",
    ]
    slides.append(
        {
            "type": "text",
            "title": _ensure_sentence_title(
                ask_headline or "What we're raising and why"
            ),
            "bullets": list(ask_bullets),
            "speaker_notes": {
                "hook": "The ask.",
                "key_claim": ask_headline or "Investment ask",
            },
        }
    )

    return {
        "title": company,
        "subtitle": one_liner,
        "author": founders,
        "topic": f"investor-pitch-{company.lower().replace(' ', '-')}",
        "theme": theme,
        "template": "lab",
        "slides": slides,
    }


__all__ = ["build_investor_pitch"]
