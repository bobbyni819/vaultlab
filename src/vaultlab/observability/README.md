# vaultlab.observability

The reserved home for run-progress reporting and structured execution traces — **currently a placeholder, with no public API yet.**

This package is named in the architecture sketch in [`docs/architecture.md`](../../../docs/architecture.md) (the `observability/` line under the package map, scoped as *"rich progress + JSONL trace"*). There is no matching section in the plain-language subsystems guide yet because the package has not been built out.

## What it is

`vaultlab.observability` is intended to be the one place where a long-running vaultlab primitive narrates *what it is doing right now* (a live progress feed for the human watching) and *what it did* (a structured, machine-readable trace of each step, written as JSONL). Today it is an empty stub: the directory holds only `__init__.py`, whose docstring reads *"Placeholder. Will be populated by migration commits."* Nothing imports it, and it exports nothing.

The functionality it is meant to consolidate already exists in scattered form across the codebase — primitives currently emit progress events through their own small `progress` callback hooks and write their own diagnostic traces and manifests next to their outputs. This package is the planned destination for that pattern once it is factored out and shared, not new behaviour layered on top.

## Public surface

**None.** The package is a placeholder. `__init__.py` defines no `__all__`, no classes, and no functions — only a module docstring. There is nothing here to import or call yet.

If you are looking for the progress/trace behaviour that this package is *eventually* meant to own, see **How it fits** below for where it lives today.

## How it fits

- **Today:** observability concerns are handled inline by the primitives that need them. For example, `vaultlab.research.lineage` carries a `progress` callback and an internal `_emit(...)` helper, and writes per-source search-trace and per-DOI acquisition-trace files; `vaultlab.figures.acquisition` writes a re-run manifest. Those modules treat traces as diagnostic, not load-bearing — failure to write one is logged and ignored.
- **Intended:** this package would become the shared layer those primitives call into, so a single progress/trace convention (rich live progress for the terminal, JSONL traces for after-the-fact inspection) is reused rather than re-implemented per primitive.

Until the migration happens, depending on `vaultlab.observability` from anywhere will get you an empty module.

## What it does NOT do

- It does **not** export any progress reporter, tracer, logger, or context object today — there is no code here beyond the placeholder docstring.
- It is **not** wired into any primitive; nothing in vaultlab imports it.
- It is **not** the persistence layer for results, citations, or provenance receipts — structured *output* provenance lives in `vaultlab.provenance`; this package is about *execution* progress and traces.
- It does **not** define new behaviour beyond consolidating the progress/trace pattern that primitives already implement locally.

## Files

- `__init__.py` — placeholder module; docstring only, no public symbols.

(No sibling `.md` docs, submodules, or tests exist for this package yet.)

## See also

- [`docs/architecture.md`](../../../docs/architecture.md) — the package map entry that reserves this name (`observability/` → *rich progress + JSONL trace*).
- `vaultlab.provenance` — per-output provenance receipts (the *output* side of trustworthiness, distinct from *execution* tracing).
- `vaultlab.research.lineage` — where progress callbacks and search/acquisition traces currently live.
- `vaultlab.figures.acquisition` — where the figure-acquisition re-run manifest currently lives.
- `vaultlab.errors` — `retry` / `degraded` / `llm_recover` decorators, the related cross-cutting reliability layer.
