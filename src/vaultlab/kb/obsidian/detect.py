"""Detect existing Obsidian install and recommended-plugin state.

Used by ``vaultlab kb obsidian-doctor`` (a planned slash command) to tell the
user whether their Obsidian setup is ready for vaultlab's auto-open behavior.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from vaultlab.kb.obsidian.plugins import RECOMMENDED_PLUGINS


@dataclass
class ObsidianInstall:
    """Snapshot of the user's Obsidian setup, as detected from disk.

    Attributes
    ----------
    found
        Whether Obsidian is installed at all (binary or config present).
    binary_path
        Path to the Obsidian executable, if found. Used by
        :func:`vaultlab.kb.obsidian.open.open_in_obsidian` for direct launches.
    config_path
        Path to ``obsidian.json`` (the Obsidian app config that lists vaults).
    vault_root
        The currently-open vault, if any.
    vault_name
        Vault display name (folder basename).
    enabled_plugins
        Plugin IDs marked enabled in ``community-plugins.json`` for the open vault.
    missing_recommended
        Recommended plugins (from ``RECOMMENDED_PLUGINS``) that are not enabled.
    """

    found: bool = False
    binary_path: Path | None = None
    config_path: Path | None = None
    vault_root: Path | None = None
    vault_name: str | None = None
    enabled_plugins: list[str] = field(default_factory=list)
    missing_recommended: list[str] = field(default_factory=list)


def detect_install() -> ObsidianInstall:
    """Locate Obsidian + report on plugin state.

    Returns an :class:`ObsidianInstall` with whatever could be found. Never
    raises — partial data still useful for diagnostics.
    """
    install = ObsidianInstall()

    # Binary
    binary_candidates = [
        Path.home() / "AppData" / "Local" / "Programs" / "Obsidian" / "Obsidian.exe",
        Path("/Applications/Obsidian.app/Contents/MacOS/Obsidian"),
        Path("/usr/bin/obsidian"),
        Path("/opt/Obsidian/obsidian"),
    ]
    for candidate in binary_candidates:
        if candidate.exists():
            install.binary_path = candidate
            install.found = True
            break

    # Config
    config_candidates = [
        Path.home() / "AppData" / "Roaming" / "obsidian" / "obsidian.json",
        Path.home() / "Library" / "Application Support" / "obsidian" / "obsidian.json",
        Path.home() / ".config" / "obsidian" / "obsidian.json",
    ]
    for cfg in config_candidates:
        if cfg.exists():
            install.config_path = cfg
            install.found = True
            break

    # Vault info
    if install.config_path is not None:
        try:
            data = json.loads(install.config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
        vaults = data.get("vaults", {})
        for info in vaults.values():
            if info.get("open") and "path" in info:
                install.vault_root = Path(info["path"])
                install.vault_name = install.vault_root.name
                break
        if install.vault_root is None:
            for info in vaults.values():
                if "path" in info:
                    install.vault_root = Path(info["path"])
                    install.vault_name = install.vault_root.name
                    break

    # Plugin state — read community-plugins.json from the open vault
    if install.vault_root is not None:
        plugins_file = install.vault_root / ".obsidian" / "community-plugins.json"
        if plugins_file.exists():
            try:
                enabled = json.loads(plugins_file.read_text(encoding="utf-8"))
                if isinstance(enabled, list):
                    install.enabled_plugins = [str(p) for p in enabled]
            except json.JSONDecodeError:
                install.enabled_plugins = []

    install.missing_recommended = [
        p.plugin_id for p in RECOMMENDED_PLUGINS if p.plugin_id not in install.enabled_plugins
    ]

    return install


def summarize_install(install: ObsidianInstall) -> str:
    """Render an ObsidianInstall as a human-readable diagnostic string."""
    lines = ["Obsidian install report:"]
    if not install.found:
        lines.append("  ❌ Not found. Install from https://obsidian.md/")
        return "\n".join(lines)
    lines.append(
        f"  ✅ Binary: {install.binary_path or '(not on disk; URL handler may still work)'}"
    )
    lines.append(f"  ✅ Config: {install.config_path}")
    if install.vault_root is None:
        lines.append("  ⚠️  No vault detected. Open a vault in Obsidian first.")
    else:
        lines.append(f"  ✅ Open vault: {install.vault_name} → {install.vault_root}")
    if install.missing_recommended:
        lines.append("  ⚠️  Missing recommended plugins:")
        for pid in install.missing_recommended:
            lines.append(f"       - {pid}")
        lines.append("       → Install via Obsidian → Settings → Community plugins → Browse.")
    else:
        lines.append("  ✅ All recommended plugins enabled.")
    return "\n".join(lines)


__all__ = ["ObsidianInstall", "detect_install", "summarize_install"]


if __name__ == "__main__":  # pragma: no cover - manual diagnostic invocation
    print(summarize_install(detect_install()))
    sys.exit(0)
