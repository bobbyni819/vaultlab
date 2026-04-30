"""Meeting primitives — compose role prompts into multi-agent sessions.

Implements the virtual-lab inspired meeting structure (lead/member team
meetings, individual meetings with always-on critic, parallel-merge
synthesis). See ``INSPIRATIONS.md`` and the
``architecture-and-lineage-2026-04-29.md`` Part 1 lineage table for the full
intellectual lineage; the short form is: meetings/agendas/team structure
adopted as a PATTERN from Swanson et al. *Nature* 2025 ("The Virtual Lab",
zou-group/virtual-lab), reimplemented in Python with vaultlab's role taxonomy.

This layer is intentionally pure-Python and LLM-agnostic. It builds the
exact prompts each agent should receive for a given meeting configuration.
Executing the prompts is the runner layer's job (``ClaudeCodeRunner`` /
``LocalRunner``).

Slash commands consume these by rendering meetings into instructions the
``Agent`` tool can spawn; the future harness server consumes the same
meetings and runs them against the Claude API directly.

Roles come from :mod:`vaultlab.roles` — markdown + YAML on disk, loaded
into the canonical :class:`vaultlab.runner.models.Role` shape. There is
exactly one Role class in vaultlab; ``compose_turns`` calls ``role.prompt_for``
directly with no adapter layer.
"""

from __future__ import annotations

from typing import Iterable, Optional

from vaultlab.runner.models import (
    Agenda,
    Meeting,
    MeetingMode,
    MeetingResult,
    MeetingTurn,
    Mode,
    Role,
)


def _catalog():
    """Return the live vaultlab.roles catalog (imported lazily).

    The runner package is imported by :mod:`vaultlab.roles` (which needs
    ``Role`` and ``Mode`` from :mod:`vaultlab.runner.models`); importing
    :mod:`vaultlab.roles` at the top of this module would close the
    circular reference. Deferring the import to call time keeps the
    package-load order clean while still letting callers treat
    ``ROLE_TEMPLATES`` as a module-level dict.
    """
    from vaultlab.roles import ROLE_TEMPLATES as _RT
    return _RT


def _roles_for(meeting_type: str, mode: Mode = Mode.DATA_ANALYSIS) -> list[Role]:
    """Lazy passthrough to :func:`vaultlab.roles.roles_for`. See :func:`_catalog`."""
    from vaultlab.roles import roles_for as _rf
    return _rf(meeting_type, mode)


# Backwards-compatible re-exports. Callers may still do
# ``from vaultlab.runner.meetings import ROLE_TEMPLATES`` — the proxy
# resolves lazily on access. New code should prefer
# ``from vaultlab.roles import ROLE_TEMPLATES`` directly.
class _LazyRoleTemplates:
    """Dict-style proxy that resolves to vaultlab.roles.ROLE_TEMPLATES on access."""

    def _resolve(self):
        return _catalog()

    def __getitem__(self, role_id: str) -> Role:
        return self._resolve()[role_id]

    def __contains__(self, role_id: object) -> bool:
        return role_id in self._resolve()

    def __iter__(self):
        return iter(self._resolve())

    def __len__(self) -> int:
        return len(self._resolve())

    def keys(self):
        return self._resolve().keys()

    def values(self):
        return self._resolve().values()

    def items(self):
        return self._resolve().items()

    def get(self, role_id: str, default=None):
        return self._resolve().get(role_id, default)


ROLE_TEMPLATES = _LazyRoleTemplates()


def roles_for(meeting_type: str, mode: Mode = Mode.DATA_ANALYSIS) -> list[Role]:
    """Re-export of :func:`vaultlab.roles.roles_for` — see :func:`_roles_for`."""
    return _roles_for(meeting_type, mode)


def build_meeting(
    topic: str,
    meeting_type: str,
    session_context: str,
    mode: Mode = Mode.DATA_ANALYSIS,
    round_num: int = 1,
    prior_summary: str = "",
    roles: Optional[Iterable[Role]] = None,
    agenda: Optional[Agenda] = None,
) -> Meeting:
    """Build a meeting from a named type or an explicit role list.

    ``meeting_type`` maps to a default role set (see ``roles_for``). Pass
    ``roles`` to override — the mode+type must still make sense together.
    """
    resolved_mode = _infer_mode_map(meeting_type)
    selected = list(roles) if roles is not None else roles_for(meeting_type, mode)
    return Meeting(
        topic=topic,
        mode=resolved_mode,
        roles=selected,
        session_context=session_context,
        round_num=round_num,
        prior_summary=prior_summary,
        agenda=agenda,
    )


