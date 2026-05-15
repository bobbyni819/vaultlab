---
name: run-analysis
description: Run the vaultlab result-analysis pipeline on a project directory. Consumes tidy CSV / Parquet / TSV result tables, produces stats summaries, figures (matplotlib via the vaultlab.figures contract), a draft methods.md paragraph, and provenance receipts. Scope-disciplined — rejects raw-data formats (FASTQ / BAM / HDF5 / microscopy / mass-spec).
arguments: <project-dir> [--out <out-dir>] [--name <project-name>]
---

# /run-analysis <project-dir>

> *"Drop your tidy result tables in a folder, run this, get figures +
> methods paragraph + audit receipts back — no glue code."*

Drives `vaultlab.analysis.run_pipeline`. The pipeline is the
**layer above** raw-data analysis: inputs MUST be tidy result tables
(CSV / TSV / Parquet). Raw formats (FASTQ, BAM, HDF5, ND2, mzML, FCS,
...) are rejected with a `ValueError` pointing the user back at their
analysis code.

## What it produces

- `out/stats_summary.json` — `{filename: {column: {dtype, n, mean, std, ...}}}`
- `out/<figure_name>.png` for each entry in `figures_config`
- `out/methods.md` — draft methods paragraph (template-based, no LLM)
- `<artifact>.provenance.json` + `<artifact>.method.md` for every
  output (Red Line #2)

## Figures config

The pipeline reads a `vaultlab-analysis.json` file in the project dir
(or accepts the dict directly). Each figure entry has the shape:

```json
{
  "figures": {
    "donor-bar": {
      "kind": "bar",
      "source": "per_donor_stats.csv",
      "x": "donor_id",
      "y": "lipid_score"
    },
    "lpi-vs-tg": {
      "kind": "scatter",
      "source": "lipid_pairs.csv",
      "x": "lpi",
      "y": "tg"
    }
  }
}
```

Supported `kind`: `bar`, `scatter`, `histogram`, `line`. Anything fancier
belongs in `vaultlab.figures.recipes`, not this pipeline.

## Pre-flight

1. Confirm `<project-dir>` exists
2. Confirm there's at least one tidy result table inside it
3. If a raw-data file is present, the pipeline will raise — point the
   user at their analysis code first

## Execution

```python
import shlex
from pathlib import Path
from vaultlab.analysis import run_pipeline

raw_args = shlex.split("$ARGUMENTS") if "$ARGUMENTS" else []
positional: list[str] = []
out_dir_arg: str | None = None
name_arg: str | None = None
i = 0
while i < len(raw_args):
    tok = raw_args[i]
    if tok == "--out" and i + 1 < len(raw_args):
        out_dir_arg = raw_args[i + 1]
        i += 2
    elif tok == "--name" and i + 1 < len(raw_args):
        name_arg = raw_args[i + 1]
        i += 2
    else:
        positional.append(tok)
        i += 1
project_dir = " ".join(positional).strip()
if not project_dir:
    raise SystemExit("usage: /run-analysis <project-dir> [--out ...] [--name ...]")

result = run_pipeline(
    project_dir,
    out_dir=out_dir_arg,
    project_name=name_arg,
    # figures_config=None → loaded from `vaultlab-analysis.json` in project_dir
)

print(f"Analysis complete for {result.project_dir}")
print(f"  inputs:          {len(result.inputs)} tidy table(s)")
print(f"  figures:         {len(result.figures)} written to {result.out_dir}")
print(f"  methods.md:      {result.methods_md}")
print(f"  manifests:       {len(result.manifest_paths)} sidecar(s)")
if result.methods_md is not None:
    print(f"to open: bobby-kb open {result.methods_md}")
```

## Output

- `out/stats_summary.json` — per-file per-column descriptive stats
- `out/<name>.png` — one PNG per figures_config entry, rcParams from
  `vaultlab.figures.contract`
- `out/methods.md` — drafted methods paragraph naming each input + each
  figure
- `<artifact>.provenance.json` + `<artifact>.method.md` next to every
  generated file (so collaborators / reviewers can audit exactly what
  produced each output)

## Test plan

- Sample project: drop `donor_stats.csv` + a one-figure
  `vaultlab-analysis.json` in a temp dir; run `/run-analysis <tempdir>`.
  Verify the figure rendered + methods.md exists + sidecars exist.
- Raw-data guard: drop a `*.fastq` next to the CSV → the pipeline should
  raise `ValueError("project_dir contains raw-data files: ...")` before
  doing any work.
- Explicit out: `/run-analysis <proj> --out /tmp/scratch` should write
  artifacts under `/tmp/scratch` regardless of the project dir.

## Rules of engagement

- **Tidy in, audit out.** This pipeline does not do raw-data wrangling.
  If your data isn't already in long/tidy CSV / Parquet, run your own
  analysis first.
- **methods.md is a draft.** Use `/polish` to clean it up before any
  manuscript draft.
- **Provenance is mandatory.** Every output carries a sidecar — don't
  hand-edit them; re-run the pipeline if the source data changed.

## Related

- `vaultlab.analysis.run_pipeline` — underlying pipeline
- `vaultlab.analysis.methods.compose_methods_paragraph` — the methods
  template
- `vaultlab.analysis.stats.summarize_dataframe` — the stats backend
- `vaultlab.figures.contract` — rcParams + colour palette
- `/polish` — clean up the drafted methods.md before sharing
- `/figure-contract` — design a figure spec before adding it to
  `vaultlab-analysis.json`
