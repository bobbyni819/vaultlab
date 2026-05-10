"""Numeric-rubric scoring for ensemble critic synthesis.

Background
----------
Pattern lifted from AI-Scientist's `perform_review.py:160-192`: when an
ensemble of critics scores the same artifact (a draft paragraph, a
deck plan, a hypothesis), aggregating their scores via plain mean
**hides the failure mode the ensemble was supposed to catch**.

If 4 of 5 reviewers say "Soundness 4" and 1 says "Soundness 1",
the mean is `int(round(np.mean([4,4,4,4,1])))` = 3, which the
synthesizer then takes as a "decent score." The dissenter's fatal-flaw
signal is averaged out. AI-Scientist itself has this anti-pattern:
they roll reviewers at temperature=0.75 "to encourage diversity" and
then collapse to int-mean.

Vaultlab's contribution: aggregate as **mean ± spread** so the
synthesizer always sees both the central tendency AND the range. A
4-vs-1 split shows up as `mean=3.4, range=[1,4], spread=1.5` and the
synthesizer is forced to address the dissent rather than ignore it.

Design
------

* :class:`RubricItem` — one rubric dimension (name, description,
  scale typically 1-5).
* :class:`DEFAULT_METHODS_RUBRIC` — the 9-item rubric we lift from
  AI-Scientist (originality, soundness, significance, presentation,
  contribution, overall) plus 3 domain-specific items
  (provenance, novelty-vs-prior-work, claim-evidence-fit).
* :class:`RubricScore` — one critic's per-item scores + free-text
  rationale.
* :class:`RubricEnsembleScore` — aggregate across critics: mean,
  spread (max - min), all individual scores preserved, dissent flag.
* :func:`aggregate_rubric_scores(scores)` — produces the ensemble
  score with the anti-pattern guard.

Used by callers that wire a rubric into the methods_critic role
(via a custom prompt). The rubric primitive itself is callback-shape-
neutral; you can use it for any role that emits structured numeric
scores.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "DEFAULT_METHODS_RUBRIC",
    "RubricEnsembleScore",
    "RubricItem",
    "RubricScore",
    "aggregate_rubric_scores",
    "rubric_section_for_prompt",
]


# ---------------------------------------------------------------------------
# Rubric definition
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RubricItem:
    """One rubric dimension.

    Attributes:
        id: Snake_case key used in the JSON response.
        title: Human-readable label.
        description: What this dimension means; used in the LLM prompt.
        min_score: Lower bound (typically 1).
        max_score: Upper bound (typically 5).
    """

    id: str
    title: str
    description: str
    min_score: int = 1
    max_score: int = 5


# 9-item rubric — 6 lifted from the AI-Scientist convention plus 3 domain
# items more relevant to vaultlab's research-claim setting.
DEFAULT_METHODS_RUBRIC: tuple[RubricItem, ...] = (
    RubricItem(
        "originality",
        "Originality",
        "Does this contribution add a meaningfully new claim, method, "
        "or framing — or just restate prior work?",
    ),
    RubricItem(
        "soundness",
        "Soundness",
        "Are the methods + reasoning rigorous? Would a knowledgeable "
        "reviewer in the field find the argument defensible?",
    ),
    RubricItem(
        "significance",
        "Significance",
        "If correct, does this materially advance understanding? Or is "
        "it incremental polish on an already-settled question?",
    ),
    RubricItem(
        "presentation",
        "Presentation",
        "Is the writing clear, well-organized, and appropriate for the "
        "intended audience? Does the structure aid comprehension?",
    ),
    RubricItem(
        "contribution",
        "Contribution",
        "Synthesis of originality + significance — the headline question: "
        "is this worth the reader's time?",
    ),
    RubricItem(
        "overall",
        "Overall",
        "All-things-considered score. Reviewers should converge here only "
        "after scoring the specific dimensions above.",
    ),
    # Domain-specific (vaultlab-flavored)
    RubricItem(
        "provenance",
        "Provenance integrity",
        "Are claims grounded in cited sources with [pN] anchors or "
        "verifiable references? Or do claims float free?",
    ),
    RubricItem(
        "novelty_vs_prior_work",
        "Novelty vs. prior work",
        "Does the synthesis correctly position itself relative to the "
        "lineage's existing work — or does it overclaim novelty by "
        "ignoring nearby prior art?",
    ),
    RubricItem(
        "claim_evidence_fit",
        "Claim-evidence fit",
        "Are the claims appropriately scaled to the evidence? Or are "
        "they stronger / weaker than what the cited work supports?",
    ),
)


# ---------------------------------------------------------------------------
# Score data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RubricScore:
    """One critic's scores across the rubric.

    Attributes:
        critic_id: Identifier for the critic that produced this score
            (e.g. ``"methods_critic_1"``).
        scores: ``rubric_item_id -> int`` mapping. Missing items
            (the critic skipped a dimension) are absent rather than 0.
        rationale: Free-text rationale for the scores. Optional; some
            critics prefer to keep their reasoning out of the structured
            response.
    """

    critic_id: str
    scores: dict[str, int]
    rationale: str = ""


@dataclass(frozen=True)
class RubricEnsembleScore:
    """Aggregated score across an ensemble of critics.

    Attributes:
        per_item: Item id → aggregate stats (``mean``, ``min``, ``max``,
            ``spread`` = max - min, ``stdev``, ``all_scores``).
        n_critics: How many critics contributed.
        dissent_flagged: Items where ``spread >= 2`` (i.e. at least one
            critic disagreed by 2+ points). Surfaces the anti-pattern
            guard — "this looks like a clean mean, but actually one
            critic gave it a 1 while the others gave it a 4."
        per_critic: Original :class:`RubricScore` list, preserved so
            the synthesizer can drill into the dissenting critic's
            rationale rather than relying on the aggregate.
    """

    per_item: dict[str, dict[str, Any]] = field(default_factory=dict)
    n_critics: int = 0
    dissent_flagged: list[str] = field(default_factory=list)
    per_critic: list[RubricScore] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Aggregation (with anti-pattern guard)
# ---------------------------------------------------------------------------


def aggregate_rubric_scores(
    scores: list[RubricScore],
    *,
    rubric: tuple[RubricItem, ...] = DEFAULT_METHODS_RUBRIC,
    dissent_threshold: int = 2,
) -> RubricEnsembleScore:
    """Aggregate ensemble critic scores with mean ± spread reporting.

    The critical design decision: this function preserves the spread.
    Callers that just want the mean still get it, but the spread is
    always present alongside, so a 4-vs-1 disagreement can never be
    silently averaged out.

    Args:
        scores: List of per-critic :class:`RubricScore` objects.
            Empty list → empty ensemble (n_critics=0).
        rubric: The rubric definition (default
            :data:`DEFAULT_METHODS_RUBRIC`). Determines which item ids
            are considered. Items not in the rubric are silently ignored
            in individual scores; items in the rubric that no critic
            scored show up as empty stats.
        dissent_threshold: Spread (max - min) >= threshold → item is
            flagged in ``dissent_flagged``. Default 2 (i.e. one critic
            gave a 1 while another gave a 3+).

    Returns:
        A populated :class:`RubricEnsembleScore`.
    """
    valid_ids = {item.id for item in rubric}

    per_item: dict[str, dict[str, Any]] = {}
    dissent: list[str] = []

    for item in rubric:
        item_scores: list[int] = []
        for s in scores:
            v = s.scores.get(item.id)
            if v is None:
                continue
            try:
                item_scores.append(int(v))
            except (TypeError, ValueError):
                continue
        if not item_scores:
            per_item[item.id] = {
                "mean": None,
                "min": None,
                "max": None,
                "spread": None,
                "stdev": None,
                "all_scores": [],
            }
            continue
        mean = round(statistics.fmean(item_scores), 2)
        lo = min(item_scores)
        hi = max(item_scores)
        spread = hi - lo
        stdev = round(statistics.pstdev(item_scores), 2) if len(item_scores) > 1 else 0.0
        per_item[item.id] = {
            "mean": mean,
            "min": lo,
            "max": hi,
            "spread": spread,
            "stdev": stdev,
            "all_scores": list(item_scores),
        }
        if spread >= int(dissent_threshold):
            dissent.append(item.id)

    return RubricEnsembleScore(
        per_item=per_item,
        n_critics=len(scores),
        dissent_flagged=dissent,
        per_critic=list(scores),
    )


# ---------------------------------------------------------------------------
# Prompt fragment helper
# ---------------------------------------------------------------------------


def rubric_section_for_prompt(
    rubric: tuple[RubricItem, ...] = DEFAULT_METHODS_RUBRIC,
) -> str:
    """Render the rubric as a markdown block for embedding in a critic's prompt.

    Returned text is suitable for splicing into a methods_critic system
    prompt — explains what each dimension means and asks the critic to
    return a JSON object with one int per dimension.
    """
    lines: list[str] = [
        "## Rubric",
        "",
        f"Score the artifact on these {len(rubric)} dimensions, each on a "
        f"{rubric[0].min_score}-{rubric[0].max_score} scale:",
        "",
    ]
    for item in rubric:
        lines.append(
            f"- **{item.id}** ({item.title}, {item.min_score}-{item.max_score}): {item.description}"
        )
    lines.extend(
        [
            "",
            "Return your scores as JSON:",
            "",
            "```json",
            "{",
            '  "scores": {',
        ]
    )
    for item in rubric[:3]:
        lines.append(f'    "{item.id}": <int>,')
    lines.append("    ...")
    lines.append("  },")
    lines.append('  "rationale": "<2-3 sentences explaining the scores>"')
    lines.append("}")
    lines.append("```")
    lines.append("")
    lines.append(
        "Score independently — do NOT calibrate to other critics' likely "
        "scores. Honest dissent is more valuable than artificial consensus. "
        "If you think one dimension is fatally flawed (score 1) while "
        "others are fine, say 1 — the synthesizer will see the spread and "
        "investigate."
    )
    return "\n".join(lines)
