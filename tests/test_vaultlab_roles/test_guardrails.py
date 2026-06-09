"""Tests for vaultlab.roles._guardrails.enforce_hedge (B2)."""

from __future__ import annotations

from vaultlab.roles import enforce_hedge


def test_flags_overclaim() -> None:
    flags = enforce_hedge("This proves X.")
    assert flags
    assert any("proves" in f for f in flags)


def test_flags_multiple_occurrences() -> None:
    flags = enforce_hedge("It demonstrates that A and we conclude that B.")
    assert len(flags) == 2


def test_clean_hedged_text_passes() -> None:
    # Hedged verification prose (as emitted by the analysis interpretation pass).
    text = "`y` appears higher in `a` than `b`; this is consistent with the trend."
    assert enforce_hedge(text) == []


def test_empty_text() -> None:
    assert enforce_hedge("") == []


def test_case_insensitive() -> None:
    flags = enforce_hedge("This PROVES it.")
    assert flags, "expected an overclaim flag for 'PROVES'"
    assert any("proves" in f.lower() for f in flags)
