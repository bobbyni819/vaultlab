# scripts/_personal/

These scripts are **personal-use, not portable**, and exist as a record of how the maintainer (Bobby) drove specific test runs against his own KB during early development.

They are committed to the repo but:

- **Do not run them** unless you are Bobby running on Bobby's machine.
- They have hardcoded `G:/My Drive/Knowledge/vaultlab/...` paths that won't exist on your system.
- They reference internal-iteration jargon (`evening-3`, `phase 1a`, `L4 stage A`) that won't match your project layout.
- They are kept in-tree so that the commit history accurately reflects what was actually run during early development — not because anyone outside the maintainer's machine should re-run them.

## What's in here

- `_evening*.py` / `_e2e_*.py` / `_trial_*.py` / `_demo_*.py` — date-stamped trial scripts driving specific debugging or stress-test runs against Bobby's CODEX / spatial-tx KB.
- `_audit_l4_decks.py` / `l4_e2e_*.py` — internal audit scripts for the L4 milestone work.
- `phase1*_codex*.py` / `reacquire_codex_pdfs.py` / `extract_codex_dois.py` — CODEX-corpus-specific harness scripts.
- `figure_understanding_*.py` — early prototypes of the figure-understand pipeline that landed in `vaultlab.figures.understand`.

## Where the runnable / shareable demos live

For demos that work on any machine:

- `examples/` — runnable example projects (codex_hubmap_tonsil, pbmc3k, visium_brain).
- `scripts/build_demo_pptx_v2.py`, `scripts/build_native_annotated_demo.py`, `scripts/research_pipeline_crispr_demo.py` — top-level demo scripts that should run against the bundled examples.

If you want to verify vaultlab works end-to-end, start there.
