"""Configuration for vaultlab.research — load API keys from KB-synced config.

Resolution order (first match with at least one key wins):

1. Explicit ``config_path`` argument (test override / CLI flag)
2. ``$VAULTLAB_RESEARCH_API_CONFIG`` environment variable (full path)
3. **KB-relative path** — ``<kb_root>.parent / tools / .config / research_apis.json``,
   where ``<kb_root>`` is whatever ``resolve_kb_root()`` returns. For Bobby's
   typical layout (``G:/My Drive/Knowledge/vaultlab``) this resolves to
   ``G:/My Drive/Knowledge/tools/.config/research_apis.json``. The keys file
   lives at the *vault* level (sibling of all KBs), not inside any one KB,
   so it's shared across projects.
4. Local user config — ``~/.config/bobby_research/config.json``
5. Per-key environment variables (``BOBBY_RESEARCH_NCBI_API_KEY`` etc.)

Pre-2026-05-06 the resolver hardcoded ``G:/My Drive/Knowledge/...`` for
step 3, which broke for any user whose Drive letter wasn't G: — friction
finding #6 from the metabolism dogfood run.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Local user config (fallback, last-resort before env vars)
_LOCAL_CONFIG_DIR = Path.home() / ".config" / "bobby_research"
_LOCAL_CONFIG_FILE = _LOCAL_CONFIG_DIR / "config.json"

# Environment variable for explicit config-file path
_PATH_ENV_VAR = "VAULTLAB_RESEARCH_API_CONFIG"

# Environment variable prefix for individual API-key fallback
_ENV_PREFIX = "BOBBY_RESEARCH_"

_config: dict[str, Any] | None = None

_KEY_NAMES = [
    "ncbi_api_key",
    "springer_open_access_api_key",
    "springer_meta_api_key",
    "semantic_scholar_api_key",
    "elsevier_key",
]


def _kb_relative_config_path() -> Path | None:
    """Return ``<vault>/tools/.config/research_apis.json`` if KB-root resolves.

    The vault is the parent of the resolved KB root (matches Bobby's layout
    where all KBs are siblings under ``G:/My Drive/Knowledge/`` and shared
    productivity stuff lives in a peer ``tools/`` folder).

    Returns ``None`` if KB root can't be resolved or the resolver throws —
    this function never raises so it can be safely chained in path lookups
    even on machines where ``vaultlab init`` hasn't been run yet.
    """
    try:
        from vaultlab.context import resolve_kb_root

        kb_root = resolve_kb_root(interactive=False)
    except Exception:
        return None
    vault_root = kb_root.parent
    return vault_root / "tools" / ".config" / "research_apis.json"


def get_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """Load and cache the research API config.

    Resolution order documented at module top. Returns dict with API keys
    and settings; raises ``FileNotFoundError`` if no source has any key.
    """
    global _config
    if _config is not None and config_path is None:
        return _config

    config: dict[str, Any] = {}
    checked: list[Path] = []

    paths_to_try: list[Path] = []
    if config_path:
        paths_to_try.append(Path(config_path))

    env_path = os.environ.get(_PATH_ENV_VAR)
    if env_path:
        paths_to_try.append(Path(env_path).expanduser())

    kb_relative = _kb_relative_config_path()
    if kb_relative is not None:
        paths_to_try.append(kb_relative)

    paths_to_try.append(_LOCAL_CONFIG_FILE)

    for p in paths_to_try:
        checked.append(p)
        if p.exists():
            try:
                config = json.loads(p.read_text(encoding="utf-8"))
                logger.debug("Loaded research config from %s", p)
                break
            except (json.JSONDecodeError, PermissionError) as e:
                logger.warning("Failed to read config from %s: %s", p, e)

    # Fill in missing keys from per-key environment variables
    for key in _KEY_NAMES:
        if not config.get(key):
            env_name = _ENV_PREFIX + key.upper()
            env_val = os.environ.get(env_name, "")
            if env_val:
                config[key] = env_val
                logger.debug("Loaded %s from environment variable %s", key, env_name)

    has_key = any(config.get(k) for k in _KEY_NAMES)
    if not has_key:
        checked_str = "\n".join(f"  - {p}" for p in checked)
        raise FileNotFoundError(
            f"No research API config found. Checked:\n"
            f"{checked_str}\n"
            f"  - Environment variables ({_ENV_PREFIX}*)\n\n"
            f"Fix:\n"
            f"  - Set ${_PATH_ENV_VAR} to a config-file path, OR\n"
            f"  - Place keys at <vault>/tools/.config/research_apis.json "
            f"(the canonical KB-relative path), OR\n"
            f"  - Create {_LOCAL_CONFIG_FILE}, OR\n"
            f"  - Export per-key env vars ({_ENV_PREFIX}NCBI_API_KEY etc.)"
        )

    if config_path is None:
        _config = config
    return config


def get_key(key_name: str, config_path: str | Path | None = None) -> str:
    """Get a specific API key, or empty string if not configured."""
    config = get_config(config_path)
    return config.get(key_name, "")


def reload() -> None:
    """Force reload the config file on next access."""
    global _config
    _config = None
