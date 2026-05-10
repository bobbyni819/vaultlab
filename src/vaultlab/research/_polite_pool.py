"""Centralized polite-pool identity for outbound HTTP requests.

Many literature APIs (OpenAlex, Unpaywall, CrossRef) request that
clients identify themselves via a User-Agent header + a ``mailto:``
contact email — the "polite pool" — for higher rate limits and better
operator support.

vaultlab historically hardcoded the maintainer's email here. That was
fine while the package was single-user, but the moment it ships to
real users it means every install attributes its API queries back to
the maintainer. This module makes the polite-pool identity
configurable per-user via env var + a sensible default that clearly
signals "this user hasn't set their own."

Resolution order:
1. ``VAULTLAB_POLITE_POOL_EMAIL`` env var (per-user override)
2. ``email`` field in ``~/.config/vaultlab/config.json``
3. The fallback ``vaultlab-anonymous@users.noreply.github.com``
   (signals "unconfigured" to API operators while still being a
   valid mailable address)

Public API
----------
- :func:`get_polite_pool_email()` → str
- :func:`get_user_agent(component: str = "vaultlab")` → str

Usage
-----
::

    from vaultlab.research._polite_pool import get_polite_pool_email, get_user_agent
    headers = {"User-Agent": get_user_agent("vaultlab-research")}
    params = {"email": get_polite_pool_email()}

Why this matters
----------------
A user running ``/lit-arc`` on their own laptop should attribute its
OpenAlex / Unpaywall / CrossRef queries to *them*, not to whoever
authored vaultlab. This module makes that possible without anyone
having to touch source code.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

__all__ = ["get_polite_pool_email", "get_user_agent"]


# Fallback used when the user hasn't configured a polite-pool email. The
# domain ``users.noreply.github.com`` is GitHub's published no-reply
# convention — valid as a mailto target but signals "unset" to API
# operators who pay attention to the polite-pool field.
_DEFAULT_EMAIL = "vaultlab-anonymous@users.noreply.github.com"

# Pinned in the User-Agent string — matches the package version in
# pyproject.toml at release time. Kept here rather than computed so the
# User-Agent doesn't depend on a runtime version lookup that could fail.
_USER_AGENT_VERSION = "0.0.3"

_ENV_VAR = "VAULTLAB_POLITE_POOL_EMAIL"
_CONFIG_PATH = Path.home() / ".config" / "vaultlab" / "config.json"
_CONFIG_KEY = "polite_pool_email"


def get_polite_pool_email() -> str:
    """Return the configured polite-pool email for this user.

    Resolution order:

    1. ``VAULTLAB_POLITE_POOL_EMAIL`` env var
    2. ``polite_pool_email`` key in ``~/.config/vaultlab/config.json``
    3. The unconfigured-fallback (``vaultlab-anonymous@users.noreply.github.com``)
    """
    env_val = os.environ.get(_ENV_VAR, "").strip()
    if env_val:
        return env_val

    if _CONFIG_PATH.exists():
        try:
            cfg = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(
                "Could not read polite-pool config at %s: %s. Falling back to default.",
                _CONFIG_PATH,
                exc,
            )
        else:
            if isinstance(cfg, dict):
                candidate = cfg.get(_CONFIG_KEY)
                if isinstance(candidate, str) and candidate.strip():
                    return candidate.strip()

    return _DEFAULT_EMAIL


def get_user_agent(component: str = "vaultlab") -> str:
    """Return a User-Agent string that includes the polite-pool email.

    Format: ``"<component>/<version> (mailto:<email>)"``.
    """
    email = get_polite_pool_email()
    return f"{component}/{_USER_AGENT_VERSION} (mailto:{email})"
