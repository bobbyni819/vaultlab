"""Configuration for bobby_research — load API keys from Google Drive config."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Primary config location: Google Drive
_DRIVE_CONFIG_PATH = Path("G:/My Drive/Knowledge/tools/.config/research_apis.json")

# Fallback: local user config
_LOCAL_CONFIG_DIR = Path.home() / ".config" / "bobby_research"
_LOCAL_CONFIG_FILE = _LOCAL_CONFIG_DIR / "config.json"

# Environment variable prefix for fallback
_ENV_PREFIX = "BOBBY_RESEARCH_"

_config: dict[str, Any] | None = None

_KEY_NAMES = [
    "ncbi_api_key",
    "springer_open_access_api_key",
    "springer_meta_api_key",
    "semantic_scholar_api_key",
    "elsevier_key",
]


def get_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """Load and cache the research API config.

    Resolution order:
    1. Explicit config_path argument
    2. Google Drive config file (G:/My Drive/Knowledge/tools/.config/research_apis.json)
    3. Local config file (~/.config/bobby_research/config.json)
    4. Environment variables (BOBBY_RESEARCH_NCBI_API_KEY, etc.)

    Returns:
        Dict with API keys and settings.

    Raises:
        FileNotFoundError: If no config file found and no env vars set.
    """
    global _config
    if _config is not None and config_path is None:
        return _config

    config: dict[str, Any] = {}

    # Try loading from file
    paths_to_try = []
    if config_path:
        paths_to_try.append(Path(config_path))
    paths_to_try.extend([_DRIVE_CONFIG_PATH, _LOCAL_CONFIG_FILE])

    for p in paths_to_try:
        if p.exists():
            try:
                config = json.loads(p.read_text(encoding="utf-8"))
                logger.debug("Loaded research config from %s", p)
                break
            except (json.JSONDecodeError, PermissionError) as e:
                logger.warning("Failed to read config from %s: %s", p, e)

    # Fill in missing keys from environment variables
    for key in _KEY_NAMES:
        if not config.get(key):
            env_name = _ENV_PREFIX + key.upper()
            env_val = os.environ.get(env_name, "")
            if env_val:
                config[key] = env_val
                logger.debug("Loaded %s from environment variable %s", key, env_name)

    # Validate that at least one API key is configured
    has_key = any(config.get(k) for k in _KEY_NAMES)
    if not has_key:
        raise FileNotFoundError(
            f"No research API config found. Checked:\n"
            f"  - {_DRIVE_CONFIG_PATH}\n"
            f"  - {_LOCAL_CONFIG_FILE}\n"
            f"  - Environment variables ({_ENV_PREFIX}*)\n"
            f"Create a config file with at least one API key."
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
