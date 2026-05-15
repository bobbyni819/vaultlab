"""Stats descriptions for tidy result files.

``summarize_dataframe(df)`` returns a per-column dict with dtype, n,
n_missing, and numeric/categorical summaries. **No hypothesis tests** —
vaultlab CONSUMES analysis results, it does not compute them
(see ``pipeline.md`` SKILL bundle for the scope discipline).

The output is plain Python types (no numpy scalars, no pandas Timestamp
objects) so it's safe to round-trip through ``json.dumps`` and embed
in provenance receipts.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pandas as pd

__all__ = ["summarize_column", "summarize_dataframe"]


def summarize_dataframe(df: "pd.DataFrame") -> dict[str, dict[str, Any]]:
    """Summarize every column of ``df``.

    Returns ``{column_name: {dtype, n, n_missing, ...}}``. Numeric columns
    also carry ``mean / std / min / max``. Non-numeric columns carry
    ``unique_count`` and a small sample of ``top_values``.

    The dict is fully JSON-serializable.
    """
    out: dict[str, dict[str, Any]] = {}
    for col in df.columns:
        out[str(col)] = summarize_column(df[col])
    return out


def summarize_column(series: "pd.Series") -> dict[str, Any]:
    """Summarize a single column.

    Numeric columns → ``mean``, ``std``, ``min``, ``max`` (None when n=0).
    Non-numeric columns → ``unique_count``, ``top_values`` (up to 5 most
    common as ``[{value, count}, ...]``).

    All values are JSON-serializable (no numpy scalars, no NaN floats).
    """
    import pandas as pd  # lazy: pandas is a core dep, but keep imports local
    from pandas.api import types as pdtypes

    n_total = int(series.shape[0])
    n_missing = int(series.isna().sum())
    n = n_total - n_missing
    dtype = str(series.dtype)

    summary: dict[str, Any] = {
        "dtype": dtype,
        "n": n,
        "n_missing": n_missing,
    }

    if pdtypes.is_numeric_dtype(series) and not pdtypes.is_bool_dtype(series):
        non_null = series.dropna()
        if n == 0:
            summary.update({"mean": None, "std": None, "min": None, "max": None})
        else:
            summary["mean"] = _safe_float(non_null.mean())
            summary["std"] = _safe_float(non_null.std(ddof=1)) if n > 1 else None
            summary["min"] = _safe_float(non_null.min())
            summary["max"] = _safe_float(non_null.max())
    else:
        # Categorical / string / boolean / datetime: report unique + top values.
        non_null = series.dropna()
        summary["unique_count"] = int(non_null.nunique())
        if not non_null.empty:
            top = non_null.value_counts().head(5)
            summary["top_values"] = [
                {"value": _safe_scalar(v), "count": int(c)} for v, c in top.items()
            ]
        else:
            summary["top_values"] = []

    return summary


# ---------------------------------------------------------------------------
# Internal — JSON-safe coercion
# ---------------------------------------------------------------------------


def _safe_float(x: Any) -> float | None:
    """Coerce numpy scalar / pandas value → plain float, mapping NaN to None."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(v) or math.isinf(v):
        return None
    return v


def _safe_scalar(x: Any) -> Any:
    """Coerce pandas / numpy scalars to plain Python types for JSON."""
    # numpy / pandas scalars expose ``.item()``
    if hasattr(x, "item") and not isinstance(x, (str, bytes)):
        try:
            return x.item()
        except (ValueError, AttributeError):
            pass
    if isinstance(x, (int, float, str, bool)) or x is None:
        return x
    return str(x)
