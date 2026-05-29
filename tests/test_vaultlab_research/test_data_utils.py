"""Tests for vaultlab.research.data_utils.detect_data_format."""

from __future__ import annotations

from pathlib import Path

import pytest

from vaultlab.research.data_utils import detect_data_format


class TestExcelMultiRowHeader:
    """Stacked-header xlsx must report raw row-0 values, not Unnamed: N."""

    def test_no_unnamed_columns(self, tmp_path: Path) -> None:
        openpyxl = pytest.importorskip("openpyxl")  # noqa: F841
        import pandas as pd

        # 3 stacked header rows + 2 data rows, written with no logical header
        # so the file on disk literally has the stacked rows at the top.
        rows = [
            ["Vehicle", "Vehicle", "(R)-DI-87", "(R)-DI-87"],
            ["S. aureus", "S. aureus", "S. aureus", "S. aureus"],
            ["kidney-L", "kidney-R", "kidney-L", "kidney-R"],
            [1.0, 2.0, 3.0, 4.0],
            [5.0, 6.0, 7.0, 8.0],
        ]
        xlsx = tmp_path / "Fig4A.xlsx"
        pd.DataFrame(rows).to_excel(xlsx, header=False, index=False)

        result = detect_data_format(str(xlsx))

        assert result["format"] == "xlsx"
        assert result["columns"] is not None
        assert not any(str(c).startswith("Unnamed") for c in result["columns"])
        # Real row-0 values surface instead of mangled labels.
        assert "Vehicle" in result["columns"]
        assert result["cols"] == 4
        # header=None → every row is data, so all 5 rows count.
        assert result["rows"] == 5
        assert "header=None" in result["load_command"]
