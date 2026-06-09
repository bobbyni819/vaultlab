"""Convert elife-91157 Figure 4 source-data xlsx → tidy long CSV.

Deterministic. No LLM, no judgment calls about scientific meaning. Used by
Phase 1 of the vaultlab stress-test audit.

Output schema (column order is enforced):
    panel, group, replicate, measurement, value

Run:
    /opt/anaconda3/bin/python scripts/xlsx_to_tidy.py

Algorithm (handles multi-row headers + stacked sub-blocks):
    For every numeric cell at (row i, col j) with j > 0:
      - Walk upward in column j, collecting non-blank string values until we
        encounter another numeric value (which would indicate a previous
        block's data). The collected strings — in top-down order — form the
        column-header label.
      - Walk upward in column 0, take the most recent non-blank string
        value. That's the row-label context.
      - Concatenate row-label + column-header parts with " | " as the
        `group` label.
    Replicate is the 0-based position of the numeric cell among numeric
    cells in the SAME (column, block) pair.
"""

from __future__ import annotations

import math
import re
import sys
from pathlib import Path

import openpyxl  # noqa: F401  (declares dependency)
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
XLSX_DIR = REPO / "elife-91157-fig4-data1-v1"
OUT_DIR = Path("/Users/arnav/vaultlab-kb/elife-91157-stress/data")
COLUMNS = ["panel", "group", "replicate", "measurement", "value"]

PANEL_RE = re.compile(r"^Figure\s*4([A-I])\.xlsx$", re.IGNORECASE)
IGNORE_LABELS = {
    "(values used for figure)",
    "values used for figure",
}


def panel_from_filename(name: str) -> str:
    m = PANEL_RE.match(name)
    if not m:
        raise SystemExit(f"unexpected filename, cannot infer panel: {name!r}")
    return f"Fig4{m.group(1).upper()}"


def _is_blank(cell: object) -> bool:
    if cell is None:
        return True
    if isinstance(cell, float) and math.isnan(cell):
        return True
    if isinstance(cell, str) and cell.strip() == "":
        return True
    return False


def _is_numeric(cell: object) -> bool:
    if isinstance(cell, bool):
        return False
    if isinstance(cell, (int, float)):
        return not (isinstance(cell, float) and math.isnan(cell))
    return False


def _as_label(cell: object) -> str | None:
    if _is_blank(cell):
        return None
    text = str(cell).strip()
    if not text:
        return None
    if text.lower() in IGNORE_LABELS:
        return None
    return text


def tidy_workbook(xlsx_path: Path) -> pd.DataFrame:
    panel = panel_from_filename(xlsx_path.name)
    xl = pd.ExcelFile(xlsx_path, engine="openpyxl")
    multi_sheet = len(xl.sheet_names) > 1

    out_rows: list[dict] = []

    for sheet_name in xl.sheet_names:
        df = pd.read_excel(
            xlsx_path, sheet_name=sheet_name, engine="openpyxl", header=None
        )
        measurement = sheet_name if multi_sheet else "value"
        n_rows, n_cols = df.shape

        # Precompute row-label context for each row (most recent non-blank
        # string value in column 0 at row ≤ i; resets to None when col 0
        # contains a numeric value).
        row_labels: list[str | None] = []
        current_row_label: str | None = None
        for i in range(n_rows):
            cell0 = df.iat[i, 0] if n_cols > 0 else None
            if _is_numeric(cell0):
                current_row_label = None
            else:
                lab = _as_label(cell0)
                if lab is not None:
                    current_row_label = lab
            row_labels.append(current_row_label)

        # Iterate column-by-column so we can cache the active block's
        # header for the column and reuse it across all data rows in the
        # block.
        for j in range(1, n_cols):
            in_data = False
            current_header: list[str] = []
            rep = 0
            for i in range(n_rows):
                cell = df.iat[i, j]
                if _is_numeric(cell):
                    if not in_data:
                        # Entering a new data block — compute the header
                        # by walking up column j until we hit a numeric
                        # (end of previous block) or the top.
                        parts: list[str] = []
                        for k in range(i - 1, -1, -1):
                            cand = df.iat[k, j]
                            if _is_numeric(cand):
                                break
                            lab = _as_label(cand)
                            if lab is not None:
                                parts.append(lab)
                        parts.reverse()
                        current_header = parts
                        rep = 0
                        in_data = True

                    row_label = row_labels[i]
                    label_parts: list[str] = []
                    if row_label is not None:
                        label_parts.append(row_label)
                    label_parts.extend(current_header)
                    group_label = (
                        " | ".join(label_parts) if label_parts else f"col{j}"
                    )

                    out_rows.append(
                        {
                            "panel": panel,
                            "group": group_label,
                            "replicate": rep,
                            "measurement": measurement,
                            "value": float(cell),
                        }
                    )
                    rep += 1
                else:
                    if in_data:
                        in_data = False
                        current_header = []

    if not out_rows:
        return pd.DataFrame(columns=COLUMNS)

    out = pd.DataFrame(out_rows)[COLUMNS]
    return out


def count_source_nonempty_value_cells(xlsx_path: Path) -> int:
    """Count numeric cells (anywhere in any sheet) of the source workbook."""
    xl = pd.ExcelFile(xlsx_path, engine="openpyxl")
    total = 0
    for sheet_name in xl.sheet_names:
        df = pd.read_excel(
            xlsx_path, sheet_name=sheet_name, engine="openpyxl", header=None
        )
        for i in range(df.shape[0]):
            for j in range(df.shape[1]):
                if _is_numeric(df.iat[i, j]):
                    total += 1
    return total


def main() -> int:
    if not XLSX_DIR.is_dir():
        raise SystemExit(f"missing XLSX_DIR: {XLSX_DIR}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    xlsx_files = sorted(XLSX_DIR.glob("*.xlsx"))
    if not xlsx_files:
        raise SystemExit(f"no xlsx files in {XLSX_DIR}")

    print(
        f"{'file':<22} {'n_groups':>8} {'n_rows':>8} {'src_nums':>9} {'diff':>5}"
    )
    for xlsx in xlsx_files:
        panel = panel_from_filename(xlsx.name)
        tidy = tidy_workbook(xlsx)
        n_groups = tidy["group"].nunique()
        n_rows = len(tidy)
        src_nums = count_source_nonempty_value_cells(xlsx)
        diff = n_rows - src_nums
        out_path = OUT_DIR / f"{panel}.csv"
        tidy.to_csv(out_path, index=False)
        print(f"{xlsx.name:<22} {n_groups:>8} {n_rows:>8} {src_nums:>9} {diff:>5}")

    print(f"\nwrote {len(xlsx_files)} CSV(s) to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
