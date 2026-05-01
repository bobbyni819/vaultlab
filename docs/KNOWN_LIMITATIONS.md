# Known limitations

vaultlab is **alpha-stage open-source software**. This document tracks known limitations honestly. Updated continuously.

## Status: v0.0.x — alpha software, working orchestrators

The repo contains working orchestrators wired through Claude Code as the LLM runtime. Most of the framework is functional; the rough edges are at the orchestrator boundaries (rerun behavior, alternate input paths) rather than at the core. Test count: 1093 (as of 2026-04-30). Target for v0.1.0 release: 2026-05-27.

**What works in v0.0.x** (per-orchestrator readiness rated empirically):

- `/onboard-project <folder>` — GREEN
- `/start-project "<topic>"` — GREEN
- `/lit-arc <topic>` — YELLOW (works clean for typical paths; reruns overwrite summaries in place)
- `/build-deck <source>` — YELLOW (lineage path validated; paper-PDF and wet-lab-data paths under-exercised)
- `/understand-figure` — YELLOW for Claude-Code mode (works), SDK mode requires real `ANTHROPIC_API_KEY` (Claude Code OAuth tokens are rejected by the Messages API — Anthropic-side limitation)
- `/lit-report <topic>` — RED for full corpora; smoke-tested only on a small synthetic corpus (architectural async-callback redesign needed)

**Known rough edges before v0.1.0:**

- `/lit-arc` rerun is NOT additive at the summary level — `Wiki/Summaries/<doi>.md` overwrites in place. Decisions log is correctly additive. State-aware reruns (`since: <date>`) is on the v0.1.x track.
- Run artifact location is inconsistent — `run_dir` only auto-populates on the crosstalk path; straight `run_lit_arc` falls back to `Sources/Notes/`.
- If your topic is heavily Elsevier-paywalled, expect ~30% of recent papers to fail acquisition without an Elsevier API key. `/lit-arc` doesn't yet warn early on low acquisition rates.
- SDK-mode users need a real Anthropic API key, not a Claude Code OAuth token.

For the empirical readiness check that informs this section, see the per-orchestrator GREEN/YELLOW/RED breakdown in the project KB (`Sources/Notes/readiness-for-external-use-2026-04-30.md` if you have access to the development KB).

---

## Anticipated limitations for v0.1.0+ (recorded in advance for honesty)

### Data

- When input data has <500 cells, clustering produces unstable results. vaultlab's auto-cluster-annotate flags low-confidence labels but does not block. Re-cluster manually with higher resolution.
- When CODEX channels include uncalibrated markers (no positive control), cluster annotations may name cell types that don't exist in your sample. Always cross-check `cluster_annotations.md` against your panel notes.

### Citation verification

- When a citation is paywalled and not in your KB, vaultlab falls back to abstract-level matching. Verdicts will be `WEAKLY_SUPPORTED` rather than `SUPPORTED`. To upgrade, ingest the full PDF into the KB.
- For preprints with multiple versions, vaultlab uses the latest version on bioRxiv unless you specify a DOI explicitly. Check `evidence.json` for the `verifier_version` field.

### LLM

- Hallucination rate on cluster annotation: ~5% expected (per HuBMAP tonsil eval; benchmark to be reported in v0.1.0). Always review LLM-generated annotations before publication.
- Figure caption faithfulness drops when the figure has >5 panels with related but distinct content (LLM may conflate). Workaround: split into sub-figure captions.

### Performance

- Pipeline time scales linearly with #cells for clustering, quadratically for spatial neighborhood enrichment. >100k cells → consider downsampling.
- LLM costs scale with manuscript length and #citations. A 50-cite, 3000-word manuscript audit ≈ $1.50 in Anthropic billing (estimate; will refine post-launch).

### Infrastructure

- vaultlab is local-first. No hosted compute; no cloud sync. If your data is >100GB, expect proportional disk usage in `<kb>/Output/`.
- Obsidian integration uses the Advanced URI plugin. If you uninstall it, `vaultlab kb open` falls back to your default text editor.

### Figure annotation (motif labeling)

The figure-understanding pipeline ships its describe + localize + match steps as v0.1 (these are stable and produce useful per-figure understanding text). The **Step 4 verify-and-render-annotated-PNG** sub-step is **partial** for v0.1:

- Verification iteration sometimes oscillates between ACCEPT and REJECT on borderline figures. The describe/localize/match outputs are still useful even when verify oscillates — they're emitted regardless.
- The rendered annotated PNG isn't always usable for slide insertion (annotations occasionally land outside intended panels). v0.1 ships the annotation render as best-effort; for slide-grade output, prefer the original unannotated figure with vaultlab's text-only caption.
- Stabilizing verify-iteration on borderline figures is a v0.2 candidate.

This is a **deliberate v0.1 scope cut** — the underlying machinery (describe + localize + match) is real and tested; the polish on the final annotation overlay isn't release-blocking.

### Compliance

- vaultlab is **NOT HIPAA-compliant.** See [`docs/data-privacy.md`](data-privacy.md) and [`docs/compliance.md`](compliance.md).

### Dependencies

- Some optional integrations require heavy or platform-specific installs (Cellpose needs PyTorch; Cardinal needs R via `rpy2`; CellProfiler is a heavy CLI install). These are gated behind `pip install vaultlab[<modality>]` extras.

## Reporting new limitations

If you hit a limitation not listed here, [open an issue](https://github.com/bobbyni819/vaultlab/issues) using the bug template. Honest documentation of failures earns trust faster than glossy demos.
