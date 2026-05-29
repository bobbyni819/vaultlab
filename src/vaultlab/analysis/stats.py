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

__all__ = ["compare_two_groups", "summarize_column", "summarize_dataframe"]


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


def compare_two_groups(
    df: "pd.DataFrame",
    group_col: str,
    value_col: str,
    group_a: Any,
    group_b: Any,
) -> dict[str, Any]:
    """Welch's two-sample t-test between two groups of a tidy result table.

    Verification-only. This is for the pipeline interpretation pass on
    already-tidy two-group result tables (e.g. treated vs. control) — a
    faithfulness check that the direction/significance a methods paragraph
    states is actually supported by the numbers. It is NOT a substitute
    for upstream analysis (FASTQ → counts → DE); that carve-out from the
    "consumes not computes" doctrine is deliberate and narrow.

    Subsets ``df`` to rows where ``group_col`` is ``group_a`` or
    ``group_b``, drops NaNs in ``value_col``, and runs
    ``scipy.stats.ttest_ind(equal_var=False)``.

    Returns ``{mean_a, mean_b, n_a, n_b, t_stat, p_value, direction}`` —
    all plain Python scalars so the dict is ``json.dumps``-able.
    ``direction`` is ``"a>b"`` / ``"a<b"`` / ``"a==b"`` (mean comparison),
    or ``"indeterminate"`` when either group has zero matching rows (so a
    missing group is not silently read as equal means).
    ``t_stat`` / ``p_value`` are ``None`` when either group has < 2 values.
    """
    from scipy import stats as scipy_stats  # lazy: scipy is an optional extra

    a_vals = df.loc[df[group_col] == group_a, value_col].dropna()
    b_vals = df.loc[df[group_col] == group_b, value_col].dropna()

    n_a = int(a_vals.shape[0])
    n_b = int(b_vals.shape[0])
    mean_a = _safe_float(a_vals.mean()) if n_a else None
    mean_b = _safe_float(b_vals.mean()) if n_b else None

    if n_a >= 2 and n_b >= 2:
        res = scipy_stats.ttest_ind(a_vals, b_vals, equal_var=False)
        t_stat = _safe_float(res.statistic)
        p_value = _safe_float(res.pvalue)
    else:
        t_stat = None
        p_value = None

    if mean_a is None or mean_b is None:
        direction = "indeterminate"
    elif mean_a > mean_b:
        direction = "a>b"
    elif mean_a < mean_b:
        direction = "a<b"
    else:
        direction = "a==b"

    return {
        "mean_a": mean_a,
        "mean_b": mean_b,
        "n_a": n_a,
        "n_b": n_b,
        "t_stat": t_stat,
        "p_value": p_value,
        "direction": direction,
    }


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
