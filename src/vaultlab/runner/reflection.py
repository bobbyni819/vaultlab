"""Reflection loops — adopted from AI-Scientist (``generate_ideas.py:76-174``).

The pattern: ask a role to produce output, then repeatedly ask it to
refine or say "I am done". After enough iterations the role self-
terminates. Useful for:

- Idea generation (brainstorm -> refine candidates -> converge)
- Single-agent critique loops (critique -> refine critique -> done)
- Stand-alone role passes where the first draft isn't the best draft

Lifted from ``bobby_ailab._reflection`` — behaviourally identical apart
from namespace.

Example::

    from vaultlab.runner.reflection import run_with_reflection

    final_output = run_with_reflection(
        agent_fn=my_agent,
        initial_prompt="Propose 3 hypotheses for X.",
        max_reflections=5,
    )

The agent signature is the same as ``run_workflow``'s:
``(prompt, tools) -> str``. The loop terminates early when the agent's
response contains the "I am done" signal (configurable). A list of every
draft is returned via :class:`ReflectionResult` so callers can audit.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

DONE_SIGNAL_DEFAULT = "I am done"

# Accept several phrasings the model might produce
_DONE_RE = re.compile(
    r"(?i)\b(i\s+am\s+done|i['']m\s+done|no\s+further\s+refinement|nothing\s+to\s+add)\b"
)


def contains_done_signal(text: str, explicit_signal: str = DONE_SIGNAL_DEFAULT) -> bool:
    """Return ``True`` if the text contains any recognised "I am done" signal."""
    if explicit_signal.lower() in text.lower():
        return True
    return bool(_DONE_RE.search(text or ""))


# --- Non-regression guard (AI co-scientist "additive evolution": a refinement
# must never silently drop a result; Gottweis et al. 2025, arXiv:2502.18864 —
# see INSPIRATIONS.md). A refined draft is adopted only if it does not regress
# vs. the prior best on three deterministic axes: cited DOIs present, hedge-
# violation count, and numeric-consistency count.

_DOI_RE = re.compile(r"10\.\d{4,}/\S+")


def _extract_dois(text: str) -> set[str]:
    """DOIs in ``text`` with trailing punctuation stripped for stable matching."""
    return {m.rstrip(".,;:)]}'\"") for m in _DOI_RE.findall(text or "")}


def _check_regression(
    prior: str,
    candidate: str,
    *,
    check_dois: bool = True,
    check_hedge: bool = True,
    check_numeric: bool = True,
) -> list[str]:
    """Return reasons ``candidate`` regresses vs. ``prior`` (empty list = adopt).

    Reuses the existing deterministic verifiers rather than an LLM judge:
    ``roles._guardrails.enforce_hedge`` and ``runner.verifiers.verify_numeric``,
    imported lazily to avoid any import cycle at module load.
    """
    reasons: list[str] = []
    if check_dois:
        dropped = _extract_dois(prior) - _extract_dois(candidate)
        if dropped:
            reasons.append(f"dropped cited DOI(s): {', '.join(sorted(dropped))}")
    if check_hedge:
        from vaultlab.roles._guardrails import enforce_hedge

        prior_n, cand_n = len(enforce_hedge(prior)), len(enforce_hedge(candidate))
        if cand_n > prior_n:
            reasons.append(f"added unhedged claim(s) ({prior_n} -> {cand_n})")
    if check_numeric:
        from vaultlab.runner.verifiers import verify_numeric

        prior_n, cand_n = len(verify_numeric(prior)), len(verify_numeric(candidate))
        if cand_n > prior_n:
            reasons.append(f"added numeric inconsistency ({prior_n} -> {cand_n})")
    return reasons


REFLECTION_PROMPT_TEMPLATE = """\
Round {round} of {max_rounds}.

Previous draft:

{prior}

Refine the draft further, or say "I am done" if no further refinement would
improve it. Specifically:

- Tighten assumptions — name anything you hid
- Cut anything speculative
- Strengthen the strongest part; drop the weakest

If you refine, produce the full revised draft (not a diff). If you are done,
start your response with "I am done" on its own line, then briefly say why.
"""


@dataclass
class ReflectionResult:
    """Full trace of a reflection loop."""

    drafts: list[str] = field(default_factory=list)
    stopped_early: bool = False
    iterations_used: int = 0
    rejected_refinements: list[str] = field(default_factory=list)
    """Refinements blocked by the non-regression guard (reason strings); empty
    unless ``run_with_reflection(non_regression_guard=True)`` rejected a round."""

    @property
    def final(self) -> str:
        """The last non-empty draft. Empty string if nothing was produced."""
        for draft in reversed(self.drafts):
            if draft.strip():
                return draft
        return ""


def run_with_reflection(
    agent_fn: Callable[[str, list[str]], str],
    initial_prompt: str,
    max_reflections: int = 3,
    tools: list[str] | None = None,
    reflection_prompt_template: str = REFLECTION_PROMPT_TEMPLATE,
    done_signal: str = DONE_SIGNAL_DEFAULT,
    non_regression_guard: bool = False,
) -> ReflectionResult:
    """Run an agent then refine N times with early termination on "I am done".

    Parameters
    ----------
    agent_fn:
        ``(prompt, tools) -> response`` — same signature as ``run_workflow``.
    initial_prompt:
        The first prompt (already includes role system + agenda).
    max_reflections:
        Number of refinement rounds after the initial draft (so total
        agent calls = ``1 + max_reflections`` in the worst case).
    tools:
        Tool list to pass to ``agent_fn`` (defaults to ``[]``).
    reflection_prompt_template:
        Controls how refinement rounds are framed.
    done_signal:
        The string that short-circuits the loop.
    non_regression_guard:
        When ``True``, a refined draft is adopted only if it does not regress
        vs. the prior best — it must drop no cited DOI and add no unhedged claim
        or numeric inconsistency (checked with the existing ``enforce_hedge`` /
        ``verify_numeric`` verifiers). Rejected rounds are recorded in
        ``ReflectionResult.rejected_refinements`` and the prior best is kept.
        Default ``False`` preserves prior behaviour exactly. (AI co-scientist
        "additive evolution"; see INSPIRATIONS.md.)

    Returns a :class:`ReflectionResult` with every draft + stop reason.
    """
    tools = list(tools or [])
    result = ReflectionResult()

    # Round 0 — initial draft
    initial = agent_fn(initial_prompt, tools)
    result.drafts.append(initial)
    result.iterations_used = 1

    if contains_done_signal(initial, done_signal):
        result.stopped_early = True
        return result

    # Rounds 1..N — refinements
    for round_num in range(1, max_reflections + 1):
        refinement_prompt = reflection_prompt_template.format(
            round=round_num,
            max_rounds=max_reflections,
            prior=result.final,
        )
        response = agent_fn(refinement_prompt, tools)
        result.iterations_used += 1
        if non_regression_guard:
            regressions = _check_regression(result.final, response)
            if regressions:
                # Additive-evolution guard: do NOT adopt a regressing refinement;
                # keep the prior best and record why (the round still counts as an
                # agent call). A "done" signal still ends the loop.
                result.rejected_refinements.append(
                    f"round {round_num}: " + "; ".join(regressions)
                )
                if contains_done_signal(response, done_signal):
                    result.stopped_early = True
                    break
                continue
        result.drafts.append(response)
        if contains_done_signal(response, done_signal):
            result.stopped_early = True
            break

    return result


__all__ = [
    "DONE_SIGNAL_DEFAULT",
    "REFLECTION_PROMPT_TEMPLATE",
    "ReflectionResult",
    "contains_done_signal",
    "run_with_reflection",
]
