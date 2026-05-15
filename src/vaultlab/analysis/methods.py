"""Methods-paragraph composition for the result-analysis pipeline.

Template-based (no LLM call in this iteration per the SPEC-A brief). The
output is a short Markdown document that:

1. Cites each input file by name with column count + row count.
2. Lists which figures were generated and which columns they reference.
3. Surfaces statistical scope (numeric columns described as mean ± std;
   categorical columns described by unique count + top values).
4. Adds a hedged closing line per the AGENTS.md "hedged voice" quality bar.

Every claim cites a column + sample size, satisfying SPEC-A success
criterion #3 ("Methods text is grounded: every statistical claim cites a
column + sample size").
"""

from __future__ import annotations

from typing import Any

__all__ = ["compose_methods_paragraph"]


def compose_methods_paragraph(
    stats_summary: dict[str, dict[str, dict[str, Any]]],
    *,
    figure_entries: list[dict[str, Any]] | None = None,
    project_meta: dict[str, Any] | None = None,
) -> str:
    """Compose a draft methods paragraph.

    Parameters
    ----------
    stats_summary
        Two-level dict produced by the pipeline:
        ``{filename: {column: {dtype, n, n_missing, ...}}}``.
    figure_entries
        Optional list of figure plan entries (``{name, kind, x, y, source,
        path}``) so the methods paragraph can name each figure and the
        columns it cites.
    project_meta
        Optional ``{project_name, code_version, ...}`` for the header.

    Returns
    -------
    str
        A Markdown document suitable for paper Methods sections (~200-500
        words depending on column count).
    """
    project_meta = project_meta or {}
    figure_entries = figure_entries or []

    project_name = project_meta.get("project_name", "this project")
    code_version = project_meta.get("code_version", "")
    tool_label = f"vaultlab.analysis.run_pipeline ({code_version})" if code_version else (
        "vaultlab.analysis.run_pipeline"
    )

    lines: list[str] = []
    lines.append("# Methods (draft)")
    lines.append("")
    lines.append(
        f"Result tables for {project_name} were summarized and visualized with "
        f"`{tool_label}`. The pipeline consumes pre-computed tidy result tables "
        f"(CSV / Parquet / TSV) and emits figure exports plus this draft methods "
        f"paragraph; it does **not** re-run upstream analyses."
    )
    lines.append("")

    # 1. Per-file descriptions
    lines.append("## Result tables")
    lines.append("")
    for filename, cols in stats_summary.items():
        n_rows = _row_count_from_columns(cols)
        n_cols = len(cols)
        lines.append(
            f"- `{filename}` — {n_rows} rows × {n_cols} columns "
            f"({_numeric_count(cols)} numeric, "
            f"{n_cols - _numeric_count(cols)} categorical / non-numeric)."
        )
    lines.append("")

    # 2. Per-column statistical scope
    lines.append("## Column-level statistics")
    lines.append("")
    for filename, cols in stats_summary.items():
        lines.append(f"From `{filename}`:")
        lines.append("")
        for col_name, summary in cols.items():
            lines.append(f"- {_describe_column(col_name, summary)}")
        lines.append("")

    # 3. Figures
    if figure_entries:
        lines.append("## Figures")
        lines.append("")
        for entry in figure_entries:
            lines.append(f"- {_describe_figure(entry, stats_summary)}")
        lines.append("")

    # 4. Hedged closing — per AGENTS.md "Hedged voice" quality bar.
    lines.append("## Interpretation note")
    lines.append("")
    lines.append(
        "The summaries above describe the structure of the supplied result "
        "tables and may indicate where downstream interpretation is warranted; "
        "they are consistent with the columns reported by the upstream analysis "
        "and do not constitute new statistical inference."
    )
    lines.append("")

    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _row_count_from_columns(cols: dict[str, dict[str, Any]]) -> int:
    """All columns share the same length; pull n+n_missing from the first."""
    for summary in cols.values():
        return int(summary.get("n", 0)) + int(summary.get("n_missing", 0))
    return 0


def _numeric_count(cols: dict[str, dict[str, Any]]) -> int:
    return sum(1 for s in cols.values() if "mean" in s)


def _describe_column(name: str, summary: dict[str, Any]) -> str:
    n = summary.get("n", 0)
    n_missing = summary.get("n_missing", 0)
    miss_clause = f" ({n_missing} missing)" if n_missing else ""

    if "mean" in summary:
        mean = summary.get("mean")
        std = summary.get("std")
        if mean is None:
            return f"`{name}` — numeric (`{summary['dtype']}`), n={n}{miss_clause}, no finite values."
        std_str = f"±{std:.3g}" if std is not None else ""
        return (
            f"`{name}` — numeric (`{summary['dtype']}`), n={n}{miss_clause}, "
            f"mean {mean:.3g}{std_str}, "
            f"range [{summary.get('min'):.3g}, {summary.get('max'):.3g}]."
        )

    unique = summary.get("unique_count", 0)
    top = summary.get("top_values") or []
    top_str = (
        ", ".join(f"`{t['value']}` ({t['count']})" for t in top[:3])
        if top
        else "no observed values"
    )
    return (
        f"`{name}` — categorical (`{summary['dtype']}`), n={n}{miss_clause}, "
        f"{unique} unique values; top: {top_str}."
    )


def _describe_figure(
    entry: dict[str, Any],
    stats_summary: dict[str, dict[str, dict[str, Any]]],
) -> str:
    name = entry.get("name", "<unnamed>")
    kind = entry.get("kind", "<unknown kind>")
    x = entry.get("x")
    y = entry.get("y")
    source = entry.get("source")
    path = entry.get("path")
    path_clause = f" → `{path}`" if path else ""

    # Look up n for the cited columns when available.
    n_clause = ""
    if source and source in stats_summary:
        target_col = y or x
        if target_col and target_col in stats_summary[source]:
            n_clause = f", n={stats_summary[source][target_col].get('n', '?')}"

    if kind == "histogram":
        return (
            f"`{name}` — histogram of `{x}` from `{source}`{n_clause}{path_clause}."
        )
    if kind == "scatter":
        return (
            f"`{name}` — scatter of `{y}` vs `{x}` from `{source}`{n_clause}{path_clause}."
        )
    if kind == "bar":
        return (
            f"`{name}` — bar plot of `{y}` by `{x}` from `{source}`{n_clause}{path_clause}."
        )
    if kind == "line":
        return (
            f"`{name}` — line plot of `{y}` over `{x}` from `{source}`{n_clause}{path_clause}."
        )
    return f"`{name}` — {kind} figure from `{source}`{n_clause}{path_clause}."
