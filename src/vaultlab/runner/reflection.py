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
from dataclasses import dataclass, field
from typing import Callable, Optional


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
    tools: Optional[list[str]] = None,
    reflection_prompt_template: str = REFLECTION_PROMPT_TEMPLATE,
    done_signal: str = DONE_SIGNAL_DEFAULT,
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
        result.drafts.append(response)
        result.iterations_used += 1
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
