"""vaultlab.kb.obsidian — Obsidian vault setup, plugin config, and deep-link open.

This subpackage owns *all* Obsidian-related setup so a fresh `git clone vaultlab`
gets the user a working Obsidian-backed KB without piecing it together by hand.

Public API:

- :func:`init_vault` — create ``.obsidian/`` config (idempotent)
- :func:`configure_plugins` — write community-plugin enable list
- :func:`write_templates` — install vaultlab note templates (frontmatter scaffolds)
- :func:`open_in_obsidian` — implement ``vaultlab kb open`` deep links
  (powers async-first auto-open per CLAUDE.md commitment 5 / AGENTS.md invariant 10)
- :func:`detect_install` — locate existing Obsidian install + report plugin state

Setup walkthrough lives in ``docs/setup-obsidian.md``.
"""

from __future__ import annotations

from vaultlab.kb.obsidian.detect import ObsidianInstall, detect_install
from vaultlab.kb.obsidian.init import init_vault
from vaultlab.kb.obsidian.open import open_in_obsidian
from vaultlab.kb.obsidian.plugins import RECOMMENDED_PLUGINS, configure_plugins
from vaultlab.kb.obsidian.templates import write_templates

__all__ = [
    "RECOMMENDED_PLUGINS",
    "ObsidianInstall",
    "configure_plugins",
    "detect_install",
    "init_vault",
    "open_in_obsidian",
    "write_templates",
]
