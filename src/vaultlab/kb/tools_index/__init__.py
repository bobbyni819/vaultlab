"""vaultlab.kb.tools_index — curated catalog of analysis packages.

Master plan §5. Each entry is one ``packages/<name>.md`` file with frontmatter
+ function inventory + use-case examples. The LLM reads from this catalog
*before* doing web searches, so it picks real functions from real packages —
not invented function names.

Plus ``external_repos.toml`` — a registry for lab-collaborator repositories
(spatial-omics algorithms, internal pipelines, etc.) that VaultLab should
suggest for specific question types.

Public API:

- :func:`load_index` — return the catalog as a dict[name → ToolEntry]
- :func:`load_external_repos` — return the external-repo registry
- :func:`suggest_for_topic` — given a topic keyword, return matching tools

Phase-1 catalog seeded with 12 packages (Q15 in the 2026-04-29 grill):
scanpy, squidpy, anndata, scikit-image, cellpose, scipy.stats, statsmodels,
pingouin, pyimzML, scvi-tools, harmony, palantir.

External repos seeded with one placeholder (``nick-spatial-algos``) per Q17 —
url empty, status ``pending-access``.
"""

from __future__ import annotations

from vaultlab.kb.tools_index.loader import (
    ToolEntry,
    ToolsIndexError,
    external_repos_path,
    load_external_repos,
    load_index,
    packages_dir,
    suggest_for_topic,
)

__all__ = [
    "ToolEntry",
    "ToolsIndexError",
    "external_repos_path",
    "load_external_repos",
    "load_index",
    "packages_dir",
    "suggest_for_topic",
]
