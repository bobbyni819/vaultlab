"""Internal helpers shared by every public workflow builder.

* ``_slug`` — kebab-case slugifier for filenames
* ``_session_summary_if_exists`` — read prior research-session.json if any
* ``_branch_summaries`` — collect ``branch/*/summary.md`` content
* ``_latest_synthesis_text`` — read most recent ``synthesis-*.md``
* ``_inject_prior_context`` — append a "PRIOR OUTPUTS" block to every step's
  prompt in a ``WorkflowPlan`` (used between phases of a multi-phase bundle)

These were file-private in ``bobby_ailab/workflows.py``; in vaultlab they
live as a sibling module so the per-workflow files (``deep_think.py``,
``synthesis.py``, ...) can import them cleanly.
"""

from __future__ import annotations

import glob
import os
import re

from vaultlab.workflows._models import WorkflowPlan


def _slug(text: str, max_length: int = 60) -> str:
    """Kebab-case a string for use in filenames."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:max_length]


def _session_summary_if_exists(cfg: object) -> str:
    """Return ``session_summary_for_prompt`` for a project if a session is on disk.

    Returns an empty string when:

    - no ``research-session.json`` exists in the project's ``Output/`` dir
    - the research package isn't importable (extras not installed)
    - the session file is corrupt

    ``cfg`` must expose a ``kb_path`` attribute pointing at the KB root.
    """
    session_path = os.path.join(cfg.kb_path, "Output", "research-session.json")
    if not os.path.exists(session_path):
        return ""
    # Try vaultlab.research first, fall back to bobby_research.
    try:
        from vaultlab.research.session import ResearchSession  # type: ignore[import-not-found]
    except ImportError:
        try:
            from bobby_research import ResearchSession  # type: ignore[import-not-found]
        except ImportError:
            return ""
    try:
        session = ResearchSession.load(session_path)
    except (OSError, ValueError):
        return ""
    return _session_summary_for_prompt(session)


def _session_summary_for_prompt(session: object) -> str:
    """Compact prior-round summary suitable for injecting into a meeting.

    Inlined here to keep the workflows package self-contained — the legacy
    ``bobby_ailab._session_bridge.session_summary_for_prompt`` does the
    same thing and we mirror its output exactly.
    """
    findings = getattr(session, "findings", {}) or {}
    if not findings:
        return ""
    current_round = getattr(session, "current_round", 1)
    lines = [f"Current findings (round {current_round}):"]
    for finding in sorted(findings.values(), key=lambda f: f.id):
        value = f" ({finding.exact_value})" if getattr(finding, "exact_value", "") else ""
        status = (
            finding.status.value.upper()
            if hasattr(finding.status, "value")
            else str(finding.status).upper()
        )
        lines.append(f"- {finding.id}: {finding.claim} [{status}]{value}")
    return "\n".join(lines)


def _branch_summaries(cfg: object) -> list[str]:
    """Collect ``branch/*/summary.md`` contents for richer prior context."""
    summaries: list[str] = []
    pattern = os.path.join(cfg.kb_path, "Sources", "Notes", "*", "summary.md")
    for path in sorted(glob.glob(pattern)):
        try:
            with open(path, encoding="utf-8") as f:
                summaries.append(f.read())
        except OSError:
            continue
    return summaries


def _latest_synthesis_text(cfg: object) -> str:
    """Return the most recent ``synthesis-*.md`` content, or empty string."""
    pattern = os.path.join(cfg.kb_path, "Output", "synthesis-*.md")
    matches = sorted(glob.glob(pattern))
    if not matches:
        return ""
    try:
        with open(matches[-1], encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def _inject_prior_context(wp: WorkflowPlan, prior_context: str) -> None:
    """Append a ``PRIOR OUTPUTS`` block to every step's prompt in a workflow.

    Mutates the ``WorkflowPlan`` in place. Used between phases of a multi-
    phase bundle (e.g. ensemble deep-think) where later phases need to see
    earlier phases' outputs.
    """
    marker = "\n\nPRIOR OUTPUTS (from upstream phases):\n"
    for step in wp.plan.steps:
        if marker not in step.prompt:
            step.prompt = step.prompt.rstrip() + marker + prior_context.strip() + "\n"
    for turn in wp.plan.turns:
        if marker not in turn.prompt:
            turn.prompt = turn.prompt.rstrip() + marker + prior_context.strip() + "\n"


__all__ = [
    "_branch_summaries",
    "_inject_prior_context",
    "_latest_synthesis_text",
    "_session_summary_if_exists",
    "_slug",
]
