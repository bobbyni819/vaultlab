"""Markdown + YAML role template loader.

Per VaultLab Invariant 7 ("markdown is the user-facing interface"), role
prompts live as plain markdown files alongside a YAML metadata sidecar.
This module discovers role packages on disk, parses them, and returns
typed `Role` dataclass instances.

Layout (one directory per role):

    vaultlab/roles/
      <role_id>/
        prompt.md       # the system prompt (verbatim text the LLM sees)
        metadata.yaml   # name, description, eval criteria, ...

Public API:
    - Role           — dataclass with prompt + metadata fields
    - load_role(id)  — load one role by directory name
    - list_roles()   — sorted list of available role ids
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

_ROLES_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Role:
    """A named agent persona loaded from prompt.md + metadata.yaml.

    Field semantics mirror the legacy `bobby_ailab._models.Role` so existing
    pipeline code can swap in this loader with minimal change. The prompt
    body lives in `system_prompt`; everything else comes from metadata.yaml.
    """

    id: str
    name: str
    system_prompt: str
    description: str = ""
    mode: str = "data_analysis"
    icon: Optional[str] = None
    focus_areas: tuple[str, ...] = field(default_factory=tuple)
    evaluation_criteria: tuple[str, ...] = field(default_factory=tuple)
    communication_style: str = ""
    output_format: str = ""
    tools_allowed: tuple[str, ...] = field(default_factory=tuple)


class RoleNotFoundError(KeyError):
    """Raised when load_role is called with an unknown role id."""


def _role_dir(role_id: str) -> Path:
    return _ROLES_DIR / role_id


def _is_role_dir(path: Path) -> bool:
    return (
        path.is_dir()
        and not path.name.startswith("_")
        and not path.name.startswith(".")
        and (path / "prompt.md").is_file()
        and (path / "metadata.yaml").is_file()
    )


def list_roles() -> list[str]:
    """Return sorted list of role ids discovered on disk."""
    return sorted(p.name for p in _ROLES_DIR.iterdir() if _is_role_dir(p))


def load_role(role_id: str) -> Role:
    """Load a single role by id (directory name).

    Raises RoleNotFoundError if the directory or its files are missing.
    """
    role_dir = _role_dir(role_id)
    if not _is_role_dir(role_dir):
        raise RoleNotFoundError(f"role not found: {role_id!r} (looked in {role_dir})")

    prompt_text = (role_dir / "prompt.md").read_text(encoding="utf-8").strip()

    with (role_dir / "metadata.yaml").open(encoding="utf-8") as f:
        meta = yaml.safe_load(f) or {}

    if not isinstance(meta, dict):
        raise ValueError(f"metadata.yaml for {role_id!r} must be a mapping, got {type(meta).__name__}")

    # Allow metadata to override the directory name as id, but warn-via-mismatch.
    declared_id = str(meta.get("id", role_id))

    return Role(
        id=declared_id,
        name=str(meta.get("name", role_id.replace("_", " ").title())),
        system_prompt=prompt_text,
        description=str(meta.get("description", "")),
        mode=str(meta.get("mode", "data_analysis")),
        icon=meta.get("icon"),
        focus_areas=tuple(meta.get("focus_areas") or ()),
        evaluation_criteria=tuple(meta.get("evaluation_criteria") or ()),
        communication_style=str(meta.get("communication_style", "")),
        output_format=str(meta.get("output_format", "")).rstrip(),
        tools_allowed=tuple(meta.get("tools_allowed") or ()),
    )


def load_all_roles() -> dict[str, Role]:
    """Load every discoverable role into a dict keyed by id."""
    return {rid: load_role(rid) for rid in list_roles()}
