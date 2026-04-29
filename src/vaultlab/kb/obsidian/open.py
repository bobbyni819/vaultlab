"""``vaultlab kb open`` — deep-link a markdown file into Obsidian.

Powers the **async-first auto-open** behavior (CLAUDE.md commitment 5,
AGENTS.md invariant 10): every slash command that writes a grill doc, decisions
log, or START_HERE update tells the user ``bobby-kb open <path>`` so they can
read on their schedule.

Two open modes:

- **New tab** (default) — uses the Advanced URI plugin
  (``obsidian://advanced-uri?vault=...&filepath=...&openmode=tab``).
  Without the plugin, falls back to the native scheme.
- **Current pane** — native ``obsidian://open?vault=...&file=...``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple
from urllib.parse import quote


class OpenResult(NamedTuple):
    """Outcome of an open call — useful for tests and the CLI return path."""

    url: str
    file_path: Path | None
    new_tab: bool
    success: bool
    message: str


def open_in_obsidian(
    rel_path: str,
    *,
    vault_root: Path | None = None,
    vault_name: str | None = None,
    new_tab: bool = True,
    verify_exists: bool = True,
    launcher: Callable[[str], None] | None = None,
) -> OpenResult:
    """Open a vault-relative path in Obsidian via deep link.

    Parameters
    ----------
    rel_path
        Path relative to the vault root, with or without a ``.md`` extension.
        Forward or backward slashes both accepted.
    vault_root
        Vault root on disk. If omitted, auto-detected from
        ``~/AppData/Roaming/obsidian/obsidian.json`` (Windows) or platform
        equivalents.
    vault_name
        Vault name as Obsidian sees it (the folder basename by default). Only
        needed if you want to override auto-detect.
    new_tab
        If ``True`` (default), use Advanced URI to open in a new tab. If
        ``False``, use the native scheme (current pane).
    verify_exists
        If ``True``, confirm the target file exists on disk before launching.
        Set to ``False`` when ``vault_root`` cannot be determined (CI, etc.).
    launcher
        Internal hook for tests — when set, called with the constructed URL
        instead of opening it. Allows verification without launching Obsidian.

    Returns
    -------
    OpenResult
        Includes the constructed URL, resolved file path (if known), and
        a success flag.
    """
    # 1. Resolve vault root + name
    if vault_root is None:
        vault_root = _autodetect_vault_root()
    if vault_root is not None and vault_name is None:
        vault_name = vault_root.name
    if vault_name is None:
        vault_name = "Knowledge"  # last-resort default

    # 2. Normalize the relative path
    norm = rel_path.replace("\\", "/").strip("/")
    if norm.endswith(".md"):
        norm = norm[:-3]

    # 3. Optionally verify the file exists
    file_path: Path | None = None
    if vault_root is not None:
        candidate = vault_root / f"{norm}.md"
        if verify_exists and not candidate.exists():
            return OpenResult(
                url="",
                file_path=candidate,
                new_tab=new_tab,
                success=False,
                message=f"File not found: {candidate}",
            )
        file_path = candidate

    # 4. Build the deep-link URL
    encoded = quote(norm)
    if new_tab:
        url = f"obsidian://advanced-uri?vault={quote(vault_name)}&filepath={encoded}&openmode=tab"
    else:
        url = f"obsidian://open?vault={quote(vault_name)}&file={encoded}"

    # 5. Launch (or stub for tests)
    if launcher is not None:
        launcher(url)
        return OpenResult(
            url=url,
            file_path=file_path,
            new_tab=new_tab,
            success=True,
            message="Stub launcher invoked.",
        )

    success, msg = _launch(url)
    return OpenResult(url=url, file_path=file_path, new_tab=new_tab, success=success, message=msg)


def _autodetect_vault_root() -> Path | None:
    """Read Obsidian's config to find the open vault. Cross-platform."""
    config_paths = [
        Path.home() / "AppData" / "Roaming" / "obsidian" / "obsidian.json",  # Windows
        Path.home() / "Library" / "Application Support" / "obsidian" / "obsidian.json",  # macOS
        Path.home() / ".config" / "obsidian" / "obsidian.json",  # Linux
    ]
    for cfg in config_paths:
        if cfg.exists():
            try:
                data = json.loads(cfg.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            vaults = data.get("vaults", {})
            # Prefer the currently-open vault
            for info in vaults.values():
                if info.get("open") and "path" in info:
                    return Path(info["path"])
            # Fallback: first vault listed
            for info in vaults.values():
                if "path" in info:
                    return Path(info["path"])
    return None


def _launch(url: str) -> tuple[bool, str]:
    """Hand the URL to the OS handler. Returns (success, message)."""
    if sys.platform == "win32":
        # Try the Obsidian binary directly — most reliable on Windows
        obsidian_exe = Path.home() / "AppData" / "Local" / "Programs" / "Obsidian" / "Obsidian.exe"
        if obsidian_exe.exists():
            try:
                subprocess.Popen(
                    [str(obsidian_exe), url],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return True, "Launched via Obsidian.exe"
            except OSError as e:
                return False, f"Subprocess launch failed: {e}"
        # Fall back to the URL handler
        try:
            os.startfile(url)  # type: ignore[attr-defined]  # Windows-only API
            return True, "Launched via URL handler"
        except OSError as e:
            return False, f"URL handler failed: {e}"
    elif sys.platform == "darwin":
        result = subprocess.run(["open", url], check=False)
        return result.returncode == 0, f"open exit={result.returncode}"
    else:
        result = subprocess.run(["xdg-open", url], check=False)
        return result.returncode == 0, f"xdg-open exit={result.returncode}"
