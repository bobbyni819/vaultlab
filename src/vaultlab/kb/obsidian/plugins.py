"""Community plugin enable list + install instructions.

Obsidian community plugins (Advanced URI, Dataview, Templater) cannot be
*downloaded* programmatically without violating Obsidian's plugin distribution
model — users must install them via the in-app Community Plugins browser.

What this module DOES do:

- Write ``.obsidian/community-plugins.json`` listing the plugin IDs to enable.
  When the user installs them, they're auto-enabled.
- Write per-plugin default config under ``.obsidian/plugins/<id>/data.json``
  (only if the user has installed the plugin — we never overwrite their config).
- Provide the install instruction list for ``docs/setup-obsidian.md``.

Why these three:

- **Advanced URI** (Vinzent03/obsidian-advanced-uri) — required for ``vaultlab kb open``
  to support new-tab opens. Without it, opens always reuse the current pane.
- **Dataview** (blacksmithgu/obsidian-dataview) — queryable wikilink graph;
  vaultlab uses Dataview blocks in ``_Index.md`` and ``_Catalog.md``.
- **Templater** (SilentVoid13/Templater) — vaultlab's frontmatter scaffolds
  use Templater for date stamps, slug generation, etc.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final


class RecommendedPlugin:
    """A community plugin vaultlab recommends + the metadata users need to install it."""

    def __init__(self, plugin_id: str, display_name: str, why: str, install_url: str) -> None:
        self.plugin_id = plugin_id
        self.display_name = display_name
        self.why = why
        self.install_url = install_url


RECOMMENDED_PLUGINS: Final[tuple[RecommendedPlugin, ...]] = (
    RecommendedPlugin(
        plugin_id="obsidian-advanced-uri",
        display_name="Advanced URI",
        why=(
            "Required for `vaultlab kb open <path>` new-tab support. "
            "Without it, every open reuses the current pane."
        ),
        install_url="https://github.com/Vinzent03/obsidian-advanced-uri",
    ),
    RecommendedPlugin(
        plugin_id="dataview",
        display_name="Dataview",
        why=(
            "Queryable wikilink graph — vaultlab uses Dataview blocks "
            "in _Index.md / _Catalog.md to materialize cross-cutting views."
        ),
        install_url="https://github.com/blacksmithgu/obsidian-dataview",
    ),
    RecommendedPlugin(
        plugin_id="templater-obsidian",
        display_name="Templater",
        why=(
            "vaultlab note templates use Templater for date stamps, "
            "slug generation, and frontmatter helpers."
        ),
        install_url="https://github.com/SilentVoid13/Templater",
    ),
)


def configure_plugins(kb_path: str | Path) -> Path:
    """Write the community-plugins enable list into the vault.

    Lists the IDs of plugins vaultlab recommends. When the user installs them via
    Obsidian's Community Plugins browser, they will be auto-enabled.

    This file is idempotent: if it already exists, we MERGE — preserving any
    plugins the user has enabled outside vaultlab's recommendations.

    Parameters
    ----------
    kb_path
        Root folder of the knowledge base.

    Returns
    -------
    Path
        Path to the written ``.obsidian/community-plugins.json``.
    """
    kb_root = Path(kb_path)
    obsidian_dir = kb_root / ".obsidian"
    if not obsidian_dir.exists():
        raise FileNotFoundError(f".obsidian/ does not exist at {kb_root}. Run init_vault first.")

    target = obsidian_dir / "community-plugins.json"
    recommended_ids = [p.plugin_id for p in RECOMMENDED_PLUGINS]

    if target.exists():
        # Merge with existing user config — never drop their plugins
        try:
            existing = json.loads(target.read_text(encoding="utf-8"))
            if not isinstance(existing, list):
                existing = []
        except json.JSONDecodeError:
            existing = []
        merged = list(dict.fromkeys([*existing, *recommended_ids]))  # de-dup, preserve order
        target.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    else:
        target.write_text(json.dumps(recommended_ids, indent=2), encoding="utf-8")

    return target


def install_instructions_markdown() -> str:
    """Return a markdown block describing how to install the recommended plugins.

    Used by ``docs/setup-obsidian.md`` and printed by ``vaultlab kb obsidian-doctor``
    when a recommended plugin is missing.
    """
    lines = [
        "## Install Obsidian community plugins",
        "",
        "vaultlab recommends three community plugins. Install via Obsidian → "
        "*Settings* → *Community plugins* → *Browse*:",
        "",
    ]
    for p in RECOMMENDED_PLUGINS:
        lines.append(f"### {p.display_name} (`{p.plugin_id}`)")
        lines.append("")
        lines.append(p.why)
        lines.append("")
        lines.append(f"Source: {p.install_url}")
        lines.append("")
    lines.append("After installing each, enable it in *Settings* → *Community plugins*.")
    lines.append(
        "vaultlab has already pre-listed them in `community-plugins.json` so they "
        "auto-enable on install."
    )
    return "\n".join(lines)
