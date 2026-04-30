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

The returned :class:`Role` is :class:`vaultlab.runner.models.Role` — the
single canonical shape in vaultlab. The loader's job is to read disk
state and project it into that class. Behaviour (e.g. ``prompt_for``)
lives on the Role itself, so callers downstream of the loader never need
to bridge between two structurally different ``Role`` types.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from vaultlab.runner.models import Mode, Role

_ROLES_DIR = Path(__file__).resolve().parent


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


def _coerce_mode(value: object) -> Mode:
    """Project a YAML scalar into the runner's ``Mode`` enum.

    YAML stores ``mode`` as a string (``"data_analysis"`` /
    ``"literature_review"``); the runner expects an enum so equality and
    set membership are unambiguous. ``Mode`` is a ``str, Enum``, so the
    string form still compares equal to the enum value for callers that
    test ``role.mode == "data_analysis"``.
    """
    if isinstance(value, Mode):
        return value
    if isinstance(value, str):
        try:
            return Mode(value)
        except ValueError as exc:
            raise ValueError(f"unknown mode value in metadata.yaml: {value!r}") from exc
    raise TypeError(f"metadata.yaml mode must be a string, got {type(value).__name__}")


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
        mode=_coerce_mode(meta.get("mode", "data_analysis")),
        icon=meta.get("icon"),
        focus_areas=list(meta.get("focus_areas") or ()),
        evaluation_criteria=list(meta.get("evaluation_criteria") or ()),
        communication_style=str(meta.get("communication_style", "")),
        output_format=str(meta.get("output_format", "")).rstrip(),
        tools_allowed=tuple(meta.get("tools_allowed") or ()),
    )


def load_all_roles() -> dict[str, Role]:
    """Load every discoverable role into a dict keyed by id."""
    return {rid: load_role(rid) for rid in list_roles()}