def _infer_mode_map(meeting_type: str) -> MeetingMode:
    if meeting_type.startswith("critiqued_"):
        return MeetingMode.CRITIQUED
    return {
        "reasoning":         MeetingMode.ADVERSARIAL,
        "deep_think":        MeetingMode.ADVERSARIAL,
        "synthesis":         MeetingMode.SYNTHESIS,
        "brainstorm":        MeetingMode.ADVERSARIAL,
        "narrate":           MeetingMode.INDIVIDUAL,
        "round_table":       MeetingMode.ROUND_TABLE,
        "team_meeting":      MeetingMode.TEAM,
        "critique":          MeetingMode.ADVERSARIAL,
        "figure_read":       MeetingMode.INDIVIDUAL,
        "visual_deep_think": MeetingMode.ADVERSARIAL,
    }.get(meeting_type, MeetingMode.ADVERSARIAL)


def compose_turns(meeting: Meeting, task: str | Agenda) -> list[MeetingTurn]:
    """Render a meeting into the ordered prompts each role should receive.

    ROUND_TABLE: every role gets the same context, no prior outputs.
    ADVERSARIAL: later roles receive earlier roles' outputs (placeholder
      tokens — the runner substitutes actual outputs as they arrive).
    SYNTHESIS: a single role receives the prior summary as prior output.
    INDIVIDUAL: one role, no prior outputs.
    TEAM: lead opens, members respond, lead closes (virtual-lab pattern).
    CRITIQUED: role + always-on critic, with a follow-up role response turn.

    If the meeting was built with ``agenda=``, it takes precedence over the
    ``task`` argument. This keeps backwards compat while preferring structured
    agendas.
    """
    effective_task: str | Agenda = (
        meeting.agenda if meeting.agenda is not None else task
    )
    ctx = _with_round_header(meeting)
    turns: list[MeetingTurn] = []
    if meeting.mode == MeetingMode.ROUND_TABLE:
        for role in meeting.roles:
            turns.append(
                MeetingTurn(
                    role_id=role.id,
                    prompt=role.prompt_for(session_context=ctx, task=effective_task),
                )
            )
    elif meeting.mode == MeetingMode.ADVERSARIAL:
        for i, role in enumerate(meeting.roles):
            prior = _prior_placeholder(meeting.roles[:i]) if i else ""
            turns.append(
                MeetingTurn(
                    role_id=role.id,
                    prompt=role.prompt_for(
                        session_context=ctx, task=effective_task, prior_outputs=prior
                    ),
                )
            )
    elif meeting.mode == MeetingMode.SYNTHESIS:
        if len(meeting.roles) != 1:
            raise ValueError("synthesis meetings must have exactly one role")
        role = meeting.roles[0]
        turns.append(
            MeetingTurn(
                role_id=role.id,
                prompt=role.prompt_for(
                    session_context=ctx,
                    task=effective_task,
                    prior_outputs=meeting.prior_summary or "",
                ),
            )
        )
    elif meeting.mode == MeetingMode.INDIVIDUAL:
        if len(meeting.roles) != 1:
            raise ValueError("individual meetings must have exactly one role")
        role = meeting.roles[0]
        turns.append(
            MeetingTurn(
                role_id=role.id,
                prompt=role.prompt_for(session_context=ctx, task=effective_task),
            )
        )
    elif meeting.mode == MeetingMode.TEAM:
        # virtual-lab team meeting: lead opens, members respond, lead closes
        if len(meeting.roles) < 2:
            raise ValueError("team meetings need a lead plus >=1 member")
        lead = meeting.roles[0]
        members = meeting.roles[1:]
        # turn 0: lead initial framing
        turns.append(MeetingTurn(
            role_id=lead.id,
            prompt=lead.prompt_for(
                session_context=ctx,
                task=effective_task,
                prior_outputs="[role: LEAD_INITIAL — frame the meeting, name decision criteria, "
                              "and invite each team member in turn]",
            ),
        ))
        # turns 1..N: each member responds
        for i, member in enumerate(members):
            prior = _prior_placeholder([lead, *members[:i]]) if i else _prior_placeholder([lead])
            turns.append(MeetingTurn(
                role_id=member.id,
                prompt=member.prompt_for(
                    session_context=ctx,
                    task=effective_task,
                    prior_outputs=prior + (
                        '\n\nNote: if you have nothing new or relevant to add, you may say "pass".'
                    ),
                ),
            ))
        # final turn: lead closes with structured summary
        all_prior = _prior_placeholder([lead, *members])
        turns.append(MeetingTurn(
            role_id=lead.id,
            prompt=lead.prompt_for(
                session_context=ctx,
                task=effective_task,
                prior_outputs=all_prior + (
                    "\n\n[role: LEAD_FINAL — produce the structured summary with "
                    "Agenda / Team Member Input / Recommendation / Answers / Next Steps]"
                ),
            ),
        ))
    elif meeting.mode == MeetingMode.CRITIQUED:
        # virtual-lab individual meeting: role + always-on critic, iterating
        if len(meeting.roles) != 2:
            raise ValueError("critiqued meetings need exactly [role, critic]")
        role, critic = meeting.roles
        turns.append(MeetingTurn(
            role_id=role.id,
            prompt=role.prompt_for(session_context=ctx, task=effective_task),
        ))
        turns.append(MeetingTurn(
            role_id=critic.id,
            prompt=critic.prompt_for(
                session_context=ctx,
                task=effective_task,
                prior_outputs=_prior_placeholder([role]),
            ),
        ))
        # a second pass: role responds to critique
        turns.append(MeetingTurn(
            role_id=role.id,
            prompt=role.prompt_for(
                session_context=ctx,
                task=effective_task,
                prior_outputs=_prior_placeholder([role, critic]) + (
                    "\n\n[Respond to the critic: address each challenge, concede where warranted, "
                    "defend with evidence where not.]"
                ),
            ),
        ))
    else:
        raise ValueError(f"unhandled meeting mode: {meeting.mode}")
    return turns


