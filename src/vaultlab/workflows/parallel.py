"""Parallel-runs workflow — N independent deep-thinks + a Synthesizer merge.

Adopted from the virtual-lab "merge meetings" pattern: run the same
agenda independently N times at ENSEMBLE_TEMPERATURE for diversity, then
hand the Synthesizer all N outputs and ask it to produce a single answer
that picks the best of each.

Public surface
--------------

* :func:`plan_parallel_runs`
"""

from __future__ import annotations

from datetime import date

from vaultlab.runner.models import Agenda, InvestigationMode, Mode
from vaultlab.workflows._models import WorkflowPlan
from vaultlab.workflows.deep_think import plan_deep_think_round
from vaultlab.workflows.synthesis import plan_synthesis


def plan_parallel_runs(
    cfg,
    topic: str,
    num_runs: int = 3,
    round_num: int = 1,
    mode: Mode = Mode.DATA_ANALYSIS,
    investigation_mode: InvestigationMode = InvestigationMode.DIRECTED,
    agenda: Agenda | None = None,
    date_str: str | None = None,
) -> tuple[list[WorkflowPlan], WorkflowPlan]:
    """Build N parallel deep-think runs + one merge workflow — virtual-lab pattern.

    Each parallel run is a full adversarial meeting with the same agenda;
    they execute at ENSEMBLE_TEMPERATURE for diversity. The merge run
    integrates all N summaries at CONSISTENT_TEMPERATURE — Synthesizer-only.

    Returns ``(parallel_plans, merge_plan)``. Slash commands::

        for p in parallel_plans:
            run_workflow(p, agent_fn=...)
        merge_plan = _attach_prior_outputs(merge_plan, parallel_plans)
        run_workflow(merge_plan, agent_fn=...)

    Per virtual-lab's merge protocol, the merge meeting must cite which
    run each component came from. The merge agenda rule enforces this.
    """
    if num_runs < 2:
        raise ValueError("plan_parallel_runs requires num_runs >= 2")

    parallel_plans: list[WorkflowPlan] = []
    for i in range(num_runs):
        per_run_date = f"{date_str or date.today().isoformat()}-run{i + 1}"
        wp = plan_deep_think_round(
            cfg,
            topic=topic,
            round_num=round_num,
            mode=mode,
            investigation_mode=investigation_mode,
            agenda=agenda,
            date_str=per_run_date,
        )
        # Ensemble temperature for diversity — override per-step temp
        for step in wp.plan.steps:
            step.temperature = 0.75
        wp.provenance.tags = list(wp.provenance.tags) + [f"parallel-run-{i + 1}"]
        wp.provenance.kind = "parallel_run"
        parallel_plans.append(wp)

    # Merge workflow — Synthesizer alone, low temperature
    merge_agenda = Agenda(
        topic=f"merge {num_runs} parallel runs on {topic}",
        statement=(
            f"Synthesize the {num_runs} independent runs on '{topic}' into one "
            f"canonical output. Pick the best of each (not the average). "
            f"Explain provenance: 'this element came from run N because X'."
        ),
        questions=[
            "Which findings appeared in multiple runs (high-confidence)?",
            "Which findings appeared in only one run — why, and are they still worth keeping?",
            "Where did runs disagree, and which interpretation is best supported?",
            "What is the merged set of findings with provenance tags?",
        ],
        rules=[
            "Every component in the merged output must cite the run it came from (run 1, run 2, ...)",
            "Do not average conflicting claims — pick the best-supported one and name the alternative",
            "Cite exact values and null baselines preserved from the source run",
        ],
        investigation_mode=investigation_mode,
    )
    merge_plan = plan_synthesis(
        cfg,
        topic=f"merge {num_runs} runs on {topic}",
        investigation_mode=investigation_mode,
        agenda=merge_agenda,
    )
    merge_plan.provenance.tags = list(merge_plan.provenance.tags) + [
        "parallel-merge",
        f"num_runs={num_runs}",
    ]
    merge_plan.provenance.kind = "parallel_merge"
    return parallel_plans, merge_plan


__all__ = ["plan_parallel_runs"]
