"""Figure-brainstorm workflow — FigureLead + Critic propose a figure plan.

A two-role adversarial meeting: the FigureLead drafts a figure plan over
current findings + the latest synthesis, then the Methods Critic
challenges the proposal. Output is the canonical ``figure-plan.md``
consumed by downstream plotting commands.

Public surface
--------------

* :func:`plan_brainstorm_figures`
"""

from __future__ import annotations

import os
from typing import Optional  # noqa: F401  (kept for forwards compat)

from vaultlab.runner import ClaudeCodeRunner, build_meeting
from vaultlab.runner.models import Agenda

from vaultlab.workflows._models import WorkflowPlan
from vaultlab.workflows._provenance import Provenance
from vaultlab.workflows._utils import (
    _latest_synthesis_text,
    _session_summary_if_exists,
)


def plan_brainstorm_figures(
    cfg,
    focus: str = "",
) -> WorkflowPlan:
    """FigureLead + Critic propose a figure plan from current findings + latest synthesis."""
    prior = _session_summary_if_exists(cfg)
    synth = _latest_synthesis_text(cfg)
    ctx = cfg.context_summary()
    if prior:
        ctx += "\n\n" + prior
    if synth:
        ctx += "\n\nLATEST SYNTHESIS:\n" + synth

    topic = focus or "figure plan"
    agenda = Agenda(
        topic=topic,
        statement=f"Propose figures, panels, and visual hooks for current findings in {cfg.name}",
        questions=[
            "Which findings group into which figure?",
            "What is each figure's visual hook (one sentence)?",
            "What plot type for each panel and why?",
            "Does each figure cover the full breadth of data?",
            "What analyses are missing before plotting can start?",
        ],
        rules=[
            "Every panel cites the finding IDs it displays",
            "Every figure has a one-sentence visual hook",
            "Prefer fewer, stronger figures over many weak ones",
        ],
    )
    meeting = build_meeting(
        topic=topic, meeting_type="brainstorm",
        session_context=ctx, agenda=agenda,
    )
    runner = ClaudeCodeRunner(kb_path=cfg.kb_path, command_name="brainstorm-figures")
    plan = runner.plan(meeting, task=agenda)
    canonical = os.path.join(cfg.kb_path, "Output", "figure-plan.md")
    prov = Provenance(
        generated_by="brainstorm-figures",
        project=cfg.name,
        meeting_mode=meeting.mode.value,
        topic=topic, kind="figure_plan",
        tags=["figures", "brainstorm"],
    )
    return WorkflowPlan(
        meeting=meeting, plan=plan, provenance=prov,
        canonical_output_path=canonical,
    )


__all__ = ["plan_brainstorm_figures"]
