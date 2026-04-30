"""Core data models for the vaultlab orchestration runner.

These are the user-facing data classes consumed by the runner, by future
slash commands, and by code that builds meetings programmatically. They are
intentionally PUBLIC (no underscore prefix on the module): callers will write::

    from vaultlab.runner.models import Agenda, Meeting, MeetingMode, Role

Lifted from ``bobby_ailab._models`` (see migration spec). Kept behaviourally
identical — adding fields here is a runner change, not a refactor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Mode(str, Enum):
    """Project reasoning mode — determines which role variant runs."""

    DATA_ANALYSIS = "data_analysis"
    LITERATURE_REVIEW = "literature_review"


class InvestigationMode(str, Enum):
    """Is there a committed direction to build on, or are we exploring?

    EXPLORATORY — no prior direction; survey the data, catalog what's there,
      identify the strongest leads. Analyst starts broad, Synthesizer proposes
      direction candidates, outputs are survey-style with many candidates.

    DIRECTED — an existing direction exists (prior finding, hypothesis, or
      work-in-progress); tighten and defend it. Analyst targets specific
      claims, Critic stress-tests them, Synthesizer strengthens narrative
      arc around the known direction.
    """

    EXPLORATORY = "exploratory"
    DIRECTED = "directed"


class MeetingMode(str, Enum):
    """How roles in a meeting relate to each other's outputs."""

    ROUND_TABLE = "round_table"       # parallel, blind; used for broad surveys
    ADVERSARIAL = "adversarial"       # sequential, each sees prior outputs
    SYNTHESIS = "synthesis"           # single role integrates across all inputs
    INDIVIDUAL = "individual"         # one-on-one with a specific role
    TEAM = "team"                     # lead opens, members respond, lead synthesizes
    CRITIQUED = "critiqued"           # role + always-on critic (adopted from virtual-lab individual meetings)


@dataclass
class Agenda:
    """Structured meeting agenda — adopted from virtual-lab.

    An Agenda is what every agent sees as the shared frame: what we're
    discussing (statement), what must be answered (questions), and what rules
    must be followed (rules). Injecting it into every prompt keeps agents
    aligned — each one answers the same questions with the same constraints.

    `investigation_mode` distinguishes exploratory vs directed work so the
    Analyst knows whether to survey-vs-test and the Synthesizer knows whether
    to propose-direction vs strengthen-direction.
    """

    topic: str
    statement: str = ""
    questions: list[str] = field(default_factory=list)
    rules: list[str] = field(default_factory=list)
    investigation_mode: InvestigationMode = InvestigationMode.DIRECTED

    @classmethod
    def from_task(cls, topic: str, task: str) -> Agenda:
        """Lift a free-form task string into a minimal agenda."""
        return cls(topic=topic, statement=task)

    def render(self) -> str:
        """Render the agenda block as it appears in prompts."""
        parts = []
        mode_header = f"INVESTIGATION MODE: {self.investigation_mode.value.upper()}"
        if self.investigation_mode == InvestigationMode.EXPLORATORY:
            mode_header += " — no committed direction yet; survey broadly, identify the strongest leads, propose candidate directions for follow-up. Do not pretend conviction you do not have."
        else:
            mode_header += " — a direction has been committed; your job is to enrich, harden, and defend it. Test against alternatives, tighten evidence, strengthen narrative — not start over."
        parts.append(mode_header)
        if self.statement.strip():
            parts.append("AGENDA:\n" + self.statement.strip())
        if self.questions:
            numbered = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(self.questions))
            parts.append("AGENDA QUESTIONS (must be answered):\n" + numbered)
        if self.rules:
            numbered = "\n".join(f"{i + 1}. {r}" for i, r in enumerate(self.rules))
            parts.append("AGENDA RULES (must be followed):\n" + numbered)
        return "\n\n".join(parts)


@dataclass
class Role:
    """A named agent persona with a specific posture.

    This is the canonical Role shape in vaultlab. Loaded from
    ``vaultlab.roles`` (markdown + YAML on disk per Invariant 7) and
    consumed by the runner via :meth:`prompt_for` to render per-task
    system prompts that wrap the Agenda block.
    """

    id: str
    name: str
    system_prompt: str
    description: str = ""
    focus_areas: list[str] = field(default_factory=list)
    evaluation_criteria: list[str] = field(default_factory=list)
    communication_style: str = ""
    mode: Mode = Mode.DATA_ANALYSIS
    output_format: str = ""
    icon: Optional[str] = None
    tools_allowed: tuple[str, ...] = field(default_factory=tuple)

    def prompt_for(
        self,
        session_context: str,
        task: str | Agenda,
        prior_outputs: str = "",
    ) -> str:
        agenda = task if isinstance(task, Agenda) else Agenda.from_task(topic="", task=task)
        parts = [self.system_prompt.rstrip(), "", "CONTEXT:", session_context.strip()]
        if prior_outputs.strip():
            parts += ["", "PRIOR AGENT OUTPUTS:", prior_outputs.strip()]
        rendered_agenda = agenda.render()
        if rendered_agenda:
            parts += ["", rendered_agenda]
        else:
            parts += ["", f"TASK: {agenda.statement.strip() or agenda.topic.strip()}"]
        if self.output_format.strip():
            parts += ["", "OUTPUT FORMAT:", self.output_format.strip()]
        return "\n".join(parts)


@dataclass
class MeetingTurn:
    """One role's turn in a meeting."""

    role_id: str
    prompt: str
    output: str = ""
    output_path: str = ""


@dataclass
class Meeting:
    """A multi-role session configuration."""

    topic: str
    mode: MeetingMode
    roles: list[Role]
    session_context: str
    round_num: int = 1
    prior_summary: str = ""
    agenda: Optional[Agenda] = None


@dataclass
class MeetingResult:
    """Outcome of a meeting run."""

    topic: str
    mode: MeetingMode
    round_num: int
    turns: list[MeetingTurn]
    synthesis: str = ""


__all__ = [
    "Agenda",
    "InvestigationMode",
    "Meeting",
    "MeetingMode",
    "MeetingResult",
    "MeetingTurn",
    "Mode",
    "Role",
]
