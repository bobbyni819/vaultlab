"""vaultlab.onboarding — fast project onboarding.

Replaces the "1-hour conversation with Claude Code" pattern with a
5-minute fillable template + a deterministic Python orchestrator. The
slash command (``.claude/commands/onboard-project.md``) reads the
filled-in intake, scans the project folder, and writes a
:class:`ProjectInit` view to the KB — then asks the user 3-5
follow-up questions instead of 30.

Three submodules:

- :mod:`vaultlab.onboarding.intake` — the filled-form data model and
  markdown round-trip.
- :mod:`vaultlab.onboarding.project_init` — the orchestrator
  (``init_project_from_intake``) plus folder scanning.
- :mod:`vaultlab.onboarding.config` — the
  ``.vaultlab-project.json`` schema and I/O helpers.

Public API:

>>> from vaultlab.onboarding import (  # doctest: +SKIP
...     IntakeForm, parse_intake_md, render_intake_template,
...     ProjectInit, init_project_from_intake, scan_project_folder,
...     VaultLabProjectConfig, save_config, load_config,
... )
"""

from __future__ import annotations

from vaultlab.onboarding.config import (
    PROJECT_CONFIG_FILENAME,
    PROJECT_CONFIG_SCHEMA,
    VaultLabProjectConfig,
    load_config,
    load_project_config_from_cwd,
    save_config,
)
from vaultlab.onboarding.intake import (
    INTAKE_SCHEMA,
    IntakeForm,
    IntakeValidationError,
    parse_intake_md,
    render_intake_template,
)
from vaultlab.onboarding.project_init import (
    FILE_TYPE_PATTERNS,
    FolderInventory,
    ProjectInit,
    copy_intake_template_to,
    init_project_from_intake,
    scan_project_folder,
)

__all__ = [
    # intake
    "INTAKE_SCHEMA",
    "IntakeForm",
    "IntakeValidationError",
    "parse_intake_md",
    "render_intake_template",
    # project_init
    "FILE_TYPE_PATTERNS",
    "FolderInventory",
    "ProjectInit",
    "copy_intake_template_to",
    "init_project_from_intake",
    "scan_project_folder",
    # config
    "PROJECT_CONFIG_FILENAME",
    "PROJECT_CONFIG_SCHEMA",
    "VaultLabProjectConfig",
    "load_config",
    "load_project_config_from_cwd",
    "save_config",
]
