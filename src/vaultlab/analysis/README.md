# vaultlab.analysis

Takes the tidy result tables your analysis code already produced and turns them into figures, a draft Methods paragraph, and provenance receipts — without ever re-running the analysis itself.

Plain-language subsystem framing: see the "Figures from data" section of `G:/My Drive/Knowledge/vaultlab/Wiki/Concepts/vaultlab-subsystems.md` (this package is the descriptive/Methods half of that story). Architecture context: `docs/architecture.md`. Usage walkthrough with the JSON config and output layout: the sibling `pipeline.md` (SKILL bundle).

## What it is

This is the result-analysis pipeline. You point it at a project folder that holds finished result tables — CSV, Parquet, or TSV — and it summarizes every column, draws a small set of figures driven by a JSON config, drafts a Methods paragraph that cites each file and column with sample sizes, and writes a provenance receipt next to each artifact. It exists because vaultlab is the layer *above* analysis: the heavy statistical work (DE, clustering, model fitting) happens in your own project repo, and this package is the disciplined consumer that turns those tidy outputs into publication-shaped artifacts you can trust. The `/run-analysis` slash command is the natural-language front door; `run_pipeline` is the function it calls.

A second run on the same project is **additive, not destructive**. Pass `mode="extend"` and the pipeline reads what prior runs already produced (via the state-aware preflight) and keeps identically-named figures in place rather than clobbering them — the default `mode="fresh"` reproduces a clean run each time. Where a figure compares two groups, it also attaches a hedged, recomputed-on-the-numbers interpretation sentence — a faithfulness check, never a substitute for your upstream inference.

## Public surface

