"""vaultlab.analysis — consume tidy results, produce figures + methods + audit.

Boundary: this module consumes POST-ANALYSIS files (CSV / Parquet / TSV
of tidy results) and produces vaultlab-canonical artifacts (figures,
methods paragraph, audit manifest). It does NOT run analyses, fit
models, or process raw data — that lives in the user's project repo.

Public API
----------

>>> from vaultlab.analysis import run_pipeline, AnalysisResult
>>> result = run_pipeline(project_dir)
>>> result.figures        # list[Path]
>>> result.methods_md     # Path | None
>>> result.stats_summary  # {filename: {column: {dtype, n, ...}}}
>>> result.manifest_paths # list[Path] of provenance sidecars

See ``pipeline.md`` (SKILL bundle) for scope discipline and accepted
input types.
"""

from vaultlab.analysis.pipeline import (
    RAW_DATA_EXTENSIONS,
    TIDY_RESULT_EXTENSIONS,
    AnalysisResult,
    PreflightResult,
    run_pipeline,
    state_aware_preflight,
)
from vaultlab.analysis.stats import (
    compare_two_groups,
    summarize_column,
    summarize_dataframe,
)
from vaultlab.analysis.methods import compose_methods_paragraph

__all__ = [
    "RAW_DATA_EXTENSIONS",
    "TIDY_RESULT_EXTENSIONS",
    "AnalysisResult",
    "PreflightResult",
    "compare_two_groups",
    "compose_methods_paragraph",
    "run_pipeline",
    "state_aware_preflight",
    "summarize_column",
    "summarize_dataframe",
]
