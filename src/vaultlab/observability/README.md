# vaultlab.observability

The reserved home for run-progress reporting and structured execution traces — **currently a placeholder, with no public API yet.**

This package is named in the architecture sketch in [`docs/architecture.md`](../../../docs/architecture.md) (the `observability/` line under the package map, scoped as *"rich progress + JSONL trace"*). There is no matching section in the plain-language subsystems guide yet because the package has not been built out.

## What it is

`vaultlab.observability` is intended to be the one place where a long-running vaultlab primitive narrates *what it is doing right now* (a live progress feed for the human watching) and *what it did* (a structured, machine-readable trace of each step, written as JSONL). Today it is an empty stub: the directory holds only `__init__.py`, whose docstring reads *"Placeholder. Will be populated by migration commits."* Nothing imports it, and it exports nothing.

The functionality it is meant to consolidate already exists in scattered form across the codebase — primitives currently emit progress events through their own small `progress` callback hooks and write their own diagnostic traces and manifests next to their outputs. This package is the planned destination for that pattern once it is factored out and shared, not new behaviour layered on top.

A defining property of the pattern this package would own is that **observability is treated as diagnostic, never load-bearing.** Today the primitives say so in their own code — the trace files carry comments like *"the trace is observability, not load-bearing data"* — and a failure to emit a progress event or write a trace is logged at debug level and swallowed, so the primitive's real work is never blocked by a broken trace. Any shared layer this package eventually exposes is expected to preserve that contract: a watcher and an audit aid, not a dependency the run can fail on.

## Public surface

**None.** The package is a placeholder. `__init__.py` defines no `__all__`, no classes, and no functions — only a module docstring. There is nothing here to import or call yet.

If you are looking for the progress/trace behaviour that this package is *eventually* meant to own, see **How it fits** below for where it lives today.

## How it fits

- **Today:** observability concerns are handled inline by the primitives that need them. The pattern this package would own can be seen in three concrete places, each tagged in-code as a numbered "Gap":
  - **Live progress** — `vaultlab.research.lineage` carries an optional `progress` callback and an internal `_emit(progress, ...)` helper that forwards each step to that callback. Crucially, if the callback raises, `_emit` catches it and logs at debug level (*"progress callback raised"*) — the run continues. That swallow-on-error shape is the convention a shared reporter would inherit.
  - **Per-source search trace (Gap 1)** — `lineage` writes a side-by-side, per-source trace of a literature search (which source returned what), explicitly noting a failure to write it is non-fatal.
  - **Per-DOI acquisition trace (Gap 2)** — `lineage` also writes a per-DOI PDF-acquisition trace recording how each paper's full text was (or wasn't) obtained across the download waterfall.
  - **Figure re-run manifest (Gap 3)** — `vaultlab.figures.acquisition` writes a manifest that records what a figure render consumed, so the render can be reproduced or re-run.
- **Intended:** this package would become the shared layer those primitives call into, so a single progress/trace convention — rich live progress for the terminal, JSONL traces for after-the-fact inspection — is reused rather than re-implemented per primitive. The `Gap 1/2/3` labels in the code are the inventory of what a first migration would absorb.

Until the migration happens, depending on `vaultlab.observability` from anywhere will get you an empty module.

## What it does NOT do

- It does **not** export any progress reporter, tracer, logger, or context object today — there is no code here beyond the placeholder docstring.
- It is **not** wired into any primitive; nothing in vaultlab imports it.
- It is **not** the persistence layer for results, citations, or provenance receipts — structured *output* provenance lives in `vaultlab.provenance`; this package is about *execution* progress and traces.
- It does **not** define new behaviour beyond consolidating the progress/trace pattern that primitives already implement locally.
- It does **not** today emit the "rich" terminal progress its architecture line promises (the `rich`-library live display). The progress that exists now is the plain callback-forwarding hook described above; a styled live feed is part of what a build-out would add, not something this package ships yet.
- It is **not** a backing store you should write a load-bearing audit log to — by the pattern's own contract, traces are diagnostic and a failed write is ignored, so nothing safety-critical should depend on a trace being present.

## Files

- `__init__.py` — placeholder module; docstring only, no public symbols.

(No sibling `.md` docs, submodules, or tests exist for this package yet.)

## See also

- [`docs/architecture.md`](../../../docs/architecture.md) — the package map entry that reserves this name (`observability/` → *rich progress + JSONL trace*).
- `vaultlab.provenance` — per-output provenance receipts (the *output* side of trustworthiness, distinct from *execution* tracing).
- `vaultlab.research.lineage` — where progress callbacks and search/acquisition traces currently live.
- `vaultlab.figures.acquisition` — where the figure-acquisition re-run manifest currently lives.
- [`vaultlab.errors`](../errors/README.md) — the sibling cross-cutting reliability layer (recovering from what failed, vs. this package's seeing what ran). It is also a placeholder today: its `__init__.py` exports nothing, and the `retry` / `degraded` / `llm_recover` decorators named on the `errors/` line of [`docs/architecture.md`](../../../docs/architecture.md) are reserved/intended contents, not current symbols. The live resilience helper is `retry_with_feedback` (a function, not a decorator) in [`vaultlab.research.retry`](../research/retry.py).
