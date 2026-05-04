"""Tests for vaultlab.research.deck_cache."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from vaultlab.research.deck_cache import (
    DeckDecision,
    cache_decision,
    clear_cache,
    deck_decision,
    get_cached_decision,
)
from vaultlab.research.notes_from_summary import SummaryRecord


def _mk_decision(doi: str = "10.1234/x") -> DeckDecision:
    return DeckDecision(
        doi=doi,
        figure_path="/tmp/figures/x.png",
        speaker_notes={"hook": "h", "key_claim": "k", "script": "s"},
        citation="Doe et al. 2024 | Nature",
    )


def test_cache_roundtrip(tmp_path):
    d = _mk_decision()
    cache_decision(d, cache_dir=tmp_path)
    loaded = get_cached_decision("10.1234/x", cache_dir=tmp_path)
    assert loaded is not None
    assert loaded.doi == "10.1234/x"
    assert loaded.figure_path == "/tmp/figures/x.png"
    assert loaded.speaker_notes["hook"] == "h"
    assert loaded.citation == "Doe et al. 2024 | Nature"
    assert loaded.cached_at  # stamped on save


def test_cache_miss_returns_none(tmp_path):
    assert get_cached_decision("10.1234/missing", cache_dir=tmp_path) is None


def test_clear_cache_removes_files(tmp_path):
    cache_decision(_mk_decision("10.1/a"), cache_dir=tmp_path)
    cache_decision(_mk_decision("10.1/b"), cache_dir=tmp_path)
    cache_decision(_mk_decision("10.1/c"), cache_dir=tmp_path)
    n = clear_cache(cache_dir=tmp_path)
    assert n == 3
    assert get_cached_decision("10.1/a", cache_dir=tmp_path) is None


def test_corrupt_cache_returns_none(tmp_path):
    p = tmp_path / "10.1234_x.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("not json", encoding="utf-8")
    assert get_cached_decision("10.1234/x", cache_dir=tmp_path) is None


def test_deck_decision_uses_cache(tmp_path):
    """deck_decision returns cached without recomputing when use_cache=True."""
    d = _mk_decision("10.1234/x")
    cache_decision(d, cache_dir=tmp_path)

    # If cache works, the helpers should NOT be called
    with patch("vaultlab.research.notes_from_summary.load_summary") as mock_load:
        result = deck_decision("10.1234/x", cache_dir=tmp_path)
    mock_load.assert_not_called()
    assert result is not None
    assert result.doi == "10.1234/x"


def test_deck_decision_recomputes_when_use_cache_false(tmp_path):
    """use_cache=False bypasses the cache entirely."""
    d = _mk_decision("10.1234/x")
    cache_decision(d, cache_dir=tmp_path)

    fake_record = SummaryRecord(
        doi="10.1234/x", title="T", authors=["A B"], year=2024,
        tldr="tldr", journal="J",
    )
    with (
        patch(
            "vaultlab.research.deck_cache.load_summary", return_value=fake_record
        ),
        patch(
            "vaultlab.research.deck_cache.pick_best_figure_for_doi",
            return_value=Path("/tmp/new.png"),
        ),
    ):
        result = deck_decision("10.1234/x", cache_dir=tmp_path, use_cache=False)
    assert result is not None
    # New figure path beats cached one (Path normalises slashes per OS)
    assert Path(result.figure_path) == Path("/tmp/new.png")


def test_deck_decision_override_supersedes_cache_figure(tmp_path):
    """figure_path_override returns cached notes but with the supplied figure."""
    d = _mk_decision("10.1234/x")
    cache_decision(d, cache_dir=tmp_path)

    result = deck_decision(
        "10.1234/x",
        cache_dir=tmp_path,
        figure_path_override="/abs/override.png",
    )
    assert result is not None
    assert result.figure_path == "/abs/override.png"
    assert result.speaker_notes == d.speaker_notes  # cached notes preserved


def test_deck_decision_returns_none_when_no_summary(tmp_path):
    """No cache + no summary file = None."""
    with (
        patch("vaultlab.research.deck_cache.load_summary", return_value=None),
    ):
        result = deck_decision("10.1234/missing", cache_dir=tmp_path)
    assert result is None


def test_deck_decision_caches_on_first_compute(tmp_path):
    """First call computes + caches; second call hits cache."""
    fake_record = SummaryRecord(
        doi="10.5678/y", title="T", authors=["X Y"], year=2025,
        tldr="content", journal="Cell",
    )
    with (
        patch(
            "vaultlab.research.deck_cache.load_summary", return_value=fake_record
        ),
        patch(
            "vaultlab.research.deck_cache.pick_best_figure_for_doi",
            return_value=Path("/picked.png"),
        ),
    ):
        first = deck_decision("10.5678/y", cache_dir=tmp_path)

    # Now load_summary should NOT be called again
    with patch("vaultlab.research.deck_cache.load_summary") as mock_load:
        second = deck_decision("10.5678/y", cache_dir=tmp_path)
    mock_load.assert_not_called()
    assert first.doi == second.doi
    assert first.figure_path == second.figure_path
    assert Path(first.figure_path) == Path("/picked.png")
