# vaultlab.analysis

Takes the tidy result tables your analysis code already produced and turns them into figures, a draft Methods paragraph, and provenance receipts — without ever re-running the analysis itself.

Plain-language subsystem framing: see the "Figures from data" section of `G:/My Drive/Knowledge/vaultlab/Wiki/Concepts/vaultlab-subsystems.md` (this package is the descriptive/Methods half of that story). Architecture context: `docs/architecture.md`. Usage walkthrough with the JSON config and output layout: the sibling `pipeline.md` (SKILL bundle).

## What it is

This is the result-analysis pipeline. You point it at a project folder that holds finished result tables — CSV, Parquet, or TSV — and it summarizes every column, draws a small set of figures driven by a JSON config, drafts a Methods paragraph that cites each file and column with sample sizes, and writes a provenance receipt next to each artifact. It exists because vaultlab is the layer *above* analysis: the heavy statistical work (DE, clustering, model fitting) happens in your own project repo, and this package is the disciplined consumer that turns those tidy outputs into publication-shaped artifacts you can trust. The `/run-analysis` slash command is the natural-language front door; `run_pipeline` is the function it calls.

## Public surface

- `run_pipeline` — the entrypoint. Consumes a project's tidy tables and produces figures + a `methods.md` draft + a `stats_summary.json` + provenance sidecars, returning an `AnalysisResult`. Has an opt-in `audit=True` mode that runs a `rigor_auditor` pass over the drafted methods.
- `AnalysisResult` — the dataclass `run_pipeline` returns: the figure paths, the methods-md path, the per-file stats summary, the provenance manifest paths, the discovered inputs, the run mode, and any guardrail `interpretation_warnings`.
- `state_aware_preflight` — globs prior runs (in the KB project's `Output/` and the target out-dir) so an `extend` run builds on existing figures rather than starting from zero. The first concrete implementation of CLAUDE.md commitment #6.
- `PreflightResult` — what the preflight returns: the resolved mode, KB root, the set of prior figure stems, any prior stats summary, and a human log line.
- `summarize_dataframe` — describes every column of a DataFrame as a JSON-serializable dict (`{column: {dtype, n, n_missing, ...}}`); numeric columns also carry mean/std/min/max.
- `summarize_column` — the single-column version of the above.
- `compare_two_groups` — a Welch's two-sample t-test between two groups of a tidy table. **Verification-only**: it is a faithfulness check on already-tidy numbers, not upstream inference (see the boundary note below).
- `compose_methods_paragraph` — composes the draft Methods Markdown from a stats summary plus optional figure entries. Template-based, no LLM call.
- `RAW_DATA_EXTENSIONS` — the frozenset of raw-data extensions (`.fastq`, `.bam`, `.h5ad`, `.nd2`, `.czi`, `.tif`, `.mzml`, `.fcs`, ...) the pipeline rejects.
- `TIDY_RESULT_EXTENSIONS` — the frozenset it accepts (`.csv`, `.parquet`, `.pq`, `.tsv`, `.tab`).

## How it fits

It reads tidy result tables from a project directory (top level plus the `inputs/` and `data/` subtrees), and an optional `vaultlab-analysis.json` figures config from that same directory. On startup it resolves the KB root so the state-aware preflight can find prior runs, and — when a KB is configured — routes its outputs to the canonical `Output/<project>/runs/<date>/` location via `vaultlab.kb.paths`. It leans on a few sibling packages: `vaultlab.figures.contract` for the publication rcParams, `vaultlab.provenance` for the receipts, `vaultlab.roles._guardrails` + `vaultlab.runner.verifiers` to keep authored figure interpretations hedged and numerically self-consistent, and (only when `audit=True`) `vaultlab.workflows.crosstalk` for the rigor pass. Its outputs feed the rest of the pipeline: the figures drop into `vaultlab.slides`, the `methods.md` draft goes on to `vaultlab.citations` for citation verification and `vaultlab.manuscript` polish, and after a run it updates the project's `START_HERE.md` so the next session resumes cleanly.

## What it does NOT do

- It does **not** run analyses — no model fitting, no DE / clustering / dimensionality reduction, no hypothesis testing as a primary step. Run that in your project code first and hand it the tidy outputs.
- It does **not** read raw data. If it finds a raw-data file (or a raw `.xlsx`/`.xls` spreadsheet) in the project's top level, `inputs/`, or `data/`, it raises `ValueError` naming the offenders and pointing you back to your analysis code.
- It is **not** a chart library. The figure vocabulary is deliberately four kinds — `bar`, `scatter`, `histogram`, `line`; anything fancier belongs in `vaultlab.figures.recipes`.
- The one carve-out from "consumes, not computes": `compare_two_groups` recomputes a Welch's t-test on already-tidy two-group values purely as a verification check, surfaced as a hedged interpretive line — never as a substitute for upstream inference.

## Files

- `pipeline.py` — `run_pipeline`, `state_aware_preflight`, the scope-discipline enforcement, input discovery, the four-kind matplotlib renderer, and the provenance-sidecar writers.
- `stats.py` — `summarize_dataframe` / `summarize_column` (descriptive, JSON-safe) and `compare_two_groups` (verification-only Welch's t-test).
- `methods.py` — `compose_methods_paragraph`, the template-based draft Methods composer (cites each file, column, and figure with sample sizes; closes in hedged voice).
- `pipeline.md` — the SKILL-bundle doc: when to use the pipeline, the scope contract, the `vaultlab-analysis.json` schema, and the output layout.

## See also

- `pipeline.md` (this directory) — the user-facing how-to, input/output examples, and composition tips.
- `../figures/` — the recipe library for figures beyond the four-kind vocabulary, and the `figures.contract` rcParams this package applies.
- `../provenance/` — the receipt format (`.provenance.json` + `.method.md`) every artifact here carries.
- `../citations/` — verifies citations added to the methods draft.
- `../manuscript/` — polishes the methods draft toward submission.
- `.claude/commands/run-analysis.md` — the slash command that drives `run_pipeline`.
