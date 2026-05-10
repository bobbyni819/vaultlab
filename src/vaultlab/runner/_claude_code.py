"""ClaudeCodeRunner — plan meeting execution for in-session slash commands.

The runner produces a ``RunPlan`` the slash command follows by calling the
Agent tool for each step. This centralises the wiring (tool selection per
role, output paths, session-update hooks) that was previously inlined in
every command's markdown.

This is NOT an LLM executor. Active LLM calls happen via the Agent tool
inside Claude Code. ``LocalRunner`` (in ``vaultlab.runner._local``) fills
the same interface but calls the Anthropic API directly — that's the
secondary API surface.

Lifted from ``bobby_ailab._runner``. Behaviourally identical.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date as _date

from vaultlab.runner._temperatures import temperature_for
from vaultlab.runner.meetings import adversarial_inject, compose_turns
from vaultlab.runner.models import Agenda, Meeting, MeetingMode, MeetingTurn

# Per-role tool allow-lists. Conservative defaults — a role gets Bash only if
# its work genuinely requires running code. This mirrors the CLAUDE.md rule
# "don't add capabilities beyond what the task requires."
DEFAULT_TOOLS_BY_ROLE: dict[str, tuple[str, ...]] = {
    "data_analyst": ("Bash", "Read", "Glob", "Grep"),
    "literature_surveyor": ("Bash", "Read", "Glob", "Grep"),
    "domain_expert": ("Bash", "Read", "Glob", "Grep"),
    "methods_critic": ("Read", "Glob", "Grep"),
    "literature_critic": ("Read", "Glob", "Grep"),
    "synthesizer": ("Read", "Glob", "Grep"),
    "narrator": ("Read",),
    "figure_lead": ("Read", "Glob", "Grep"),
    "team_lead": ("Read",),
    "figure_reader": ("Read", "Glob", "Grep"),
}


@dataclass
class AgentSpec:
    """Spec for one Agent-tool invocation.

    A slash command reads the plan's ``steps`` and calls the Agent tool once
    per step with ``prompt`` and ``tools``. After the call, it writes the
    agent's response to ``output_path``.

    ``temperature`` is a hint for LocalRunner-style callers that can pass it
    through to the LLM; Claude Code's Agent tool ignores it (uses its own
    defaults), but the value is still useful for logs and provenance.
    """

    role_id: str
    role_name: str
    prompt: str
    tools: tuple[str, ...]
    output_path: str
    step_index: int
    temperature: float = 0.2


@dataclass
class RunPlan:
    """A meeting rendered into an executable sequence of agent invocations.

    ``steps`` are executed in order. Between steps, the slash command is
    expected to:

    1. Call the Agent tool with ``step.prompt`` and ``step.tools``
    2. Capture the response
    3. Write it to ``step.output_path``
    4. Fill ``turn.output`` on the corresponding ``MeetingTurn``
    5. Call ``plan.inject_prior_outputs(completed_turns)`` before the next
       step to re-render adversarial prompts with real outputs

    ``session_updates`` lists the recommended post-run actions.
    """

    meeting: Meeting
    steps: list[AgentSpec]
    turns: list[MeetingTurn]
    command_name: str
    round_num: int
    date_str: str
    kb_path: str
    session_updates: list[str] = field(default_factory=list)

    def inject_prior_outputs(self, completed_turns: list[MeetingTurn]) -> RunPlan:
        """Re-render the plan after some turns have completed.

        For adversarial / team / critiqued modes, later steps' prompts
        reference earlier outputs via placeholders. Call this with the turns
        that have been filled in to substitute real outputs into later
        prompts.
        """
        injected = adversarial_inject(completed_turns)
        new_steps = [
            AgentSpec(
                role_id=step.role_id,
                role_name=step.role_name,
                prompt=injected[i].prompt if i < len(injected) else step.prompt,
                tools=step.tools,
                output_path=step.output_path,
                step_index=step.step_index,
            )
            for i, step in enumerate(self.steps)
        ]
        return RunPlan(
            meeting=self.meeting,
            steps=new_steps,
            turns=injected,
            command_name=self.command_name,
            round_num=self.round_num,
            date_str=self.date_str,
            kb_path=self.kb_path,
            session_updates=self.session_updates,
        )


class ClaudeCodeRunner:
    """Planner for in-session Claude Code slash commands.

    Usage from a slash command::

        from vaultlab.runner import ClaudeCodeRunner, build_meeting

        runner = ClaudeCodeRunner(kb_path=cfg.kb_path, command_name="deep-think")
        meeting = build_meeting(topic="X", meeting_type="reasoning", session_context=ctx)
        plan = runner.plan(meeting, task="assess finding F001")
        for step in plan.steps:
            # spawn Agent(prompt=step.prompt, tools=step.tools)
            # capture response, write to step.output_path
            # fill plan.turns[step.step_index].output = response
            plan = plan.inject_prior_outputs(plan.turns)
    """

    def __init__(
        self,
        kb_path: str,
        command_name: str,
        date_str: str | None = None,
        tools_by_role: dict[str, tuple[str, ...]] | None = None,
    ):
        self.kb_path = kb_path
        self.command_name = command_name
        self.date_str = date_str or _date.today().isoformat()
        self.tools_by_role = tools_by_role or DEFAULT_TOOLS_BY_ROLE

    def plan(
        self,
        meeting: Meeting,
        task: str | Agenda,
        ensemble: bool = False,
    ) -> RunPlan:
        turns = compose_turns(meeting, task=task)
        steps = [
            AgentSpec(
                role_id=turn.role_id,
                role_name=meeting.roles[[r.id for r in meeting.roles].index(turn.role_id)].name,
                prompt=turn.prompt,
                tools=self.tools_for(turn.role_id),
                output_path=self._output_path(turn.role_id, i, meeting),
                step_index=i,
                temperature=temperature_for(
                    meeting.mode,
                    role_id=turn.role_id,
                    ensemble=ensemble,
                ),
            )
            for i, turn in enumerate(turns)
        ]
        return RunPlan(
            meeting=meeting,
            steps=steps,
            turns=turns,
            command_name=self.command_name,
            round_num=meeting.round_num,
            date_str=self.date_str,
            kb_path=self.kb_path,
            session_updates=self._session_updates_for(meeting),
        )

    def tools_for(self, role_id: str) -> tuple[str, ...]:
        return self.tools_by_role.get(role_id, ("Read", "Glob", "Grep"))

    def _output_path(self, role_id: str, step_index: int, meeting: Meeting) -> str:
        # Disambiguate when the same role appears twice (team meetings have the
        # lead at both start and end; critiqued meetings loop back to the role).
        suffix = ""
        repeat_count = sum(1 for r in meeting.roles[: step_index + 1] if r.id == role_id)
        if meeting.mode == MeetingMode.TEAM and role_id == "team_lead":
            suffix = "-initial" if step_index == 0 else "-final"
        elif meeting.mode == MeetingMode.CRITIQUED and role_id != "methods_critic":
            suffix = "-open" if step_index == 0 else "-response"
        elif repeat_count > 1:
            suffix = f"-{repeat_count}"
        filename = (
            f"{self.command_name}-{self.date_str}-round{meeting.round_num}-{role_id}{suffix}.md"
        )
        return os.path.join(self.kb_path, "Output", filename)

    def _session_updates_for(self, meeting: Meeting) -> list[str]:
        hints = [
            "After each step: write agent output to `step.output_path`",
            "Fill `plan.turns[step.step_index].output` with the agent response",
            "Between steps: call `plan = plan.inject_prior_outputs(plan.turns)` "
            "to propagate real outputs into later prompts",
            "After all steps: call `record_meeting(session, merge_outputs(meeting, "
            "plan.turns))` and `session.save()`",
        ]
        if meeting.mode == MeetingMode.ADVERSARIAL and any(
            r.id in ("methods_critic", "literature_critic") for r in meeting.roles
        ):
            hints.append(
                "After the critic's turn: parse rating strings with "
                "`set_rating(session, finding_id, rating)` for each finding"
            )
        if meeting.mode == MeetingMode.TEAM:
            hints.append(
                "The team lead's final turn IS the structured summary — write it to "
                "`{kb}/Output/{command}-{date}-summary.md` in addition to its per-turn path"
            )
        return hints


def render_plan_as_instructions(plan: RunPlan) -> str:
    """Render a RunPlan as human-readable markdown for debugging / preview."""
    lines = [
        f"# RunPlan: {plan.command_name} round {plan.round_num} ({plan.date_str})",
        "",
        f"Meeting mode: **{plan.meeting.mode.value}**  |  "
        f"Topic: **{plan.meeting.topic}**  |  "
        f"Roles: {', '.join(r.name for r in plan.meeting.roles)}",
        "",
        "## Steps",
        "",
    ]
    for step in plan.steps:
        lines.append(f"### Step {step.step_index + 1}: {step.role_name} (`{step.role_id}`)")
        lines.append(f"- **Tools:** {', '.join(step.tools) or '(none)'}")
        lines.append(f"- **Output:** `{step.output_path}`")
        lines.append(f"- **Prompt length:** {len(step.prompt)} chars")
        lines.append("")
    lines.append("## Post-run actions")
    for hint in plan.session_updates:
        lines.append(f"- {hint}")
    return "\n".join(lines)


__all__ = [
    "DEFAULT_TOOLS_BY_ROLE",
    "AgentSpec",
    "ClaudeCodeRunner",
    "RunPlan",
    "render_plan_as_instructions",
]
