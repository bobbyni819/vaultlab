"""Ensemble-critic workflow — N independent critics + Area Chair meta-reviewer.

Adopted from AI-Scientist's ``perform_review.py``. A single Methods Critic
suffers from positivity bias; running N critics independently at
ENSEMBLE_TEMPERATURE (>0.5) and aggregating with strictest-wins surfaces
minority concerns reliably.

Public surface
--------------

* :func:`plan_ensemble_critic` — N critic plans + 1 meta-review plan
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from vaultlab.runner import ClaudeCodeRunner, build_meeting
from vaultlab.runner.meetings import ROLE_TEMPLATES
from vaultlab.runner.models import Agenda, Mode

from vaultlab.workflows._models import WorkflowPlan
from vaultlab.workflows._provenance import Provenance
from vaultlab.workflows.synthesis import plan_synthesis


def plan_ensemble_critic(
    cfg,
    topic: str,
    prior_outputs: str,
    n_critics: int = 3,
    round_num: int = 1,
    date_str: Optional[str] = None,
) -> tuple[list[WorkflowPlan], WorkflowPlan]:
    """N independent Methods Critic runs + 1 meta-reviewer — AI-Scientist pattern.

    Each critic runs at ENSEMBLE_TEMPERATURE for diversity. The meta-
    reviewer aggregates their ratings (strictest wins) and unions their
    priority tests.

    ``prior_outputs`` is the analyst+expert+synthesis context the critics
    review.

    Returns ``(critic_plans, meta_plan)``. Slash commands run critics in
    any order (ideally parallel), collect their outputs, then run meta-
    review.
    """
    if n_critics < 2:
        raise ValueError("plan_ensemble_critic requires n_critics >= 2")

    # TODO(ensemble-lift): the area-chair system prompt still lives in
    # bobby_ailab._ensemble. Small (~140 LOC); deferred until ensemble
    # aggregation utilities (pick_strictest, dedupe_tests) are lifted as
    # a unit.
    from bobby_ailab._ensemble import META_REVIEWER_SYSTEM_PROMPT

    critic_agenda = Agenda(
        topic=topic,
        statement=f"Independently review the findings on {topic}.",
        questions=[
            "What is the rating for each finding (ROBUST/NEEDS_VALIDATION/WEAK/UNSUPPORTED)?",
            "What specific test would move a NEEDS_VALIDATION rating to ROBUST?",
            "Which assumptions were hidden or not stated?",
        ],
        rules=[
            "Every rating needs a specific falsifiable test (not 'needs more analysis')",
            "Flag any assumption that was not explicitly stated in the prior outputs",
            "Priority tests tagged [CRITICAL]/[HIGH]/[MEDIUM]/[LOW]",
        ],
    )

    critic_plans: list[WorkflowPlan] = []
    for i in range(n_critics):
        per_date = f"{date_str or date.today().isoformat()}-critic{i + 1}"
        # Use a single-role meeting (critiqued-mode shape but just the critic)
        meeting = build_meeting(
            topic=topic,
            meeting_type="reasoning",
            session_context=cfg.context_summary() + "\n\nPRIOR OUTPUTS:\n" + prior_outputs,
            mode=Mode.DATA_ANALYSIS,
            round_num=round_num,
            agenda=critic_agenda,
        )
        meeting.roles = [ROLE_TEMPLATES["methods_critic"]]
        runner = ClaudeCodeRunner(
            kb_path=cfg.kb_path, command_name="ensemble-critic", date_str=per_date,
        )
        plan = runner.plan(meeting, task=critic_agenda, ensemble=True)
        for step in plan.steps:
            step.temperature = 0.75
        prov = Provenance(
            generated_by="ensemble-critic",
            project=cfg.name,
            meeting_mode=meeting.mode.value,
            topic=topic,
            round=round_num,
            kind="ensemble_critic",
            tags=["critic-ensemble", f"critic-{i + 1}"],
        )
        critic_plans.append(WorkflowPlan(meeting=meeting, plan=plan, provenance=prov))

    # Meta-reviewer — Area Chair role reusing the synthesizer shell but with
    # META_REVIEWER_SYSTEM_PROMPT layered in via the agenda statement.
    meta_agenda = Agenda(
        topic=f"meta-review of {n_critics} critics on {topic}",
        statement=META_REVIEWER_SYSTEM_PROMPT,
        questions=[
            "What is the aggregated (strictest) rating per finding?",
            "What disagreements existed between reviewers, and how were they resolved?",
            "What is the deduplicated priority queue for the next round?",
        ],
        rules=[
            "Strictest rating wins — majority vote hides minority objections",
            "Priority tests deduped by description; keep the higher priority of duplicates",
            "Name disagreements explicitly ('Critic A said X, Critic B said Y')",
        ],
    )
    meta_plan = plan_synthesis(
        cfg, topic=f"meta-review of {n_critics} critics",
        agenda=meta_agenda,
        date_str=f"{date_str or date.today().isoformat()}-meta",
        canonical_suffix="meta-review",
    )
    meta_plan.provenance.tags = list(meta_plan.provenance.tags) + [
        "meta-review", f"n_critics={n_critics}",
    ]
    meta_plan.provenance.kind = "ensemble_meta_review"
    return critic_plans, meta_plan


__all__ = ["plan_ensemble_critic"]