def _with_round_header(meeting: Meeting) -> str:
    header = [f"ROUND: {meeting.round_num}", f"TOPIC: {meeting.topic}"]
    if meeting.prior_summary.strip():
        header += ["", "PRIOR-ROUND SUMMARY:", meeting.prior_summary.strip()]
    return "\n".join(header) + "\n\n" + meeting.session_context.strip()


def _prior_placeholder(prior_roles: list[Role]) -> str:
    """The runner substitutes actual outputs; this is a structural hint."""
    return "\n\n".join(
        f"[{r.name} output will be inserted here by the runner]" for r in prior_roles
    )


def build_merge_meeting(
    prior_results: list[MeetingResult],
    agenda: Agenda,
    session_context: str,
    explain_choices: bool = True,
) -> Meeting:
    """Build a Synthesizer meeting that merges the best parts of N prior runs.

    Pattern adopted from virtual-lab's ``create_merge_prompt``: you run the
    same meeting N times independently (fresh context per run to diversify),
    then hand the Synthesizer all N outputs and ask it to produce a single
    answer that merges the best components of each.

    When ``explain_choices`` is true, the merger must explain which
    components came from which prior run and why — this is the provenance
    the downstream reviewer relies on.
    """
    if not prior_results:
        raise ValueError("build_merge_meeting needs at least one prior result")
    synthesizer = ROLE_TEMPLATES["synthesizer"]
    blocks = []
    for i, result in enumerate(prior_results, start=1):
        concatenated = "\n\n".join(
            f"### {ROLE_TEMPLATES[t.role_id].name}\n{t.output.strip()}"
            for t in result.turns
            if t.output.strip()
        )
        blocks.append(
            f"[begin run {i}]\n\n{concatenated}\n\n[end run {i}]"
        )
    merge_summary = "\n\n".join(blocks)

    merge_rules = list(agenda.rules)
    if explain_choices:
        merge_rules.append(
            "For each component of your merged answer, explain which prior run it came from "
            "and why you chose to include it."
        )
    merged_agenda = Agenda(
        topic=agenda.topic,
        statement=(
            "Read the summaries of multiple separate meetings about the same agenda. "
            "Based on the summaries, provide a single answer that merges the best components "
            "of each individual answer. " + agenda.statement
        ).strip(),
        questions=list(agenda.questions),
        rules=merge_rules,
    )
    return Meeting(
        topic=agenda.topic,
        mode=MeetingMode.SYNTHESIS,
        roles=[synthesizer],
        session_context=session_context,
        round_num=1,
        prior_summary=merge_summary,
        agenda=merged_agenda,
    )


def merge_outputs(meeting: Meeting, turns: list[MeetingTurn]) -> MeetingResult:
    """Collect completed turns into a MeetingResult.

    Callers should populate ``turn.output`` with the actual agent output
    before calling this. This function does not execute anything; it just
    collects.
    """
    expected_ids = [r.id for r in meeting.roles]
    got_ids = [t.role_id for t in turns]
    if expected_ids != got_ids:
        raise ValueError(
            f"turn role_ids {got_ids} do not match meeting.roles {expected_ids}"
        )
    return MeetingResult(
        topic=meeting.topic,
        mode=meeting.mode,
        round_num=meeting.round_num,
        turns=turns,
    )


