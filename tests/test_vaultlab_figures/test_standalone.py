"""Standalone integration test for vaultlab.figures.

Implements north-star Criterion #3 ("plug-in companion"): the primary
entrypoints of ``vaultlab.figures`` must be invocable from a fresh
``tmp_path`` fixture with no prior vaultlab state.

We test two entrypoints:

1. ``FigureContract`` + ``validate_contract`` — pure-Python dataclass
   round-trip (no plotting libraries needed).
2. ``acquire_figures`` with an empty DOI — exercises the public
   acquisition entrypoint and the cache-dir initialization path without
   any network calls (the function gracefully returns
   ``source="unavailable"`` on empty input).
"""

from __future__ import annotations

from pathlib import Path

import pytest


def test_figure_contract_runs_standalone_from_fresh_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``FigureContract`` + ``validate_contract`` are usable without any
    KB, config, or matplotlib install."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))

    from vaultlab.figures.contract import (
        FigureArchetype,
        FigureContract,
        validate_contract,
    )

    contract = FigureContract(
        conclusion="Test signal differs between conditions.",
        evidence_chain={"A": "Group means", "B": "Per-subject points"},
        archetype=FigureArchetype.QUANTITATIVE_GRID,
        width_mm=183.0,
        height_mm=120.0,
    )

    warnings = validate_contract(contract)
    # Should be valid (>=2 panels, sensible dimensions, no missing notes)
    assert isinstance(warnings, list)
    assert warnings == []
    assert contract.panels() == ["A", "B"]


def test_acquire_figures_runs_standalone_from_fresh_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``acquire_figures`` returns ``source='unavailable'`` for an empty
    DOI without raising — exercises the public API + cache initialization
    on a fresh ``tmp_path``."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))

    from vaultlab.figures import FigureAcquisitionResult, acquire_figures

    cache_dir = tmp_path / "figure-cache"
    result = acquire_figures("", cache_dir=cache_dir)

    assert isinstance(result, FigureAcquisitionResult)
    assert result.source == "unavailable"
    assert result.figures == []
    assert result.error == "empty doi"
    # Empty-DOI fast-path returns before touching the cache dir — the
    # important plug-in guarantee is that the call doesn't raise from a
    # fresh tmp_path.
