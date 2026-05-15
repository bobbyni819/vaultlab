# Goal — SPEC-A: result-analysis pipeline (sub-goal 2.6)

**Status:** complete
**Plan reference:** `.claude/goals/vaultlab-north-star-plan.md` sub-goal 2.6
**Advances:** Criterion #5 (composability — net-new use case) + Criterion #2

## What shipped

`vaultlab.analysis` — new subpackage that **consumes post-analysis tidy
result files** (CSV / Parquet / TSV) and produces:

- a `stats_summary` dict (per-column dtype, n, missing, numeric/categorical
  summaries) — see `vaultlab.analysis.stats.summarize_dataframe`
- one figure per entry in the user's `figures_config` (bar / scatter /
  histogram / line, rendered with matplotlib using `vaultlab.figures.contract`
  rcParams) with provenance + method-md sidecars
- a draft `methods.md` paragraph (template-based, no LLM) that cites each
  file by name, column count, row count, and statistical scope
- a per-figure `.provenance.json` + `.method.md` sidecar plus a top-level
  `.vaultlab-provenance.jsonl` index (per AGENTS.md Red Line #2)

Public API:

```python
from vaultlab.analysis import run_pipeline, AnalysisResult

result = run_pipeline(project_dir, out_dir=..., figures_config=...)
# result.figures        — list[Path] of figure PNGs
# result.methods_md     — Path to drafted methods paragraph
# result.stats_summary  — {filename: {column: {...}}}
# result.manifest_paths — list[Path] of provenance JSON sidecars
```

## Scope discipline (must hold)

vaultlab is the **layer above** analysis. The pipeline rejects raw-data
formats with a `ValueError` pointing the user to their analysis code:

```
.fastq, .fq, .bam, .sam, .cram, .vcf, .bcf, .h5, .h5ad, .loom,
.nd2, .czi, .lif, .tif (image), .tiff (image), .nii, .nii.gz, .dcm,
.mzml, .mzxml, .raw, .d, .wiff, .fcs
```

Tidy-only acceptance: `{.csv, .parquet, .pq, .tsv, .tab}`.

The boundary is tested in `tests/test_vaultlab_analysis/test_pipeline.py`.

## Files created

- `src/vaultlab/analysis/__init__.py`
- `src/vaultlab/analysis/pipeline.py`
- `src/vaultlab/analysis/stats.py`
- `src/vaultlab/analysis/methods.py`
- `src/vaultlab/analysis/pipeline.md` (SKILL.md)
- `tests/test_vaultlab_analysis/__init__.py`
- `tests/test_vaultlab_analysis/test_pipeline.py`
- `examples/result-analysis/` (synthetic 50-row dataset + config + run.py + expected_outputs/)

## What was NOT done (deferred)

- **LLM-driven methods polish.** Methods paragraph is template-based in
  this iteration per the task brief. A later sub-goal can compose
  `vaultlab.manuscript.polish` over the draft.
- **Multi-panel composites.** Each `figures_config` entry produces a single
  panel. Multi-panel composites already live under
  `vaultlab.figures.recipes.multi_panel_composite` — not in scope here.
- **Stats hypothesis tests.** No t-tests / ANOVA / multiple-testing
  correction. vaultlab CONSUMES results; it doesn't compute them. If users
  want p-values cited, they precompute and include them as columns.

## Verify

```bash
cd ~/Downloads/vaultlab
pytest tests/test_vaultlab_analysis/ -q
pytest tests/test_vaultlab_invariants/ -q  # still 8/0
python examples/result-analysis/run.py
```
