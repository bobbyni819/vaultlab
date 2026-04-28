# Known limitations

vaultlab is **alpha-stage open-source software**. This document tracks known limitations honestly. Updated continuously.

## Status: v0.0.x — pre-release scaffold

The repo currently contains the architectural scaffold and design documentation. **Most subpackages contain only `__init__.py` placeholders.** Real implementations are being migrated in from `bobby-tools` over the next ~2 weeks toward v0.1.0 release (target: 2026-05-27).

What works in v0.0.x:
- The repo structure matches the master plan
- LICENSE, README, AGENTS.md, CLAUDE.md, CONTRIBUTING.md are real
- pyproject.toml correctly defines dependencies
- `pip install -e .` succeeds (but most CLI commands are placeholders)

What does NOT work in v0.0.x:
- Almost all CLI commands print "not yet implemented"
- The `vaultlab demo` command is a stub
- No actual figure generation, citation verification, or manuscript drafting
- Tests are not yet written

**Wait for v0.1.0 (target 2026-05-27) for any actual functionality.**

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

### Compliance

- vaultlab is **NOT HIPAA-compliant.** See [`docs/data-privacy.md`](data-privacy.md) and [`docs/compliance.md`](compliance.md).

### Dependencies

- Some optional integrations require heavy or platform-specific installs (Cellpose needs PyTorch; Cardinal needs R via `rpy2`; CellProfiler is a heavy CLI install). These are gated behind `pip install vaultlab[<modality>]` extras.

## Reporting new limitations

If you hit a limitation not listed here, [open an issue](https://github.com/bobbyni819/vaultlab/issues) using the bug template. Honest documentation of failures earns trust faster than glossy demos.
