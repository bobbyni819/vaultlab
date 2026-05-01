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
- :func:`resolve_kb_root` — multi-tenant KB-root resolution (env var →
  vaultlab config → bobby_kb compat → first-run prompt). The single canonical
  way every orchestrator and slash command should obtain ``kb_root`` —
  introduced 2026-04-30 to make vaultlab installable for users other than
  Bobby. See ``Sources/Notes/grill-multi-tenant-routing-2026-04-30.md``
  Layer A for the design, Q1-Q5 for the resolved decisions.
- :exc:`KbRootNotConfigured` — raised by :func:`resolve_kb_root` when no
  source resolves and the runner is non-interactive.

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

import json
import os
import sys
import tomllib
from pathlib import Path
from typing import Any

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
    if isinstance(value, int | float):
        return str(value)
    raise TypeError(f"Unsupported TOML value type: {type(value).__name__}")


# ---------------------------------------------------------------------------
# Multi-tenant KB-root resolution (Layer A — added 2026-04-30)
# ---------------------------------------------------------------------------
#
# Design source: ``Sources/Notes/grill-multi-tenant-routing-2026-04-30.md``
# §6 (proposal). Resolution chain (first match wins):
#
#   1. Explicit ``kb_root=`` arg (test override / CLI flag)
#   2. ``$VAULTLAB_KB_ROOT`` env var
#   3. ``~/.config/vaultlab/locations.toml`` ``[paths] kb_root`` (and the
#      legacy ``[kb] root`` location for compat with prior writes)
#   4. ``~/.config/bobby_kb/config.json`` ``root`` (+ ``default_kb`` if set —
#      compat fallback so Bobby's existing setup keeps working invisibly).
#      Never imports ``bobby_kb`` itself; reads the JSON directly to avoid a
#      hard dependency on a package public users will not have installed.
#   5. First-run prompt when interactive AND none of the above resolved.
#      Default offered: ``~/vaultlab-kb/``. The chosen path is persisted to
#      ``~/.config/vaultlab/locations.toml`` under ``[paths] kb_root`` so the
#      prompt fires only once.
#   6. Non-interactive + nothing resolved → raise :exc:`KbRootNotConfigured`
#      with a friendly hint pointing at ``vaultlab init``.
#
# Bobby's machine has only the bobby_kb config (step 4). New users will
# typically land on step 5 once and then step 3 forever after.

# Default KB root offered to new users at the first-run prompt. Per Bobby's
# Q2 in the grill doc — namespaced, simple, cross-platform; doesn't conflict
# with ``~/Documents`` (which on some Windows setups is OneDrive-synced and
# on Linux may not exist).
_DEFAULT_KB_ROOT_NAME = "vaultlab-kb"


class KbRootNotConfigured(RuntimeError):
    """No KB root could be resolved and the runner is non-interactive.

    Carries :attr:`suggested_default` so callers (CLI, slash commands) can
    surface a one-key-accept prompt without re-deriving the default.
    """

    def __init__(
        self,
        message: str | None = None,
        *,
        suggested_default: Path | None = None,
    ) -> None:
        if message is None:
            message = (
                "No vaultlab KB root configured. Run `vaultlab init` to choose "
                "one, or set the VAULTLAB_KB_ROOT environment variable, or "
                "write [paths] kb_root in ~/.config/vaultlab/locations.toml."
            )
        super().__init__(message)
        self.suggested_default = suggested_default or (Path.home() / _DEFAULT_KB_ROOT_NAME)


def _bobby_kb_root_from_config() -> Path | None:
    """Read ``~/.config/bobby_kb/config.json`` (if present) and return the
    KB root.

    bobby_kb's config stores ``root`` (parent of all KBs) and optionally
    ``default_kb`` (which subfolder is the active one). For Bobby's machine
    today: ``root="G:/My Drive/Knowledge"``, ``default_kb="vaultlab"`` →
    returns ``Path("G:/My Drive/Knowledge/vaultlab")``.

    Returns ``None`` when:
    - the file does not exist
    - the file is unreadable / malformed (we never want this compat bridge
      to crash the resolver)
    """
    cfg_path = Path.home() / ".config" / "bobby_kb" / "config.json"
    if not cfg_path.exists():
        return None
    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    root = data.get("root")
    if not isinstance(root, str) or not root:
        return None
    default_kb = data.get("default_kb")
    if isinstance(default_kb, str) and default_kb:
        return Path(root) / default_kb
    return Path(root)


def _is_interactive() -> bool:
    """Return whether stdin appears to be a TTY."""
    try:
        return sys.stdin.isatty()
    except (AttributeError, ValueError):  # pragma: no cover — defensive
        return False


