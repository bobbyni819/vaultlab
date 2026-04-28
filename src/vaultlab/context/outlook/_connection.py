"""Shared COM connection singleton for Outlook automation.

Provides a lazy-initialized, cached connection to the Outlook COM API
with automatic retry on stale references (e.g., after Outlook restart).
"""

from __future__ import annotations

import functools
import logging
from typing import Any

logger = logging.getLogger(__name__)

_outlook_app: Any | None = None
_namespace: Any | None = None


def get_outlook_app() -> Any:
    """Return the cached Outlook.Application COM object, creating it if needed."""
    global _outlook_app
    if _outlook_app is None:
        import win32com.client

        _outlook_app = win32com.client.Dispatch("Outlook.Application")
        logger.debug("Created Outlook.Application COM object")
    return _outlook_app


def get_namespace() -> Any:
    """Return the cached MAPI namespace, creating it if needed."""
    global _namespace
    if _namespace is None:
        app = get_outlook_app()
        _namespace = app.GetNamespace("MAPI")
        logger.debug("Created MAPI namespace")
    return _namespace


def reset() -> None:
    """Clear cached COM references (call after Outlook restart)."""
    global _outlook_app, _namespace
    _outlook_app = None
    _namespace = None
    logger.debug("Reset Outlook COM connection cache")


def _with_retry(fn):
    """Decorator that retries once on COM error after resetting the connection."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            exc_str = str(exc).lower()
            # Retry on common COM disconnection errors
            if any(
                hint in exc_str
                for hint in ("rpc server", "disconnected", "call was rejected", "co_e_")
            ):
                logger.warning("COM error in %s, resetting and retrying: %s", fn.__name__, exc)
                reset()
                return fn(*args, **kwargs)
            raise

    return wrapper