def adversarial_inject(turns: list[MeetingTurn]) -> list[MeetingTurn]:
    """Rewrite adversarial prompts so each later turn sees earlier outputs.

    Call this after ``turn.output`` has been filled in for earlier turns.
    Only meaningful for ADVERSARIAL meetings. Returns a new list.
    """
    rewritten: list[MeetingTurn] = []
    prior_blocks: list[str] = []
    for turn in turns:
        if prior_blocks and turn.output == "":
            prior = "\n\n".join(prior_blocks)
            new_prompt = _swap_prior(turn.prompt, prior)
            rewritten.append(
                MeetingTurn(
                    role_id=turn.role_id, prompt=new_prompt, output="",
                    output_path=turn.output_path,
                )
            )
        else:
            rewritten.append(turn)
        if turn.output.strip():
            display_name = (
                ROLE_TEMPLATES[turn.role_id].name
                if turn.role_id in ROLE_TEMPLATES
                else turn.role_id
            )
            prior_blocks.append(
                f"### {display_name}\n{turn.output.strip()}"
            )
    return rewritten


def wrap_context(label: str, content: str, index: int = 1) -> str:
    """Wrap a context block with virtual-lab style ``[begin <label> N] ... [end <label> N]``.

    Use this to combine multiple prior summaries or evidence blocks in one
    ``session_context`` string without the agent conflating them.
    """
    content = content.strip()
    return f"[begin {label} {index}]\n\n{content}\n\n[end {label} {index}]"


def wrap_contexts(label: str, blocks: list[str]) -> str:
    """Wrap an ordered list of context blocks, numbered contiguously from 1.

    Empty/whitespace-only blocks are dropped. Remaining blocks are
    re-numbered so the reader sees an unbroken sequence — the original
    positions don't matter, only disambiguation between surviving blocks.
    """
    kept = [b for b in blocks if b.strip()]
    return "\n\n".join(
        wrap_context(label, block, index=i + 1)
        for i, block in enumerate(kept)
    )


def save_meeting(result: MeetingResult, out_dir: str, slug: str = "meeting") -> str:
    """Write a meeting's full discussion as a single markdown file.

    Useful when you want one consolidated transcript in addition to the
    per-turn files the runner writes. Returns the path written.
    """
    import os
    from datetime import datetime
    os.makedirs(out_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(out_dir, f"{slug}-{timestamp}.md")
    lines = [
        f"# Meeting: {result.topic}",
        f"Mode: {result.mode.value}  |  Round: {result.round_num}  |  "
        f"Turns: {len(result.turns)}",
        "",
    ]
    for i, turn in enumerate(result.turns, start=1):
        name = (
            ROLE_TEMPLATES[turn.role_id].name
            if turn.role_id in ROLE_TEMPLATES
            else turn.role_id
        )
        lines += [
            f"## Turn {i}: {name} ({turn.role_id})",
            "",
            turn.output.strip() or "_(no output captured)_",
            "",
        ]
    if result.synthesis.strip():
        lines += ["---", "", "## Synthesis", "", result.synthesis.strip(), ""]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


def _swap_prior(prompt: str, new_prior: str) -> str:
    """Replace the PRIOR AGENT OUTPUTS block with real outputs.

    The block ends at the first following all-caps section header — one of
    ``INVESTIGATION MODE:``, ``AGENDA:``, ``TASK:``, or ``OUTPUT FORMAT:``.
    Earlier versions split on ``TASK:`` alone, which broke for agenda-style
    prompts (where ``TASK:`` never appears).
    """
    marker = "PRIOR AGENT OUTPUTS:"
    if marker not in prompt:
        return prompt
    before, _, rest = prompt.partition(marker)
    # find the earliest position of any next-section header
    candidates = ["\n\nINVESTIGATION MODE:", "\n\nAGENDA:", "\n\nTASK:", "\n\nOUTPUT FORMAT:"]
    positions = [rest.find(c) for c in candidates]
    valid = [(p, c) for p, c in zip(positions, candidates) if p != -1]
    if not valid:
        # No known section header — safer to leave untouched
        return prompt
    next_start, next_marker = min(valid, key=lambda x: x[0])
    # `next_marker` begins with "\n\n"; keep one newline-pair of separation
    after_prior = rest[next_start + 2:]  # strip leading "\n\n"
    return f"{before}{marker}\n{new_prior}\n\n{after_prior}"


__all__ = [
    "adversarial_inject",
    "build_meeting",
    "build_merge_meeting",
    "compose_turns",
    "merge_outputs",
    "save_meeting",
    "wrap_context",
    "wrap_contexts",
]