def _prompt_for_kb_root(
    *,
    suggested_default: Path,
    input_fn: Any | None = None,
) -> Path:
    """Ask the user where the KB should live; return the chosen path.

    Bare ``Enter`` accepts ``suggested_default``. The function only handles
    the prompt itself — persistence is the caller's responsibility (see
    :func:`resolve_kb_root`).
    """
    reader = input_fn if input_fn is not None else input
    prompt = (
        f"\nvaultlab: where should your knowledge base live?\n"
        f"  (press Enter for default: {suggested_default})\n"
        f"  KB path: "
    )
    raw = reader(prompt)
    chosen = raw.strip() or str(suggested_default)
    return Path(chosen).expanduser()


def resolve_kb_root(
    *,
    explicit: str | Path | None = None,
    interactive: bool | None = None,
    input_fn: Any | None = None,
    persist_first_run: bool = True,
) -> Path:
    """Resolve the canonical vaultlab KB root.

    Resolution chain (first match wins):

    1. ``explicit`` argument (test override; CLI flag).
    2. ``$VAULTLAB_KB_ROOT`` environment variable.
    3. ``~/.config/vaultlab/locations.toml`` — ``[paths] kb_root``, with
       ``[kb] root`` as a legacy fallback within the same file.
    4. ``~/.config/bobby_kb/config.json`` — Bobby's existing setup keeps
       working without code changes.
    5. First-run prompt (only when ``interactive`` is True). Default
       offered: ``~/vaultlab-kb/``. Result is persisted to
       ``locations.toml`` so this fires exactly once per machine.
    6. Otherwise: raise :exc:`KbRootNotConfigured`.

    Parameters
    ----------
    explicit
        If given, returned as-is (after :class:`Path` conversion). Lets
        tests / CLI flags bypass the resolution chain.
    interactive
        Whether the runner may prompt the user. ``None`` (default) →
        auto-detect via ``sys.stdin.isatty()``. Pass ``False`` from tests
        and from non-interactive scripts to force the failure path.
    input_fn
        Override for ``builtins.input`` — useful for tests.
    persist_first_run
        When ``True`` (default), a successful first-run prompt writes the
        chosen path to ``~/.config/vaultlab/locations.toml``. Disable in
        tests that examine prompt behaviour without touching the user's
        real config.

    Returns
    -------
    Path
        Absolute :class:`Path` for the KB root. May or may not exist on
        disk — :func:`resolve_kb_root` does not auto-create directories
        (per Q1/Q3 in the grill doc: read-side never magic-creates).

    Raises
    ------
    KbRootNotConfigured
        When no source resolves and ``interactive`` is False (or stdin is
        not a TTY).
    """
    # 1. Explicit override
    if explicit is not None:
        return Path(explicit).expanduser()

    # 2. Environment variable
    env_value = os.environ.get("VAULTLAB_KB_ROOT")
    if env_value:
        return Path(env_value).expanduser()

    # 3. Vaultlab's own locations.toml
    locations = load_locations()
    # New canonical location: [paths] kb_root
    cfg_value = get_path("paths.kb_root", locations=locations)
    if cfg_value:
        return Path(cfg_value).expanduser()
    # Legacy fallback within same file: [kb] root (was Bobby's pre-2026-04-30
    # convention; surfaced in the grill doc and several existing slash
    # commands)
    legacy_value = get_path("kb.root", locations=locations)
    if legacy_value:
        # If [kb] default is also set, treat [kb] root as a parent and
        # combine — mirrors bobby_kb's root + default_kb shape.
        legacy_default = get_path("kb.default", locations=locations)
        if legacy_default:
            return (Path(legacy_value) / legacy_default).expanduser()
        return Path(legacy_value).expanduser()

    # 4. bobby_kb compat fallback
    bobby_kb_root = _bobby_kb_root_from_config()
    if bobby_kb_root is not None:
        return bobby_kb_root.expanduser()

    # 5. First-run prompt
    suggested = Path.home() / _DEFAULT_KB_ROOT_NAME
    can_prompt = interactive if interactive is not None else _is_interactive()
    if can_prompt:
        chosen = _prompt_for_kb_root(suggested_default=suggested, input_fn=input_fn)
        if persist_first_run:
            try:
                register_path("paths.kb_root", str(chosen))
            except Exception:  # pragma: no cover — never block on persistence
                # If persistence fails (read-only home dir, etc.) we still
                # honour the user's choice for this run.
                pass
        return chosen

    # 6. Non-interactive + nothing resolved
    raise KbRootNotConfigured(suggested_default=suggested)


__all__ = [
    "KbRootNotConfigured",
    "get_path",
    "load_locations",
    "locations_path",
    "missing_paths_grill_doc",
    "register_path",
    "resolve_kb_root",
]
