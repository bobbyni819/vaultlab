"""parameter_stamp() — embed the --K CLI convention into figure filenames.

Per Pattern 4 (metabolism-patterns-to-lift.md): every figure-generating script
accepts a --K parameter (or similar) and embeds the parameter value in the
output filename so re-runs with different K values don't overwrite each other.

PLACEHOLDER — full implementation lands as part of P0 helper consolidation.
"""

from __future__ import annotations


def parameter_stamp(*, base: str, **params: int | float | str) -> str:
    """Construct a filename suffix from key=value parameters.

    Examples
    --------
    >>> parameter_stamp(base="cluster_umap", K=8, resolution=0.6)
    'cluster_umap_K8_res0.6'
    >>> parameter_stamp(base="heatmap")
    'heatmap'
    """
    if not params:
        return base
    parts = []
    for key, value in params.items():
        # Compact key (single-letter param keys stay as-is; multi-letter
        # gets a 3-char abbreviation)
        compact_key = key if len(key) <= 3 else key[:3]
        parts.append(f"{compact_key}{value}")
    return base + "_" + "_".join(parts)
