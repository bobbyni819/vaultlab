"""Dataclasses returned by the public workflow builders.

A ``WorkflowPlan`` is the single bundle every slash command consumes —
it carries the underlying ``Meeting`` configuration, the executable
``RunPlan`` (one ``AgentSpec`` per agent turn), the provenance stub for
output frontmatter, and an optional canonical output path for the
"final" file the workflow produces.

A ``DeepThinkEnsembleBundle`` packages the four phases of an ensemble-
critic deep-think (pre-critic, N critics, meta-review, synthesis) as
separate ``WorkflowPlan`` instances so callers can run them in order with
the right inter-phase wiring.

Lifted from ``bobby_ailab.workflows`` (see migration spec). Kept
behaviourally identical.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from vaultlab.runner._claude_code import RunPlan
from vaultlab.runner.models import Meeting
from vaultlab.workflows._provenance import Provenance


@dataclass
class WorkflowPlan:
    """A single bundle the slash command consumes.

    Carries both the engine ``RunPlan`` and the provenance stub so the
    command doesn't need to reconstruct either.
    """

    meeting: Meeting
    plan: RunPlan
    provenance: Provenance
    canonical_output_path: str | None = None  # e.g. synthesis-{date}.md
    notes: list[str] = field(default_factory=list)


@dataclass
class DeepThinkEnsembleBundle:
    """Structured output of ``plan_deep_think_with_ensemble_critic``.

    The bundle carries the 4 phases of an ensemble-critic deep-think as
    separate ``WorkflowPlan`` instances. Execution order (enforced by
    ``run_deep_think_with_ensemble_critic``):

        1. pre_critic   — Analyst + Expert (2-step adversarial)
        2. critic_plans — N independent Critic runs at ENSEMBLE_TEMPERATURE
                          (caller may run these in parallel)
        3. meta_review  — Area Chair aggregates the N critics (strictest wins)
        4. synthesis    — Synthesizer reads Analyst + Expert + meta-review

    Prior outputs flow between phases: the Analyst/Expert outputs seed each
    Critic's prompt; the N critic outputs seed the meta-review; the
    pre-critic + meta outputs seed the Synthesizer.
    """

    pre_critic: WorkflowPlan
    critic_plans: list[WorkflowPlan]
    meta_review: WorkflowPlan
    synthesis: WorkflowPlan

    @property
    def all_plans(self) -> list[WorkflowPlan]:
        """Flat list of every WorkflowPlan in execution order."""
        return [self.pre_critic, *self.critic_plans, self.meta_review, self.synthesis]


__all__ = ["DeepThinkEnsembleBundle", "WorkflowPlan"]
