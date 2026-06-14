# vaultlab.errors

A reserved home for vaultlab's shared error-handling and resilience helpers — currently an empty placeholder, not yet populated.

> Plain-language subsystem guide: `G:/My Drive/Knowledge/vaultlab/Wiki/Concepts/vaultlab-subsystems.md`. Architectural sketch: [`docs/architecture.md`](../../../docs/architecture.md) (see the `errors/` line in the top-level package map).

## What it is

This package is a stub. As of now `src/vaultlab/errors/__init__.py` contains only a docstring — `"Placeholder. Will be populated by migration commits."` — and exports nothing. It exists to stake out a single, obvious place for the cross-cutting resilience helpers that the architecture wants vaultlab to share: the small decorators and wrappers that decide what happens when an LLM call, an external API, or a file read fails partway through. The intent (per the architecture's package map) is for this to eventually hold `retry`, `degraded`, and `llm_recover`-style decorators so the rest of the codebase can lean on one consistent failure policy instead of re-implementing retries in every module.

That migration has not happened yet. Until it does, the resilience logic that *is* live lives next to the code that needs it — most notably the retry helper in [`research/retry.py`](../research/retry.py), used by the literature-search sources, PDF acquisition, and summarization passes.

## Public surface

There is no public API yet. The package exports no symbols (`__all__` is not defined; the module body is a docstring only). Importing `vaultlab.errors` succeeds but gives you nothing to call.

If you are looking for retry/degrade/recover behavior **today**, reach for the in-place helpers instead — e.g. the retry decorator under `vaultlab.research.retry` — rather than importing from here.

## How it fits

Nothing currently imports from `vaultlab.errors`; a repo-wide grep finds no references. When it is populated, it would sit *underneath* the orchestration and I/O layers — the runner, the research/literature sources, the context pipes (Google/Outlook), and the figure/slide builders would wrap their fragile outbound calls in these decorators so a flaky network or a bad model response degrades to a flagged fallback rather than crashing a long pipeline. It reads nothing from the KB and writes nothing to it; it is pure plumbing.

## What it does NOT do

- It does **not** export any functions, classes, or decorators right now — it is a reserved name, not a working module.
- It is **not** the current source of retry/degrade/recover behavior; that logic lives in `research/retry.py` and similar per-module helpers until the migration lands.
- It does **not** define the project's exception *types* or domain errors (those live with the components that raise them, e.g. `KbRootNotConfigured` in `vaultlab.context`).
- It does **not** do logging, tracing, or progress reporting — that is `vaultlab.observability`'s job.

## Files

- `__init__.py` — placeholder module (docstring only; no exports). Reserved for future migration commits.
- `README.md` — this file.

## See also

- [`docs/architecture.md`](../../../docs/architecture.md) — top-level package map; the `errors/` line records the intended `retry` / `degraded` / `llm_recover` contents.
- [`research/retry.py`](../research/retry.py) — where the live retry helper currently lives.
- `vaultlab.observability` — rich progress + JSONL trace (the sibling cross-cutting concern for *seeing* what ran, vs. *recovering* from what failed).
- `NEXT_STEPS.md` (repo root) — tracks not-yet-built scaffolding like this one.
