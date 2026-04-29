"""Source-type detection and routing.

The dispatcher inspects the input — file path, URL string, DOI prefix —
and calls the right ingestor. New ingestors register via the
:func:`register` decorator pattern; the dispatcher keeps a stable registry
that the ``/kb-ingest`` slash command can introspect.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

from vaultlab.kb.ingest.models import KbDocument


class IngestError(Exception):
    """Raised when input cannot be classified or an ingestor fails cleanly."""


class IngestorEntry(NamedTuple):
    """Registry row — one per source-type ingestor."""

    name: str
    matches: Callable[[str], bool]
    ingest: Callable[[str], KbDocument | list[KbDocument]]
    implemented: bool
    description: str


_REGISTRY: list[IngestorEntry] = []


def register(
    name: str,
    *,
    description: str,
    implemented: bool = True,
) -> Callable[
    [Callable[[str], KbDocument | list[KbDocument]]],
    Callable[[str], KbDocument | list[KbDocument]],
]:
    """Decorator factory: register an ingestor with a match-test sibling.

    The match function must be on the same module — ``register`` looks for
    ``matches_<name>`` in the decorated function's module. Cleaner than two
    decorators.
    """

    def decorator(
        fn: Callable[[str], KbDocument | list[KbDocument]],
    ) -> Callable[[str], KbDocument | list[KbDocument]]:
        import sys

        module = sys.modules[fn.__module__]
        matcher_name = f"matches_{name}"
        matcher = getattr(module, matcher_name, None)
        if matcher is None or not callable(matcher):
            raise RuntimeError(
                f"Ingestor {name!r} requires a sibling match function "
                f"`{matcher_name}` in module {fn.__module__}."
            )
        _REGISTRY.append(
            IngestorEntry(
                name=name,
                matches=matcher,
                ingest=fn,
                implemented=implemented,
                description=description,
            )
        )
        return fn

    return decorator


def registered_ingestors() -> list[IngestorEntry]:
    """Return the current registry — used by /kb-ingest for help text."""
    return list(_REGISTRY)


def ingest(source: str | Path) -> KbDocument | list[KbDocument]:
    """Detect the source type and route to the right ingestor.

    Parameters
    ----------
    source
        File path, URL, DOI string, or directory path.

    Returns
    -------
    KbDocument | list[KbDocument]
        Single doc for single-source ingestors; list for batch (BibTeX,
        folder).
    """
    source_str = str(source)
    for entry in _REGISTRY:
        if entry.matches(source_str):
            if not entry.implemented:
                raise NotImplementedError(
                    f"Ingestor {entry.name!r} matches {source_str!r} but is "
                    f"not yet implemented in this phase. Description: "
                    f"{entry.description}"
                )
            return entry.ingest(source_str)
    raise IngestError(
        f"No ingestor matches {source_str!r}. Registered: {[e.name for e in _REGISTRY]}"
    )


# ---------------------------------------------------------------------------
# Force-import side-effect-registered ingestors so they're visible after
# ``from vaultlab.kb.ingest import ingest``. Done at module-load time, not
# import-of-callsites — keeps the Python import graph well-defined.
# ---------------------------------------------------------------------------


def _bootstrap_registry() -> None:
    """Import each ingestor module so its @register decorators run.

    Done lazily at first ingest call so the dispatcher module itself has
    no hard dependencies on every leaf ingestor.
    """
    if _REGISTRY:
        return
    from vaultlab.kb.ingest import bibtex, folder, markdown, pdf, ris, stubs  # noqa: F401


# Trigger registration on first ingest call instead of at import. This keeps
# import order tractable and lets tests selectively load only the ingestors
# they care about.
_orig_ingest = ingest


def _ingest_with_bootstrap(source: str | Path) -> KbDocument | list[KbDocument]:
    _bootstrap_registry()
    return _orig_ingest(source)


def _registered_with_bootstrap() -> list[IngestorEntry]:
    _bootstrap_registry()
    return list(_REGISTRY)


# Replace the public function names so callers always get bootstrap-protected
# versions. The originals stay private for tests that want to bypass bootstrap.
ingest = _ingest_with_bootstrap  # type: ignore[assignment]
registered_ingestors = _registered_with_bootstrap  # type: ignore[assignment]  # noqa: F811


__all__ = ["IngestError", "IngestorEntry", "ingest", "register", "registered_ingestors"]


# Add URL-detection regex used by stubs.py + the markdown ingestor's strict
# guard against accidentally treating a URL as a path
URL_PATTERN = re.compile(r"^https?://", re.IGNORECASE)
DOI_PATTERN = re.compile(r"^(10\.\d{4,9}/[^\s]+)$|^doi:\s*10\.", re.IGNORECASE)
PMID_PATTERN = re.compile(r"^pmid:?\s*\d+$|^\d{6,9}$", re.IGNORECASE)
