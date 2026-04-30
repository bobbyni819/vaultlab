"""vaultlab.onboarding.config — ``.vaultlab-project.json`` schema + I/O.

Once ``/onboard-project`` runs, it writes a machine-readable config to
``<project-folder>/.vaultlab-project.json`` so future commands skip the
intake interview. The schema is documented in
``onboarding-audit-2026-04-30.md`` §"Proposed: ``.vaultlab-project.json``
schema".

The KB-side copy (``Wiki/Projects/<slug>/intake.md`` + START_HERE.md)
is human-readable; this file is the **machine** view: a stable JSON
contract other slash commands can rely on.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

__all__ = [
    "PROJECT_CONFIG_FILENAME",
    "PROJECT_CONFIG_SCHEMA",
    "VaultLabProjectConfig",
    "load_config",
    "save_config",
]

PROJECT_CONFIG_FILENAME = ".vaultlab-project.json"
PROJECT_CONFIG_SCHEMA = "vaultlab-project/v1"


def _today() -> str:
    return date.today().strftime("%Y-%m-%d")


@dataclass
class VaultLabProjectConfig:
    """Schema for ``.vaultlab-project.json`` per the onboarding audit.

    Fields mirror the audit doc plus a handful of provenance keys
    (``schema``, ``created``, ``last_updated``). Lists default to empty;
    dicts default to empty. Callers are expected to fill in what they
    have and leave the rest blank.
    """

    slug: str = ""
    topic: str = ""
    goal: list[str] = field(default_factory=list)
    audience: list[str] = field(default_factory=list)
    kb_root: str = ""
    project_path: str = ""
    data_dirs: list[str] = field(default_factory=list)
    validation_files: list[str] = field(default_factory=list)
    exclusions: dict[str, str | bool | int] = field(default_factory=dict)
    voice: dict[str, str | list[str]] = field(default_factory=dict)
    pi_preferences: str = ""
    deadlines: list[str] = field(default_factory=list)
    free_form: str = ""

    # Provenance
    schema: str = PROJECT_CONFIG_SCHEMA
    created: str = field(default_factory=_today)
    last_updated: str = field(default_factory=_today)

    # ---------------------------------------------------------------
    # Serialization
    # ---------------------------------------------------------------

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=False)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "VaultLabProjectConfig":
        """Build a config from a plain dict, ignoring unknown keys.

        Tolerant of older / future schema versions: fields the current
        dataclass doesn't know about are dropped silently rather than
        raising. Required fields default to empty.
        """
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------


def save_config(
    config: VaultLabProjectConfig,
    project_path: str | Path,
    *,
    filename: str = PROJECT_CONFIG_FILENAME,
) -> Path:
    """Write ``config`` to ``<project_path>/<filename>``.

    Creates the parent directory if missing. Updates ``last_updated``
    to today before writing. Returns the path written.
    """
    target_dir = Path(project_path)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / filename
    config.last_updated = _today()
    target.write_text(config.to_json() + "\n", encoding="utf-8")
    return target


def load_config(
    project_path: str | Path,
    *,
    filename: str = PROJECT_CONFIG_FILENAME,
) -> VaultLabProjectConfig | None:
    """Load ``<project_path>/<filename>``; return None if missing.

    Tolerant of unknown keys — this lets older clients read configs
    written by newer ones (forward-compat) without crashing.
    """
    p = Path(project_path) / filename
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {p}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{p} did not parse to a JSON object")
    return VaultLabProjectConfig.from_dict(data)
