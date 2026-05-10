"""Literature-dive workflow — Literature Surveyor drives a stateful lit search.

Single-role plan that drives the paperclip stateful workflow (broad
search → optional grep → map → reduce). The agenda enforces verification
against paperclip / bobby_research and forbids citing papers from
memory.

Public surface
--------------

* :func:`plan_lit_dive`
"""

from __future__ import annotations

import os
from datetime import date

from vaultlab.roles import ROLE_TEMPLATES
from vaultlab.runner import ClaudeCodeRunner, build_meeting
from vaultlab.runner.models import Agenda, InvestigationMode, Mode
from vaultlab.workflows._models import WorkflowPlan
from vaultlab.workflows._provenance import Provenance
from vaultlab.workflows._utils import _slug


def plan_lit_dive(
    cfg,
    topic: str,
    investigation_mode: InvestigationMode = InvestigationMode.EXPLORATORY,
) -> WorkflowPlan:
    """Literature Surveyor drives paperclip's stateful search → map → reduce workflow."""
    if not topic.strip():
        raise ValueError("plan_lit_dive requires a non-empty topic")
    agenda = Agenda(
        topic=topic,
        statement=f"Synthesize the literature on {topic} using paperclip's stateful workflow.",
        questions=[
            "What is the current consensus, if any, in the literature?",
            "What are the key papers (DOIs, journals, years) that anchor the consensus?",
            "What contradicting or minority views exist, and who published them?",
            "What gaps remain that a new analysis could fill?",
            "Which paper IDs should be pulled for deeper reading?",
        ],
        rules=[
            "Every claim cites a specific paper ID (paperclip bio_/med_/PMC and DOI)",
            "Run the stateful workflow: paperclip search → optional grep → map → reduce",
            "Record the paperclip results_id in the output",
            "Never summarize abstracts from memory — always pull from paperclip",
        ],
        investigation_mode=investigation_mode,
    )
    meeting = build_meeting(
        topic=topic,
        meeting_type="figure_read",  # single-role structure; we override the role below
        session_context=cfg.context_summary(),
        mode=Mode.LITERATURE_REVIEW,
        agenda=agenda,
    )
    # Override to Literature Surveyor (the built-in figure_read is for the
    # FigureReader role; lit-dive reuses the single-role compose_turns
    # structure but with Surveyor).
    meeting.roles = [ROLE_TEMPLATES["literature_surveyor"]]

    runner = ClaudeCodeRunner(kb_path=cfg.kb_path, command_name="lit-dive")
    plan = runner.plan(meeting, task=agenda)
    slug = _slug(topic)
    canonical = os.path.join(
        cfg.kb_path, "Output", f"lit-dive-{date.today().isoformat()}-{slug}.md"
    )
    prov = Provenance(
        generated_by="lit-dive",
        project=cfg.name,
        meeting_mode=meeting.mode.value,
        investigation_mode=investigation_mode.value,
        topic=topic,
        kind="literature_dive",
        tags=["literature", "paperclip", slug],
    )
    return WorkflowPlan(
        meeting=meeting,
        plan=plan,
        provenance=prov,
        canonical_output_path=canonical,
    )


__all__ = ["plan_lit_dive"]
