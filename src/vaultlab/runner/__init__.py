"""vaultlab.runner — orchestration runners for meetings.

Two runners share one planning core:

- :class:`ClaudeCodeRunner` produces a :class:`RunPlan` that an in-session
  slash command consumes — for each step it spawns the Agent tool with the
  step's prompt + tool allow-list, captures the response, writes it to the
  step's output path, and feeds completed turns back via
  :meth:`RunPlan.inject_prior_outputs` so later prompts see real outputs.
- :class:`LocalRunner` inherits the planning surface but executes the plan
  itself against the Anthropic API (or, in default dry-run mode, fills each
  turn with a deterministic stub so the rest of the pipeline can be
  exercised without LLM cost).

Public data classes used by callers (``Meeting``, ``MeetingMode``,
``Agenda``, ``Role``, etc.) live at :mod:`vaultlab.runner.models`. They are
re-exported here for convenience.

Example::

    from vaultlab.runner import ClaudeCodeRunner, render_plan_as_instructions
    from vaultlab.runner.models import Meeting, MeetingMode, Role

    runner = ClaudeCodeRunner(kb_path="/path/to/kb", command_name="deep-think")
    plan = runner.plan(meeting, task="assess finding F001")
    print(render_plan_as_instructions(plan))

Notes
-----
This module was lifted from ``bobby_ailab`` (``_runner.py``,
``_local_runner.py``, ``_models.py``, ``_meetings.py``). The role catalog
lives at :mod:`vaultlab.roles` (markdown + YAML on disk); this module
re-exports a lazy proxy of ``ROLE_TEMPLATES`` for backward compatibility,
but new code should import from :mod:`vaultlab.roles` directly.
"""

from __future__ import annotations

from vaultlab.runner._claude_code import (
    DEFAULT_TOOLS_BY_ROLE,
    AgentSpec,
    ClaudeCodeRunner,
    RunPlan,
    render_plan_as_instructions,
)
from vaultlab.runner._local import LocalRunner, LocalRunnerConfig
from vaultlab.runner.meetings import (
    adversarial_inject,
    build_meeting,
    build_merge_meeting,
    compose_turns,
    merge_outputs,
    save_meeting,
    wrap_context,
    wrap_contexts,
)
from vaultlab.runner.models import (
    Agenda,
    InvestigationMode,
    Meeting,
    MeetingMode,
    MeetingResult,
    MeetingTurn,
    Mode,
    Role,
)
from vaultlab.runner.verifiers import verify_numeric

__all__ = [
    # Runner surface
    "AgentSpec",
    "ClaudeCodeRunner",
    "DEFAULT_TOOLS_BY_ROLE",
    "LocalRunner",
    "LocalRunnerConfig",
    "RunPlan",
    "render_plan_as_instructions",
    # Meetings layer (re-exported from .meetings)
    "adversarial_inject",
    "build_meeting",
    "build_merge_meeting",
    "compose_turns",
    "merge_outputs",
    "save_meeting",
    "wrap_context",
    "wrap_contexts",
    # Data models (re-exported from .models)
    "Agenda",
    "InvestigationMode",
    "Meeting",
    "MeetingMode",
    "MeetingResult",
    "MeetingTurn",
    "Mode",
    "Role",
    # Internal verifiers
    "verify_numeric",
]
