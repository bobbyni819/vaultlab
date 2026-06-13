"""Staleness guard for the derived recipe sources index (NEXT_STEPS B7).

The ``ANCHOR_PAPERS`` tuples are the source of truth; ``sources.json`` is a
derived artifact. These tests fail loudly if the checked-in JSON drifts from the
live tuples, so a recipe anchor change without regenerating the index cannot
slip through CI.
"""

from __future__ import annotations

import vaultlab.figures.recipes as recipes
from vaultlab.figures.corpus import (
    build_sources_index,
    load_sources_index,
    save_sources_index,
)


def test_sources_index_not_stale() -> None:
    """The checked-in sources.json must match the live ANCHOR_PAPERS tuples.

    If this fails, regenerate it:
        python -c "from vaultlab.figures.corpus import save_sources_index; save_sources_index()"
    """
    assert load_sources_index() == build_sources_index()


def test_sources_index_covers_every_recipe_with_three_papers() -> None:
    index = build_sources_index()
    assert set(index) == set(recipes.__all__)
    for name, entry in index.items():
        assert entry["version"], f"{name} missing RECIPE_VERSION"
        assert len(entry["papers"]) >= 3, f"{name} has < 3 anchor papers"


def test_save_round_trips(tmp_path) -> None:
    """save_sources_index then load returns the same structure."""
    out = save_sources_index(tmp_path / "sources.json")
    assert out.exists()
    assert load_sources_index(out) == build_sources_index()
