"""Recipe corpus — a derived index of every recipe's anchor papers.

The ``ANCHOR_PAPERS`` tuples on each recipe module (in
``vaultlab.figures.recipes``) are the SOURCE OF TRUTH. This module derives a
JSON index (``sources.json``) from them so the anchor set is queryable as data
and guarded against drift: a staleness test asserts the checked-in
``sources.json`` equals :func:`build_sources_index`.

Regenerate after changing any recipe's ``ANCHOR_PAPERS``::

    python -c "from vaultlab.figures.corpus import save_sources_index; save_sources_index()"

NEXT_STEPS B7.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

__all__ = [
    "SOURCES_PATH",
    "build_sources_index",
    "load_sources_index",
    "save_sources_index",
]

SOURCES_PATH = Path(__file__).with_name("sources.json")


def build_sources_index() -> dict[str, dict[str, Any]]:
    """Derive the sources index from the live recipe ``ANCHOR_PAPERS`` tuples.

    Returns ``{recipe_name: {"version": RECIPE_VERSION, "papers": [...]}}``,
    one entry per recipe registered in ``vaultlab.figures.recipes.__all__``.
    """
    from vaultlab.figures import recipes

    index: dict[str, dict[str, Any]] = {}
    for name in sorted(recipes.__all__):
        mod = getattr(recipes, name)
        index[name] = {
            "version": getattr(mod, "RECIPE_VERSION", ""),
            "papers": list(getattr(mod, "ANCHOR_PAPERS", ())),
        }
    return index


def save_sources_index(path: Path | str | None = None) -> Path:
    """Write the derived index to ``sources.json`` (defaults to the package file).

    Returns the path written. Trailing newline + sorted keys keep the diff
    stable across regenerations.
    """
    target = Path(path) if path is not None else SOURCES_PATH
    target.write_text(
        json.dumps(build_sources_index(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target


def load_sources_index(path: Path | str | None = None) -> dict[str, dict[str, Any]]:
    """Load the checked-in ``sources.json`` index."""
    source = Path(path) if path is not None else SOURCES_PATH
    return json.loads(source.read_text(encoding="utf-8"))
