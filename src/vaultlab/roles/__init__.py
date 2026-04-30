"""Built-in role templates for VaultLab agents.

Role prompts live as markdown + YAML on disk (one directory per role)
rather than Python string literals — users edit prompts iteratively without
touching code. See `_loader.py` for the loader, and each `<role_id>/` for
the actual prompt + metadata.

Public API:
    - Role          — dataclass returned by load_role
    - load_role     — load one role by id
    - list_roles    — sorted list of available role ids
    - load_all_roles — load every discoverable role into a dict
"""

from __future__ import annotations

from vaultlab.roles._loader import (
    Role,
    RoleNotFoundError,
    load_all_roles,
    load_role,
    list_roles,
)

__all__ = [
    "Role",
    "RoleNotFoundError",
    "load_all_roles",
    "load_role",
    "list_roles",
]
