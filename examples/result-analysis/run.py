"""End-to-end result-analysis workflow.

Pipeline
--------
1. Read the tidy CSV at ``inputs/results.csv`` (50 rows × 5 columns: a
   simple gene-expression-by-treatment-group setup).
2. Run :func:`vaultlab.analysis.run_pipeline`, which:
   - computes per-column statistics,
   - renders the three figures listed in ``vaultlab-analysis.json``,
   - composes a draft Methods paragraph citing every column with its n,
   - writes per-artifact provenance + method-md sidecars and an
     append-only ``.vaultlab-provenance.jsonl`` audit index.
3. Print a short summary of what landed in ``out/``.

Run
---

.. code-block:: bash

    python run.py

Outputs
-------
- ``out/fig1_expression_by_group.png``       — bar plot
- ``out/fig2_expression_histogram.png``      — histogram
- ``out/fig3_qc_vs_expression.png``          — scatter
- ``out/methods.md``                         — drafted methods paragraph
- ``out/stats_summary.json``                 — per-column stats
- ``out/*.provenance.json`` + ``*.method.md`` — sidecar receipts per artifact
- ``out/.vaultlab-provenance.jsonl``         — audit index

Adapt this
----------
Replace ``inputs/results.csv`` with your own tidy results table (CSV or
Parquet or TSV) and edit ``vaultlab-analysis.json`` to point at your
columns. The pipeline accepts ``bar``, ``scatter``, ``histogram``, and
``line`` figure kinds. For anything fancier, see
``vaultlab.figures.recipes``.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent
if (_REPO_ROOT / "src" / "vaultlab" / "__init__.py").exists():
    sys.path.insert(0, str(_REPO_ROOT / "src"))

logger = logging.getLogger("result-analysis-example")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=_HERE / "out")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    from vaultlab.analysis import run_pipeline

    out_dir: Path = args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    result = run_pipeline(
        project_dir=_HERE,
        out_dir=out_dir,
        project_name="result-analysis demo",
        # figures_config not passed → loads from vaultlab-analysis.json
    )

    logger.info("")
    logger.info("Done. %d figure(s) emitted:", len(result.figures))
    for fig in result.figures:
        logger.info("  - %s", fig.relative_to(_HERE))
    logger.info("Methods draft: %s", result.methods_md.relative_to(_HERE))
    logger.info(
        "Stats summary covers %d file(s): %s",
        len(result.stats_summary),
        ", ".join(result.stats_summary.keys()),
    )
    logger.info("Provenance sidecars: %d files", len(result.manifest_paths))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
