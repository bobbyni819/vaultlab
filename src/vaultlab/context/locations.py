"""Per-user locations registry — declarative paths VaultLab uses across sessions.

Master plan §4b. Stores the user's standard file paths so VaultLab doesn't have
to ask the user every session where their work-log Google Doc lives, where
meeting transcripts get saved, which Drive folders correspond to which
projects, etc.

File: ``~/.config/vaultlab/locations.toml`` (per-user, per-machine; never
committed).

Public API
----------
- :func:`load_locations` — read the registry; returns an empty dict if missing
- :func:`get_path` — look up a single named path; returns ``None`` if unset
- :func:`register_path` — write/update a named path; persists to disk
- :func:`missing_paths_grill_doc` — when N+ paths are missing, write a grill
  doc rather than blocking the chat (Invariant 10)

Schema (informal — TOML sections)
---------------------------------

::

    [work_log]
    google_doc_id = "..."
    default_tab = "daily updates"

    [meetings]
    local_video_dir = "D:/MeetingVideos/"
    transcript_drive_folder_id = "..."
    transcript_drive_path = "G:/My Drive/Meetings/Transcripts/"

    [kb]
    root = "G:/My Drive/Knowledge"
    default = "research"

    [projects]
    "car-t" = "research/Wiki/Projects/car-t"

    [google_docs]
    "lab-protocols" = "..."
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - fallback for Python <3.11; vaultlab requires 3.12+
    import tomli as tomllib  # type: ignore[no-redef]


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def locations_path() -> Path:
    """Return the canonical path for ``locations.toml``.

    Honors ``$VAULTLAB_LOCATIONS`` for tests; otherwise resolves to
    ``~/.config/vaultlab/locations.toml`` (cross-platform — Path.home() is
    correct on Windows / macOS / Linux).
    """
    override = os.environ.get("VAULTLAB_LOCATIONS")
    if override:
        return Path(override)
    return Path.home() / ".config" / "vaultlab" / "locations.toml"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_locations(path: Path | None = None) -> dict[str, Any]:
    """Read ``locations.toml``. Returns ``{}`` if the file does not exist.

    Parameters
    ----------
    path
        Override location for tests. Production code leaves this as ``None``.

    Returns
    -------
    dict
        Parsed TOML as nested dicts. Top-level sections become dict keys.
    """
    target = path if path is not None else locations_path()
    if not target.exists():
        return {}
    with target.open("rb") as f:
        return tomllib.load(f)


def get_path(slug: str, *, locations: dict[str, Any] | None = None) -> str | None:
    """Look up a named path by dotted slug.

    Slugs use dots to address nested sections. Examples:

    - ``"work_log.google_doc_id"`` → ``locations["work_log"]["google_doc_id"]``
    - ``"projects.car-t"`` → ``locations["projects"]["car-t"]``
    - ``"google_docs.lab-protocols"`` → ``locations["google_docs"]["lab-protocols"]``

    Returns ``None`` when the slug is not present (does not raise — caller
    decides whether to ``missing_paths_grill_doc`` or proceed with default).

    Parameters
    ----------
    slug
        Dotted path identifier.
    locations
        Optional pre-loaded registry (avoids re-reading TOML in tight loops).

    Returns
    -------
    str | None
        The configured path, or ``None``.
    """
    if locations is None:
        locations = load_locations()
    parts = slug.split(".")
    node: Any = locations
    for part in parts:
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node if isinstance(node, str) else None


def register_path(
    slug: str,
    value: str,
    *,
    path: Path | None = None,
) -> Path:
    """Write/update a named path; create the file if missing.

    Atomic: writes to a ``.tmp`` then renames so partial-write failures don't
    corrupt the registry.

    Parameters
    ----------
    slug
        Dotted path identifier (same form as :func:`get_path`).
    value
        The path / ID / value to store.
    path
        Override location for tests.

    Returns
    -------
    Path
        Path to the (created or updated) registry file.
    """
    target = path if path is not None else locations_path()
    target.parent.mkdir(parents=True, exist_ok=True)

    locations = load_locations(target)

    parts = slug.split(".")
    if len(parts) < 2:
        raise ValueError(f"Slug must be at least 'section.key' (got {slug!r})")
    node = locations
    for part in parts[:-1]:
        sub = node.get(part)
        if not isinstance(sub, dict):
            sub = {}
            node[part] = sub
        node = sub
    node[parts[-1]] = value

    # Render TOML by hand — stdlib has no toml writer until 3.13. Keeps the
    # dependency graph clean (no extra package just for one file).
    text = _render_toml(locations)
    tmp = target.with_suffix(".toml.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, target)
    return target


def missing_paths_grill_doc(
    kb_path: Path,
    missing: list[str],
    *,
    triggered_by: str,
    auto_open: bool = True,
) -> Path | None:
    """Write a grill doc listing missing locations.

    Used when a slash command needs paths from the registry that aren't set.
    Per Invariant 10, the command does NOT block — it queues the question via
    :func:`vaultlab.kb.feedback.open_question` and proceeds with whatever
    fallback it has (or marks the dependent step as deferred).

    Parameters
    ----------
    kb_path
        KB root — needed because grill docs live under
        ``<kb>/Sources/Notes/grill-...``.
    missing
        The slugs that were looked up but returned ``None``.
    triggered_by
        Slash command / function name that triggered the lookup.
        Becomes the grill doc's context section.
    auto_open
        Whether to call ``bobby-kb open`` after writing.

    Returns
    -------
    Path | None
        Path to the grill doc; ``None`` if ``missing`` is empty.
    """
    if not missing:
        return None

    from vaultlab.kb.feedback import open_question

    questions = [
        f"What value should `{slug}` have? (Edit `~/.config/vaultlab/locations.toml` "
        f"under the appropriate section, or paste the value below.)"
        for slug in missing
    ]

    result = open_question(
        kb_path,
        slug="locations-missing",
        title="Missing entries in locations.toml",
        questions=questions,
        context=(
            f"VaultLab tried to look up {len(missing)} location slug(s) while running "
            f"`{triggered_by}` but they were not configured. Set them in "
            f"`~/.config/vaultlab/locations.toml` so future commands skip this prompt. "
            f"VaultLab kept working with whatever fallback was available; the dependent "
            f"steps may be partial until the locations are filled in."
        ),
        auto_open=auto_open,
    )
    return result.path


# ---------------------------------------------------------------------------
# Internal — minimal TOML writer
# ---------------------------------------------------------------------------


def _render_toml(data: dict[str, Any]) -> str:
    """Render a nested dict as TOML. Supports str values + nested-dict sections.

    Not a full TOML serializer — handles the schema VaultLab actually uses:
    top-level sections of (string-keyed) string values. Section names with
    ``-`` or other special chars are bracket-quoted as TOML allows.
    """
    lines: list[str] = []
    for section, contents in data.items():
        if not isinstance(contents, dict):
            # Top-level scalar — rare, but support it
            lines.append(f"{_toml_key(section)} = {_toml_value(contents)}")
            continue
        lines.append(f"[{_toml_key(section)}]")
        for key, value in contents.items():
            lines.append(f"{_toml_key(key)} = {_toml_value(value)}")
        lines.append("")  # blank line between sections
    return "\n".join(lines).rstrip() + "\n"


def _toml_key(key: str) -> str:
    """Quote keys that contain dashes or other non-bare chars."""
    if key.replace("_", "").replace("-", "").isalnum() and not key[0].isdigit():
        # Bare key allowed only for [A-Za-z0-9_-]; quote if it contains -
        if "-" in key:
            return f'"{key}"'
        return key
    return f'"{key}"'


def _toml_value(value: Any) -> str:
    if isinstance(value, str):
        # Use double quotes; escape backslashes + quotes
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    raise TypeError(f"Unsupported TOML value type: {type(value).__name__}")


__all__ = [
    "get_path",
    "load_locations",
    "locations_path",
    "missing_paths_grill_doc",
    "register_path",
]
