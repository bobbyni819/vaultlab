"""Synthesis workflow — Synthesizer alone over existing session findings.

The classic deep-think round ends with the Synthesizer integrating the
prior steps' outputs. This builder runs the same role in isolation —
useful when you want to re-narrate after upstream findings have moved
without redoing the Analyst/Expert/Critic steps.

Public surface
--------------

* :func:`plan_synthesis` — Synthesizer-only ``WorkflowPlan``
"""

from __future__ import annotations

import os
from datetime import date

from vaultlab.runner import ClaudeCodeRunner, build_meeting, wrap_contexts
from vaultlab.runner.models import Agenda, InvestigationMode
from vaultlab.workflows._models import WorkflowPlan
from vaultlab.workflows._provenance import Provenance
from vaultlab.workflows._utils import (
    _branch_summaries,
    _session_summary_if_exists,
)


def plan_synthesis(
    cfg,
    topic: str | None = None,
    investigation_mode: InvestigationMode = InvestigationMode.DIRECTED,
    agenda: Agenda | None = None,
    date_str: str | None = None,
    canonical_suffix: str = "",
) -> WorkflowPlan:
    """Run the Synthesizer alone over existing session findings.

    ``date_str`` and ``canonical_suffix`` are for callers that invoke
    :func:`plan_synthesis` multiple times in one session (e.g. ensemble
    deep-think has both a meta-review and a final synthesis, both using
    this plan shape). Both must be unique per call or the canonical
    outputs will collide.
    """
    topic = topic or f"all findings in {cfg.name}"
    prior = _session_summary_if_exists(cfg)
    branches = _branch_summaries(cfg)
    if branches:
        prior = (prior + "\n\n" if prior else "") + wrap_contexts("branch summary", branches)

    if agenda is None:
        agenda = Agenda(
            topic=topic,
            statement=f"Integrate findings into the manuscript narrative arc for {cfg.name}",
            questions=[
                "Which finding is the LEAD?",
                "Which findings SUPPORT the lead?",
                "Which are INDEPENDENT stories?",
                "What cross-finding connections are implied?",
                "What gaps would most strengthen the narrative?",
                "What is the Tier 1/2/3 priority ranking?",
            ],
            investigation_mode=investigation_mode,
        )

    meeting = build_meeting(
        topic=topic,
        meeting_type="synthesis",
        session_context=cfg.context_summary(),
        prior_summary=prior,
        agenda=agenda,
    )
    runner = ClaudeCodeRunner(
        kb_path=cfg.kb_path,
        command_name="synthesize",
        date_str=date_str,
    )
    plan = runner.plan(meeting, task=agenda)
    suffix = f"-{canonical_suffix}" if canonical_suffix else ""
    canonical = os.path.join(
        cfg.kb_path,
        "Output",
        f"synthesis-{date_str or date.today().isoformat()}{suffix}.md",
    )
    prov = Provenance(
        generated_by="synthesize",
        project=cfg.name,
        meeting_mode=meeting.mode.value,
        investigation_mode=agenda.investigation_mode.value,
        topic=topic,
        kind="synthesizer_output",
        tags=["synthesis", agenda.investigation_mode.value],
    )
    return WorkflowPlan(
        meeting=meeting,
        plan=plan,
        provenance=prov,
        canonical_output_path=canonical,
    )


__all__ = ["plan_synthesis"]
