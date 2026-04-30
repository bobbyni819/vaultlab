"""vaultlab.workflows — composable agent-meeting builders.

A "workflow" packages a multi-role meeting into a structured plan that a
slash command (or Python script) can execute. Each public builder
returns a :class:`WorkflowPlan` (or a small bundle of them); callers
hand each plan to :func:`run_workflow` along with an ``agent_fn`` that
spawns the actual LLM calls.

Public builders
---------------

* :func:`plan_deep_think_round` — Analyst + Expert + Critic + Synthesizer
  (one round of the classic deep-think cycle)
* :func:`plan_round_from_critic_tests` — auto-build round N+1 agenda from
  prior round's Critic priorities
* :func:`plan_synthesis` — Synthesizer alone over existing findings
* :func:`plan_brainstorm_figures` — FigureLead + Critic propose figure plan
* :func:`plan_narrate_finding` — Narrator writes one finding's KB page
* :func:`plan_lit_dive` — Literature Surveyor over paperclip stateful workflow
* :func:`plan_parallel_runs` — N independent deep-thinks + Synthesizer merge
* :func:`plan_ensemble_critic` — N critics + Area Chair meta-reviewer
* :func:`plan_deep_think_with_ensemble_critic` — pre-critic + N critics +
  meta-review + synthesis bundle
* :func:`run_deep_think_with_ensemble_critic` — execute the bundle

Runners
-------

* :func:`run_workflow` — straight-line execute every step
* :func:`run_workflow_with_reflection` — wrap final step in a self-refine loop

Data classes
------------

* :class:`WorkflowPlan` — what every public builder returns
* :class:`DeepThinkEnsembleBundle` — the four-phase ensemble bundle
* :class:`Provenance` — frontmatter receipt written above each output

Lifted from ``bobby_ailab.workflows`` (1083 LOC). Kept behaviourally
identical — adapter notes for cross-namespace dependencies live as
``TODO`` markers in the per-builder files (``deep_think.py``,
``ensemble.py``, ``_runner.py``).
"""

from __future__ import annotations

# Data classes
from vaultlab.workflows._models import DeepThinkEnsembleBundle, WorkflowPlan
from vaultlab.workflows._provenance import (
    PROVENANCE_INDEX,
    Provenance,
    read_provenance,
    write_with_provenance,
)

# Runners
from vaultlab.workflows._runner import (
    run_workflow,
    run_workflow_with_reflection,
)

# Public builders
from vaultlab.workflows.brainstorm import plan_brainstorm_figures
from vaultlab.workflows.crosstalk import (
    CrosstalkResult,
    MAX_N_ROUNDS,
    MEETING_TIMEOUT_SECONDS,
    RunnerCallback,
    adversarial_arc_meeting,
    adversarial_deck_plan_meeting,
    adversarial_picker_meeting,
    append_decisions_log_entry,
    rigor_audit,
    write_crosstalk_artifacts,
)
from vaultlab.workflows.deck_plan import (
    DeckPlanTask,
    PlanGeneratorCallback,
    deck_plan_response_schema,
    generate_deck_plan,
    prepare_deck_plan_task,
    render_plan_from_response,
)
from vaultlab.workflows.deep_think import (
    plan_deep_think_round,
    plan_deep_think_with_ensemble_critic,
    plan_round_from_critic_tests,
    run_deep_think_with_ensemble_critic,
)
from vaultlab.workflows.ensemble import plan_ensemble_critic
from vaultlab.workflows.lit import plan_lit_dive
from vaultlab.workflows.narrative import plan_narrate_finding
from vaultlab.workflows.parallel import plan_parallel_runs
from vaultlab.workflows.synthesis import plan_synthesis


__all__ = [
    # Data classes
    "CrosstalkResult",
    "DeckPlanTask",
    "DeepThinkEnsembleBundle",
    "MAX_N_ROUNDS",
    "MEETING_TIMEOUT_SECONDS",
    "PROVENANCE_INDEX",
    "PlanGeneratorCallback",
    "Provenance",
    "RunnerCallback",
    "WorkflowPlan",
    "read_provenance",
    "write_with_provenance",
    # Runners
    "run_workflow",
    "run_workflow_with_reflection",
    # Public builders
    "adversarial_arc_meeting",
    "adversarial_deck_plan_meeting",
    "adversarial_picker_meeting",
    "append_decisions_log_entry",
    "deck_plan_response_schema",
    "generate_deck_plan",
    "plan_brainstorm_figures",
    "plan_deep_think_round",
    "plan_deep_think_with_ensemble_critic",
    "plan_ensemble_critic",
    "plan_lit_dive",
    "plan_narrate_finding",
    "plan_parallel_runs",
    "plan_round_from_critic_tests",
    "plan_synthesis",
    "prepare_deck_plan_task",
    "render_plan_from_response",
    "rigor_audit",
    "run_deep_think_with_ensemble_critic",
    "write_crosstalk_artifacts",
]