- `run_pipeline` — the entrypoint. Consumes a project's tidy tables and produces figures + a `methods.md` draft + a `stats_summary.json` + provenance sidecars, returning an `AnalysisResult`. Levers you can pass: `out_dir` (defaults to the canonical KB run dir, else `<project>/out`), `figures_config` (a dict; if omitted it reads `vaultlab-analysis.json`), `project_name` (the methods header + START_HERE slug), `kb_root` (override the KB used for preflight + output routing), `mode` (`"fresh"` | `"extend"`), and `audit` + `audit_runner` (opt-in rigor pass). `audit=True` without an `audit_runner` raises `ValueError`.
- `AnalysisResult` — the dataclass `run_pipeline` returns: the resolved project dir + out dir, the figure paths, the methods-md path (or `None` when there were no inputs), the per-file stats summary, the provenance manifest paths, the discovered inputs, the run `mode`, the optional `audit_result` verdict (`{"passed", "issues"}` when audited, else `None`), and any guardrail `interpretation_warnings`.
- `state_aware_preflight` — globs prior runs (in the KB project's `Output/` and the target out-dir) for prior figure stems and a prior `stats_summary.json`, so an `extend` run builds on existing figures rather than starting from zero. Never raises — an unconfigured KB is a graceful no-op. The first concrete implementation of CLAUDE.md commitment #6.
- `PreflightResult` — what the preflight returns: the resolved mode, KB root, the set of prior figure stems, any prior stats summary, and a human log line (`"found N prior figures; extending"`).
- `summarize_dataframe` — describes every column of a DataFrame as a JSON-serializable dict (`{column: {dtype, n, n_missing, ...}}`); numeric columns also carry mean/std/min/max.
- `summarize_column` — the single-column version of the above. Numeric columns get mean/std (sample std, ddof=1; `None` when n≤1)/min/max; non-numeric (categorical / string / boolean / datetime) columns get `unique_count` plus up to five `top_values`. NaN and infinities map to `None` so the dict is always `json.dumps`-safe.
- `compare_two_groups` — a Welch's two-sample t-test (`scipy.stats.ttest_ind(equal_var=False)`) between two groups of a tidy table. Returns `{mean_a, mean_b, n_a, n_b, t_stat, p_value, direction}`; `t_stat`/`p_value` are `None` when a group has < 2 values, and `direction` is `"a>b"` / `"a<b"` / `"a==b"` / `"indeterminate"` (the last when a group has no matching rows, so a missing group is not read as equal means). **Verification-only**: it is a faithfulness check on already-tidy numbers, not upstream inference (see the boundary note below).
- `compose_methods_paragraph` — composes the draft Methods Markdown from a stats summary plus optional figure entries and per-figure interpretation sentences. Template-based, no LLM call. Emits a result-tables roster, per-column statistics, a figures list, and a hedged interpretation note.
- `RAW_DATA_EXTENSIONS` — the frozenset of raw-data extensions (`.fastq`/`.fq`/`.fastq.gz`/`.fq.gz`, `.bam`/`.sam`/`.cram`, `.vcf`/`.bcf`, `.h5`/`.h5ad`/`.loom`, `.nd2`/`.czi`/`.lif`, `.tif`/`.tiff`, `.nii`/`.dcm`, `.mzml`/`.mzxml`/`.raw`/`.wiff`, `.fcs`) the pipeline rejects.
- `TIDY_RESULT_EXTENSIONS` — the frozenset it accepts (`.csv`, `.parquet`, `.pq`, `.tsv`, `.tab`).

Spreadsheet formats (`.xlsx`, `.xls`) are also rejected — but with a *distinct* message telling you to tidy the sheet to a CSV (one header row, one observation per row) rather than re-run instrument analysis. That set lives in `pipeline.py` as the module-level constant `SPREADSHEET_EXTENSIONS`; unlike `RAW_DATA_EXTENSIONS` and `TIDY_RESULT_EXTENSIONS` it is **not** re-exported from `vaultlab.analysis` — import it from `vaultlab.analysis.pipeline` if you need it directly. The rejection behavior is described under "What it does NOT do" below.

## How it fits

It reads tidy result tables from a project directory (top level plus the `inputs/` and `data/` subtrees), and an optional `vaultlab-analysis.json` figures config from that same directory. On startup it resolves the KB root so the state-aware preflight can find prior runs, and — when a KB is configured — routes its outputs to the canonical `Output/<project>/runs/<date>/` location via `vaultlab.kb.paths`. It leans on a few sibling packages: `vaultlab.figures.contract` for the publication rcParams, `vaultlab.provenance` for the receipts, `vaultlab.roles._guardrails` + `vaultlab.runner.verifiers` to keep authored figure interpretations hedged and numerically self-consistent, and (only when `audit=True`) `vaultlab.workflows.crosstalk` for the rigor pass. Its outputs feed the rest of the pipeline: the figures drop into `vaultlab.slides`, the `methods.md` draft goes on to `vaultlab.citations` for citation verification and `vaultlab.manuscript` polish, and after a run it updates the project's `START_HERE.md` so the next session resumes cleanly.

## The figures config

Each entry under `figures` in `vaultlab-analysis.json` (or the `figures_config` dict) names one output PNG. The renderer reads:

- `kind` — one of `bar`, `scatter`, `histogram`, `line` (required).
- `source` — the input table to plot, matched by basename or stem against the discovered inputs.
- `x` / `y` — the columns to plot. `histogram` needs only `x`; `bar` / `scatter` / `line` need both. A bar plot shows the per-group `mean(y)`; a line plot sorts by `x` first.
- `title`, `xlabel`, `ylabel`, `color` — optional cosmetics (`color` defaults to a pastel blue; labels default to the column names).
- `bins` — histogram bin count (default 20).
- `groups: [a, b]` — for a bar figure whose `x` has **more than two** distinct values, the explicit pair to compare in the hedged interpretation line. With exactly two distinct values the pair is inferred; with more than two and no `groups`, no comparison is fabricated.

Two robustness behaviors worth knowing: a figure whose name could escape the output dir (a path separator, an absolute path, `.`/`..`) is **skipped with a warning** rather than written, and a single figure that fails to render is logged and skipped — it does not abort the rest of the run.

## The hedged two-group interpretation

A bar figure with a numeric `y` and a categorical `x` resolving to exactly two groups (or an explicit `groups` pair) gets one extra output: a hedged sentence appended to its methods bullet, e.g. *"`expression` appears higher in `treated` than `control`; recomputed Welch's t-test n=12/11, p=0.031 (hedged, verification only — not upstream inference)."* This sentence is recomputed from the tidy values via `compare_two_groups`, and is double-checked against the hedge guardrail and the numeric-consistency verifier before it ships; a guardrail trip surfaces loudly in `AnalysisResult.interpretation_warnings` rather than being swallowed. When the figure is not a clean two-group numeric bar, no comparison is invented and only the structural description is written.

## What it does NOT do

- It does **not** run analyses — no model fitting, no DE / clustering / dimensionality reduction, no hypothesis testing as a primary step. Run that in your project code first and hand it the tidy outputs.
- It does **not** read raw data. If it finds a raw-data file in the project's top level, `inputs/`, or `data/`, it raises `ValueError` naming the offenders and pointing you back to your analysis code. The scan is non-recursive at the top level (so raw data parked in a sibling folder like `raw_backup/` is not false-flagged) but recurses into `inputs/` and `data/`.
- It does **not** read raw spreadsheets either. An `.xlsx`/`.xls` in scope raises a *distinct* `ValueError` telling you to tidy the sheet to a CSV first (one header row, one observation per row) — rather than re-running instrument analysis. The Parquet path likewise fails with an actionable message if no Parquet engine (pyarrow / fastparquet) is installed, instead of pandas' opaque error.
- It is **not** a chart library. The figure vocabulary is deliberately four kinds — `bar`, `scatter`, `histogram`, `line`; anything fancier belongs in `vaultlab.figures.recipes`.
- The one carve-out from "consumes, not computes": `compare_two_groups` recomputes a Welch's t-test on already-tidy two-group values purely as a verification check, surfaced as a hedged interpretive line — never as a substitute for upstream inference.

## Files

- `pipeline.py` — `run_pipeline`, `state_aware_preflight`, the raw-data + spreadsheet scope-discipline enforcement, KB-aware output routing, input discovery, the additive `extend` keep-existing-figures logic, the four-kind matplotlib renderer (with the hedged two-group interpretation), the provenance-sidecar writers, and the best-effort START_HERE update.
- `stats.py` — `summarize_dataframe` / `summarize_column` (descriptive, JSON-safe) and `compare_two_groups` (verification-only Welch's t-test).
- `methods.py` — `compose_methods_paragraph`, the template-based draft Methods composer (cites each file, column, and figure with sample sizes; closes in hedged voice).
- `pipeline.md` — the SKILL-bundle doc: when to use the pipeline, the scope contract, the `vaultlab-analysis.json` schema, and the output layout.

## See also

- `pipeline.md` (this directory) — the user-facing how-to, input/output examples, and composition tips.
- `../figures/` — the recipe library for figures beyond the four-kind vocabulary, and the `figures.contract` rcParams this package applies.
- `../provenance/` — the receipt format (`.provenance.json` + `.method.md` per artifact, plus the append-only `.vaultlab-provenance.jsonl` index in the out-dir) every artifact here carries.
- `../citations/` — verifies citations added to the methods draft.
- `../manuscript/` — polishes the methods draft toward submission.
- `.claude/commands/run-analysis.md` — the slash command that drives `run_pipeline`.
- `examples/result-analysis/` — a runnable end-to-end example (tidy CSV + `vaultlab-analysis.json` → figures + methods + receipts) with `expected_outputs/`.
