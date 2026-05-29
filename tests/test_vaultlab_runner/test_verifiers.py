"""Tests for vaultlab.runner.verifiers.verify_numeric (B3)."""

from __future__ import annotations

from vaultlab.runner import verify_numeric


def test_flags_impossible_p_value() -> None:
    flags = verify_numeric("recomputed Welch's t-test, p=1.5")
    assert any("implausible p-value" in f for f in flags)


def test_accepts_valid_p_value() -> None:
    assert verify_numeric("recomputed Welch's t-test n=6/6, p=5.88e-09") == []


def test_flags_zero_sample_size() -> None:
    flags = verify_numeric("group comparison n=0/6")
    assert any("non-positive sample size" in f for f in flags)


def test_flags_mean_outside_range() -> None:
    flags = verify_numeric("`value` — numeric, n=54, mean 100, range [1, 10]")
    assert any("outside its reported range" in f for f in flags)


def test_accepts_mean_within_range() -> None:
    # The descriptive line shape emitted by _describe_column.
    text = "`value` — numeric, n=54, mean 12.5±15.7, range [1.36, 65]."
    assert verify_numeric(text) == []


def test_flags_inverted_range() -> None:
    flags = verify_numeric("mean 5, range [10, 1]")
    assert any("inverted range" in f for f in flags)


def test_empty_text() -> None:
    assert verify_numeric("") == []
