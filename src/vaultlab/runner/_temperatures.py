"""Temperature tuning per meeting / role — adopted from virtual-lab.

Virtual-lab uses CREATIVE_TEMPERATURE=0.8 for ideation/brainstorming and
CONSISTENT_TEMPERATURE=0.2 for synthesis, merges, and summaries. The same
logic improves vaultlab: ensemble critics want diversity (higher T);
meta-reviewers and synthesizers want coherence (lower T).

The runner reads ``temperature_for(...)`` before spawning the Agent tool.
Callers can override via an explicit ``temperature`` kwarg on Meeting builders.

Lifted from ``bobby_ailab._temperatures``. Behaviourally identical.
"""

from __future__ import annotations

from vaultlab.runner.models import MeetingMode


CONSISTENT_TEMPERATURE = 0.2
BALANCED_TEMPERATURE = 0.5
CREATIVE_TEMPERATURE = 0.8
ENSEMBLE_TEMPERATURE = 0.75  # AI-Scientist's reviewer ensemble default


# Meeting-mode defaults. Round-table and brainstorm get creative temps
# because we want divergent ideas; adversarial and synthesis want coherence.
TEMPERATURE_BY_MEETING_MODE: dict[MeetingMode, float] = {
    MeetingMode.ROUND_TABLE: CREATIVE_TEMPERATURE,
    MeetingMode.ADVERSARIAL: BALANCED_TEMPERATURE,
    MeetingMode.SYNTHESIS: CONSISTENT_TEMPERATURE,
    MeetingMode.INDIVIDUAL: BALANCED_TEMPERATURE,
    MeetingMode.TEAM: BALANCED_TEMPERATURE,
    MeetingMode.CRITIQUED: BALANCED_TEMPERATURE,
}


# Per-role overrides. Synthesizers always want low T; ideation roles want
# high T. This overrides the meeting-mode default when the role is present.
TEMPERATURE_BY_ROLE: dict[str, float] = {
    "synthesizer":          CONSISTENT_TEMPERATURE,
    "team_lead":            CONSISTENT_TEMPERATURE,
    "narrator":             CONSISTENT_TEMPERATURE,
    "methods_critic":       BALANCED_TEMPERATURE,
    "literature_critic":    BALANCED_TEMPERATURE,
    "data_analyst":         CONSISTENT_TEMPERATURE,  # analysis is deterministic
    "domain_expert":        BALANCED_TEMPERATURE,
    "literature_surveyor":  BALANCED_TEMPERATURE,
    "figure_lead":          CREATIVE_TEMPERATURE,    # ideation
    "figure_reader":        CONSISTENT_TEMPERATURE,  # observation
}


def temperature_for(
    meeting_mode: MeetingMode,
    role_id: str = "",
    ensemble: bool = False,
) -> float:
    """Pick the best temperature for a given role in a given meeting.

    Priority:
    1. If ``ensemble=True``, return ENSEMBLE_TEMPERATURE (AI-Scientist pattern —
       diverse reviewers for aggregation).
    2. Role-specific override if present.
    3. Meeting-mode default.
    4. Fallback to CONSISTENT_TEMPERATURE.
    """
    if ensemble:
        return ENSEMBLE_TEMPERATURE
    if role_id in TEMPERATURE_BY_ROLE:
        return TEMPERATURE_BY_ROLE[role_id]
    return TEMPERATURE_BY_MEETING_MODE.get(meeting_mode, CONSISTENT_TEMPERATURE)


__all__ = [
    "BALANCED_TEMPERATURE",
    "CONSISTENT_TEMPERATURE",
    "CREATIVE_TEMPERATURE",
    "ENSEMBLE_TEMPERATURE",
    "TEMPERATURE_BY_MEETING_MODE",
    "TEMPERATURE_BY_ROLE",
    "temperature_for",
]
