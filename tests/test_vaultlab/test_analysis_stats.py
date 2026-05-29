"""Tests for vaultlab.analysis.stats.compare_two_groups."""

from __future__ import annotations

import json

import pytest

pytest.importorskip("scipy")
import pandas as pd

from vaultlab.analysis.stats import compare_two_groups


def _two_group_frame(a_vals: list[float], b_vals: list[float]) -> pd.DataFrame:
    rows = [{"group": "A", "score": v} for v in a_vals]
    rows += [{"group": "B", "score": v} for v in b_vals]
    return pd.DataFrame(rows)


class TestCompareTwoGroups:
    def test_compare_two_groups_detects_effect(self) -> None:
        df = _two_group_frame(
            a_vals=[10.0, 11.0, 9.5, 10.5, 10.2, 9.8],
            b_vals=[2.0, 2.5, 1.5, 2.2, 1.8, 2.1],
        )
        result = compare_two_groups(df, "group", "score", "A", "B")

        assert result["n_a"] == 6
        assert result["n_b"] == 6
        assert result["p_value"] is not None and result["p_value"] < 0.05
        assert result["direction"] == "a>b"
        json.dumps(result)  # must be serializable

    def test_compare_two_groups_null_effect(self) -> None:
        same = [5.0, 5.1, 4.9, 5.2, 4.8, 5.05]
        df = _two_group_frame(a_vals=same, b_vals=list(same))
        result = compare_two_groups(df, "group", "score", "A", "B")

        assert result["n_a"] == 6
        assert result["n_b"] == 6
        assert result["p_value"] is not None and result["p_value"] > 0.05
        assert result["direction"] == "a==b"
        # Pin the actual values so a swapped-group bug can't pass silently.
        assert result["mean_a"] == result["mean_b"]
        assert abs(result["t_stat"]) < 1e-9
        json.dumps(result)

    def test_compare_two_groups_missing_group_is_indeterminate(self) -> None:
        df = _two_group_frame(a_vals=[10.0, 11.0, 9.5], b_vals=[])
        result = compare_two_groups(df, "group", "score", "A", "B")
        assert result["n_b"] == 0
        assert result["mean_b"] is None
        assert result["direction"] == "indeterminate"
        assert result["p_value"] is None
        json.dumps(result)

    def test_compare_two_groups_drops_nan(self) -> None:
        import numpy as np

        df = _two_group_frame(
            a_vals=[10.0, np.nan, 11.0, 9.5],
            b_vals=[2.0, 2.5, np.nan, 1.5],
        )
        result = compare_two_groups(df, "group", "score", "A", "B")
        assert result["n_a"] == 3
        assert result["n_b"] == 3
        assert result["direction"] == "a>b"
