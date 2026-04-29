"""Vault scaffolding — write ``.obsidian/`` defaults into a KB folder.

Idempotent: never overwrites an existing config file. Safe to run on a vault that
already has Obsidian set up.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Core plugins we enable by default. Obsidian's "core" plugins are bundled with
# the app — turning them on doesn't require downloading anything.
DEFAULT_CORE_PLUGINS: tuple[str, ...] = (
    "file-explorer",
    "global-search",
    "graph",
    "backlink",
    "tag-pane",
    "page-preview",
    "outline",
    "word-count",
    "file-recovery",
    "templates",  # for the vaultlab templates module
    "command-palette",
    "switcher",
    "workspaces",
)


def init_vault(kb_path: str | Path, *, default_open_file: str = "_Index.md") -> Path:
    """Initialize Obsidian config in a KB directory.

    Creates ``.obsidian/`` with sensible defaults: app settings, appearance,
    enabled core plugins, and a workspace that opens ``default_open_file`` first.

    Parameters
    ----------
    kb_path
        Root folder of the knowledge base (e.g. ``G:/My Drive/Knowledge/research``).
    default_open_file
        Markdown file to open on first launch (relative to KB root).
        ``_Index.md`` matches vaultlab's KB convention.

    Returns
    -------
    Path
        The created ``.obsidian/`` directory.

    Examples
    --------
    >>> from vaultlab.kb.obsidian import init_vault
    >>> init_vault("/tmp/my-kb")  # doctest: +SKIP
    """
    kb_root = Path(kb_path)
    if not kb_root.exists():
        raise FileNotFoundError(f"KB root does not exist: {kb_root}")

    obsidian_dir = kb_root / ".obsidian"
    obsidian_dir.mkdir(exist_ok=True)

    _write_if_missing(
        obsidian_dir / "app.json",
        {
            "showLineNumber": True,
            "strictLineBreaks": False,
            "readableLineLength": True,
            "showFrontmatter": False,
            "foldHeading": True,
            "foldIndent": True,
            "useMarkdownLinks": False,  # prefer [[wikilinks]] for vaultlab
        },
    )

    _write_if_missing(
        obsidian_dir / "appearance.json",
        {"baseFontSize": 16, "interfaceFontSize": 14},
    )

    _write_if_missing(obsidian_dir / "core-plugins.json", list(DEFAULT_CORE_PLUGINS))

    _write_if_missing(
        obsidian_dir / "workspace.json",
        {
            "main": {
                "type": "split",
                "children": [
                    {
                        "type": "leaf",
                        "state": {
                            "type": "markdown",
                            "state": {"file": default_open_file, "mode": "preview"},
                        },
                    }
                ],
                "direction": "vertical",
            }
        },
    )

    return obsidian_dir


def _write_if_missing(path: Path, data: Any) -> None:
    """Write JSON file only if it does not already exist (idempotent)."""
    if not path.exists():
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
