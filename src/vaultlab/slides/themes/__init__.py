"""vaultlab.slides.themes — theme registry.

Phase-1 ships one theme (``default``). Future themes (``conference_clean``,
``data_dense``, ``storyteller``, ``duke``) land in phase 8b — each gets one
``<name>.py`` + ``<name>.md`` pair per the markdown-as-interface principle.
"""

from __future__ import annotations

from vaultlab.slides.themes.default import DEFAULT, THEMES, Theme, get_theme

__all__ = ["DEFAULT", "THEMES", "Theme", "get_theme"]
