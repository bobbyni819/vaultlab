"""Data format auto-detection — identify file formats and recommend load commands.

Helps Phase 1 of the research pipeline know HOW to load each data file.
Supports CSV, Parquet, H5AD, XLSX, JSON, HDF5 with graceful fallbacks.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

# Extension to format mapping
_EXT_MAP = {
    ".csv": "csv",
    ".tsv": "csv",  # TSV handled by same logic with sep='\t'
    ".parquet": "parquet",
    ".pq": "parquet",
    ".h5ad": "h5ad",
    ".xlsx": "xlsx",
    ".xls": "xlsx",
    ".json": "json",
    ".jsonl": "json",
    ".h5": "hdf5",
    ".hdf5": "hdf5",
    ".hdf": "hdf5",
}


def detect_data_format(filepath: str) -> dict:
    """Detect data file format and return metadata.

    Inspects the file extension and attempts to peek at the file contents
    to determine row/column counts and column names. Handles missing
    libraries gracefully.

    Args:
        filepath: Path to the data file.

    Returns:
        Dictionary with keys:
            format: "csv" | "parquet" | "h5ad" | "xlsx" | "json" | "hdf5" | "unknown"
            rows: int or None
            cols: int or None
            size_mb: float (0.0 if file doesn't exist)
            columns: list[str] or None (first 20 column names)
            library: "pandas" | "scanpy" | "h5py" | None (recommended library)
            load_command: str (e.g. "pd.read_csv('file.csv')")
    """
    filepath = os.path.abspath(filepath)

    result = {
        "format": "unknown",
        "rows": None,
        "cols": None,
        "size_mb": 0.0,
        "columns": None,
        "library": None,
        "load_command": "",
    }

    if not os.path.isfile(filepath):
        logger.warning("File not found: %s", filepath)
        result["load_command"] = f"# File not found: {filepath}"
        return result

    # File size
    result["size_mb"] = round(os.path.getsize(filepath) / (1024 * 1024), 2)

    # Detect format from extension
    ext = os.path.splitext(filepath)[1].lower()
    fmt = _EXT_MAP.get(ext, "unknown")
    result["format"] = fmt

    # Use the escaped filepath for load commands
    fp_escaped = filepath.replace("\\", "/")

    if fmt == "csv":
        result["library"] = "pandas"
        if ext == ".tsv":
            result["load_command"] = f"pd.read_csv('{fp_escaped}', sep='\\t')"
        else:
            result["load_command"] = f"pd.read_csv('{fp_escaped}')"
        _try_csv(filepath, result, sep="\t" if ext == ".tsv" else ",")

    elif fmt == "parquet":
        result["library"] = "pandas"
        result["load_command"] = f"pd.read_parquet('{fp_escaped}')"
        _try_parquet(filepath, result)

    elif fmt == "h5ad":
        result["library"] = "scanpy"
        result["load_command"] = f"sc.read_h5ad('{fp_escaped}')"
        _try_h5ad(filepath, result)

    elif fmt == "xlsx":
        result["library"] = "pandas"
        # header=None: these sheets often have stacked multi-row headers, so
        # we peek raw. Stacked-header sheets need walk-up conversion (see
        # scripts/xlsx_to_tidy.py) into a tidy CSV before analysis.
        result["load_command"] = f"pd.read_excel('{fp_escaped}', header=None)"
        _try_excel(filepath, result)

    elif fmt == "json":
        result["library"] = "pandas"
        if ext == ".jsonl":
            result["load_command"] = f"pd.read_json('{fp_escaped}', lines=True)"
        else:
            result["load_command"] = f"pd.read_json('{fp_escaped}')"
        _try_json(filepath, result)

    elif fmt == "hdf5":
        result["library"] = "h5py"
        result["load_command"] = f"h5py.File('{fp_escaped}', 'r')"
        _try_hdf5(filepath, result)

    else:
        result["load_command"] = f"# Unknown format: {ext or 'no extension'}"

    return result


def _try_csv(filepath: str, result: dict, sep: str = ",") -> None:
    """Try to peek at a CSV file for row/col counts."""
    try:
        import pandas as pd

        df = pd.read_csv(filepath, sep=sep, nrows=0)
        result["cols"] = len(df.columns)
        result["columns"] = list(df.columns[:20])

        # Count rows without loading everything
        with open(filepath, encoding="utf-8", errors="ignore") as f:
            row_count = sum(1 for _ in f) - 1  # subtract header
        result["rows"] = max(row_count, 0)
    except ImportError:
        logger.debug("pandas not installed; cannot peek at CSV")
    except Exception as e:
        logger.debug("Failed to peek at CSV %s: %s", filepath, e)


def _try_parquet(filepath: str, result: dict) -> None:
    """Try to peek at a Parquet file."""
    try:
        import pandas as pd

        df = pd.read_parquet(filepath)
        result["rows"] = len(df)
        result["cols"] = len(df.columns)
        result["columns"] = list(df.columns[:20])
    except ImportError:
        logger.debug("pandas/pyarrow not installed; cannot peek at Parquet")
    except Exception as e:
        logger.debug("Failed to peek at Parquet %s: %s", filepath, e)


def _try_h5ad(filepath: str, result: dict) -> None:
    """Try to peek at an h5ad file (AnnData)."""
    try:
        import scanpy as sc

        adata = sc.read_h5ad(filepath, backed="r")
        result["rows"] = adata.n_obs
        result["cols"] = adata.n_vars
        result["columns"] = list(adata.var_names[:20])
        adata.file.close()
    except ImportError:
        logger.debug("scanpy not installed; cannot peek at h5ad")
    except Exception as e:
        logger.debug("Failed to peek at h5ad %s: %s", filepath, e)


def _try_excel(filepath: str, result: dict) -> None:
    """Try to peek at an Excel file.

    Read with ``header=None`` so multi-row-header sheets (common in
    published supplementary data: stacked condition/cell-type headers,
    blank-row separators) report their raw row-0 values instead of pandas'
    mangled ``Unnamed: N`` labels. Such sheets need walk-up conversion
    (see ``scripts/xlsx_to_tidy.py``) into a tidy CSV before analysis.
    """
    try:
        import pandas as pd

        df = pd.read_excel(filepath, header=None, nrows=5)
        result["cols"] = df.shape[1]
        result["columns"] = (
            [str(v) for v in df.iloc[0].tolist()[:20]] if not df.empty else []
        )

        # Get row count from full read (Excel doesn't support lazy count).
        # No header subtraction — with header=None every row is data.
        df_full = pd.read_excel(filepath, header=None)
        result["rows"] = len(df_full)
    except ImportError:
        logger.debug("pandas/openpyxl not installed; cannot peek at Excel")
    except Exception as e:
        logger.debug("Failed to peek at Excel %s: %s", filepath, e)


def _try_json(filepath: str, result: dict) -> None:
    """Try to peek at a JSON file."""
    try:
        import json

        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            result["rows"] = len(data)
            if data and isinstance(data[0], dict):
                result["cols"] = len(data[0])
                result["columns"] = list(data[0].keys())[:20]
        elif isinstance(data, dict):
            result["rows"] = 1
            result["cols"] = len(data)
            result["columns"] = list(data.keys())[:20]
    except Exception as e:
        logger.debug("Failed to peek at JSON %s: %s", filepath, e)


def _try_hdf5(filepath: str, result: dict) -> None:
    """Try to peek at an HDF5 file."""
    try:
        import h5py

        with h5py.File(filepath, "r") as f:
            keys = list(f.keys())
            result["columns"] = keys[:20]
            result["cols"] = len(keys)
            # Try to get row count from first dataset
            for key in keys:
                if hasattr(f[key], "shape"):
                    result["rows"] = f[key].shape[0]
                    break
    except ImportError:
        logger.debug("h5py not installed; cannot peek at HDF5")
    except Exception as e:
        logger.debug("Failed to peek at HDF5 %s: %s", filepath, e)
