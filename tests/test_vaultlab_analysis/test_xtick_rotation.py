"""Regression tests for bar-chart x-label rotation (overprint fix).

The earlier rule rotated x tick labels only when there were >6 bars, leaving
low-count panels with long composite labels (e.g. "S. aureus | (R)-DI-87 | WT")
overprinted and illegible. _xtick_rotation now triggers on label length too.
"""

from __future__ import annotations

from vaultlab.analysis.pipeline import _xtick_rotation


def test_few_short_labels_no_rotation():
    assert _xtick_rotation(["WT", "adsA", "Vehicle"]) is None


def test_few_long_labels_rotate_45():
    # The 4F/4H/4I case: only 4 bars, but each label is long -> must rotate.
    labels = [
        "S. aureus | (R)-DI-87 | WT",
        "S. aureus | (R)-DI-87 | adsA",
        "S. aureus | Vehicle | WT",
        "S. aureus | Vehicle | adsA",
    ]
    assert _xtick_rotation(labels) == 45


def test_many_short_labels_rotate_30():
    assert _xtick_rotation([f"g{i}" for i in range(9)]) == 30


def test_many_long_labels_rotate_45():
    assert _xtick_rotation([f"long-label-number-{i}" for i in range(12)]) == 45


def test_boundary_label_length():
    # > 12 chars triggers rotation even with a single bar.
    assert _xtick_rotation(["x" * 13]) == 30
    assert _xtick_rotation(["x" * 12]) is None
    # > 24 chars escalates to 45.
    assert _xtick_rotation(["x" * 25]) == 45


def test_empty():
    assert _xtick_rotation([]) is None
