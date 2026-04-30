"""Built-in role templates for VaultLab agents.

Role prompts live as markdown + YAML on disk (one directory per role)
rather than Python string literals — users edit prompts iteratively
without touching code. See `_loader.py` for the loader, and each
`<role_id>/` for the actual prompt + metadata.

The :class:`Role` returned here is :class:`vaultlab.runner.models.Role`
— a single canonical shape used throughout vaultlab. Loading a role
from disk and constructing one in code produce the same type, so the
runner can call ``role.prompt_for(...)`` regardless of where the role
came from.

Public API:
    - Role            — the canonical Role dataclass (re-exported from
                        :mod:`vaultlab.runner.models`)
    - load_role       — load one role by id
    - list_roles      — sorted list of available role ids
    - load_all_roles  — load every discoverable role into a dict
    - ROLE_TEMPLATES  — dict[role_id -> Role] of all roles on disk
    - roles_for       — canonical role set for a named meeting type
"""

from __future__ import annotations

from functools import lru_cache

from vaultlab.runner.models import Mode, Role
from vaultlab.roles._loader import (
    RoleNotFoundError,
    list_roles,
    load_all_roles,
    load_role,
)


@lru_cache(maxsize=1)
def _role_catalog() -> dict[str, Role]:
    """Cached snapshot of every role on disk, keyed by id.

    Loaded once per process. Tests that mutate role files at runtime
    can call :func:`_role_catalog.cache_clear` to force a reload.
    """
    return load_all_roles()


class _RoleTemplatesProxy:
    """Lazy view over the role catalog with dict-style access.

    Defers the markdown/YAML scan until first lookup so that importing
    :mod:`vaultlab.roles` is cheap — matters for downstream modules
    (``vaultlab.runner.meetings``) that only sometimes touch the catalog.
    """

    def __getitem__(self, role_id: str) -> Role:
        catalog = _role_catalog()
        if role_id not in catalog:
            raise KeyError(role_id)
        return catalog[role_id]

    def __contains__(self, role_id: object) -> bool:
        if not isinstance(role_id, str):
            return False
        return role_id in _role_catalog()

    def __iter__(self):
        return iter(_role_catalog())

    def __len__(self) -> int:
        return len(_role_catalog())

    def keys(self):
        return _role_catalog().keys()

    def values(self):
        return _role_catalog().values()

    def items(self):
        return _role_catalog().items()

    def get(self, role_id: str, default=None):
        return _role_catalog().get(role_id, default)


ROLE_TEMPLATES = _RoleTemplatesProxy()


# Meeting-type → role-id list. Mirrors the legacy
# ``bobby_ailab._roles.roles_for`` table; the literature-mode swap and
# critiqued_* prefix are honoured the same way.
_MEETING_TYPE_ROLES: dict[str, list[str]] = {
    "reasoning":         ["__analyst__", "domain_expert", "__critic__"],
    "synthesis":         ["synthesizer"],
    "brainstorm":        ["figure_lead", "__critic__"],
    "narrate":           ["narrator"],
    "deep_think":        ["__analyst__", "domain_expert", "__critic__", "synthesizer"],
    "team_meeting":      ["team_lead", "__analyst__", "domain_expert", "__critic__"],
    "critique":          ["domain_expert", "__critic__"],
    "figure_read":       ["figure_reader"],
    "visual_deep_think": ["__analyst__", "figure_reader", "domain_expert", "__critic__", "synthesizer"],
}


def roles_for(meeting_type: str, mode: Mode = Mode.DATA_ANALYSIS) -> list[Role]:
    """Canonical role set for a named meeting type.

    Meeting types:
        reasoning    — Analyst + Expert + Critic (adversarial 3-agent review)
        synthesis    — Synthesizer alone
        brainstorm   — FigureLead + Critic (figure plan with critique)
        narrate      — Narrator alone
        deep_think   — Analyst + Expert + Critic + Synthesizer (full cycle)
        team_meeting — TeamLead + Analyst + Expert + Critic (PI-led)
        critique     — Expert + Critic (interpretation + rigor check)
        figure_read  — FigureReader alone
        visual_deep_think — Analyst + FigureReader + Expert + Critic + Synthesizer
        critiqued_*  — pair any role with auto-critic (e.g. critiqued_domain_expert)
    """
    catalog = _role_catalog()
    analyst_id = "data_analyst" if mode == Mode.DATA_ANALYSIS else "literature_surveyor"
    critic_id = "methods_critic" if mode == Mode.DATA_ANALYSIS else "literature_critic"

    if meeting_type.startswith("critiqued_"):
        base = meeting_type[len("critiqued_"):]
        if base not in catalog:
            raise ValueError(f"unknown role for critiqued meeting: {base}")
        return [catalog[base], catalog[critic_id]]

    if meeting_type not in _MEETING_TYPE_ROLES:
        raise ValueError(f"unknown meeting type: {meeting_type}")

    resolved: list[Role] = []
    for slot in _MEETING_TYPE_ROLES[meeting_type]:
        rid = analyst_id if slot == "__analyst__" else critic_id if slot == "__critic__" else slot
        resolved.append(catalog[rid])
    return resolved


__all__ = [
    "Role",
    "RoleNotFoundError",
    "load_all_roles",
    "load_role",
    "list_roles",
    "ROLE_TEMPLATES",
    "roles_for",
]
