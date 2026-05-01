"""vaultlab.context — per-user / per-machine context resolvers.

Currently exposes the locations registry (``locations.toml``) and the
multi-tenant KB-root resolver introduced 2026-04-30. Other context
modules (user_memory, etc.) are imported lazily by their own callers and
not re-exported here.
"""

from vaultlab.context.locations import (
    KbRootNotConfigured,
    get_path,
    load_locations,
    locations_path,
    missing_paths_grill_doc,
    register_path,
    resolve_kb_root,
)

__all__ = [
    "KbRootNotConfigured",
    "get_path",
    "load_locations",
    "locations_path",
    "missing_paths_grill_doc",
    "register_path",
    "resolve_kb_root",
]
