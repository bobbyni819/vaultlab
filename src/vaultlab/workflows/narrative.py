"""Narrate-finding workflow — single-role narrator writes one KB concept page.

The Narrator role writes the user-facing prose for one finding: what the
data shows, why it matters, and how confident we are. One file per
finding, never mixing two findings.

Public surface
--------------

* :func:`plan_narrate_finding` — builds the per-finding narration plan
"""

from __future__ import annotations

import os

from vaultlab.runner import ClaudeCodeRunner, build_meeting
from vaultlab.runner.models import Agenda
from vaultlab.workflows._models import WorkflowPlan
from vaultlab.workflows._provenance import Provenance
from vaultlab.workflows._utils import _slug


def plan_narrate_finding(
    cfg,
    finding_id: str,
    claim: str,
    chain_block: str = "",
    branch_content: str = "",
    exact_value: str = "",
    data_source: str = "",
    mechanism: str = "",
    literature: list[str] | None = None,
    status: str = "unknown",
    category: str = "unknown",
) -> WorkflowPlan:
    """Narrator writes the KB concept page for ONE finding."""
    lit = literature or []
    ctx = cfg.context_summary() + (
        f"\n\nFINDING: {finding_id} — {claim}\n"
        f"STATUS: {status}  CATEGORY: {category}\n"
        f"EXACT VALUE: {exact_value or 'n/a'}\n"
        f"DATA SOURCE: {data_source or 'n/a'}\n"
        f"MECHANISM: {mechanism or 'not yet proposed'}\n"
        f"LITERATURE: {', '.join(lit) or 'none'}\n\n"
        f"CHAIN OF REASONING:\n{chain_block or '(no chain recorded)'}\n\n"
        f"BRANCH DOCS:\n{branch_content or '(none)'}"
    )
    agenda = Agenda(
        topic=f"narrate {finding_id}",
        statement=f"Write the KB concept page for {finding_id}",
        questions=[
            "What does the data show in concrete terms?",
            "Why does this matter in the project's domain?",
            "How confident are we — and what would resolve any uncertainty?",
            "Where does this sit in the larger story?",
        ],
        rules=[
            "One finding per file — never mix two findings",
            "Prose, not bullet lists; sparse headings",
            "Every number must come from the provided chain (do not invent)",
            f"Link back to Sources/Notes/{finding_id.lower()}/analysis.md",
        ],
    )
    meeting = build_meeting(
        topic=f"narrate {finding_id}",
        meeting_type="narrate",
        session_context=ctx,
        agenda=agenda,
    )
    runner = ClaudeCodeRunner(kb_path=cfg.kb_path, command_name="narrate-finding")
    plan = runner.plan(meeting, task=agenda)
    slug = _slug(claim)
    canonical = os.path.join(cfg.kb_path, "Wiki", "Concepts", f"{finding_id.lower()}-{slug}.md")
    prov = Provenance(
        generated_by="narrate-finding",
        project=cfg.name,
        meeting_mode=meeting.mode.value,
        topic=f"narrate {finding_id}",
        finding_ids=[finding_id],
        kind="narration",
        tags=["narration", finding_id.lower()],
    )
    return WorkflowPlan(
        meeting=meeting,
        plan=plan,
        provenance=prov,
        canonical_output_path=canonical,
    )


__all__ = ["plan_narrate_finding"]
