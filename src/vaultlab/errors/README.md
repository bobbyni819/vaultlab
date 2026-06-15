# vaultlab.errors

A reserved home for vaultlab's shared error-handling and resilience helpers — currently an empty placeholder, not yet populated.

> Plain-language subsystem guide: `G:/My Drive/Knowledge/vaultlab/Wiki/Concepts/vaultlab-subsystems.md`. Architectural sketch: [`docs/architecture.md`](../../../docs/architecture.md) (see the `errors/` line in the top-level package map).

## What it is

This package is a stub. As of now `src/vaultlab/errors/__init__.py` contains only a docstring — `"Placeholder. Will be populated by migration commits."` — and exports nothing. It exists to stake out a single, obvious place for the cross-cutting resilience helpers that the architecture wants vaultlab to share: the small decorators and wrappers that decide what happens when an LLM call, an external API, or a file read fails partway through. The intent (per the architecture's package map) is for this to eventually hold `retry`, `degraded`, and `llm_recover`-style decorators so the rest of the codebase can lean on one consistent failure policy instead of re-implementing retries in every module.

That migration has not happened yet. Until it does, the resilience logic that *is* live lives next to the code that needs it — most notably the retry-with-feedback helper in [`research/retry.py`](../research/retry.py). That helper (`retry_with_feedback`) calls a fragile callback, and on failure truncates the error context and feeds it back into the next attempt so the LLM can self-correct, bounded so a flaky step can't loop forever. It distinguishes three failure modes — the callback **raised**, **returned nothing useful** (None / empty / non-dict), or **failed a caller-supplied validation** — and returns a record of every attempt. It is the closest thing vaultlab has today to the `retry` decorator this package is reserved to hold.

## Public surface

There is no public API yet. The package exports no symbols — `__init__.py` is a single docstring (`"Placeholder. Will be populated by migration commits."`), `__all__` is not defined, and `dir(vaultlab.errors)` has nothing user-facing in it. Importing `vaultlab.errors` succeeds but gives you nothing to call.

If you are looking for retry / degrade / recover behavior **today**, reach for the in-place helper instead — `vaultlab.research.retry` — rather than importing from here. Its public surface is:

- `retry_with_feedback(callback, task, *, max_retries=1, validate=None, apply_feedback=None, max_feedback_chars=1500)` — call a callback with bounded retry; on each failure, append the (truncated) error context to the task's prompt so the next attempt can self-correct. Returns a `RetryResult`.
- `truncate_feedback(text, *, max_chars=1500)` — keep the *tail* of an error message (where the real exception usually is) so a long stack trace doesn't blow the LLM's context budget.
- `RetryResult` — the outcome: the final `response` (or `None` if every attempt failed), the list of `attempts`, and a `succeeded` flag.
- `RetryAttempt` — one attempt's record: its 1-indexed number, whether it `succeeded`, the `failure_mode` (`"exception"` / `"empty"` / `"validation"`), and the `error_text` that would be fed back.

That helper's pattern (capture-error → feed-back → bounded retry) is exactly the shape the future `retry` decorator here is meant to generalize.

## How it fits

Nothing currently imports from `vaultlab.errors` — a repo-wide grep finds no runtime references, only two doc mentions (this README and a forward-looking cross-reference in `vaultlab.observability`'s README, which names the eventual `retry` / `degraded` / `llm_recover` decorators as its sibling reliability layer). No CLI subcommand and no slash command routes into this package. When it is populated, it would sit *underneath* the orchestration and I/O layers — the runner, the research/literature sources, the context pipes (Google/Outlook), and the figure/slide builders would wrap their fragile outbound calls in these decorators so a flaky network or a bad model response degrades to a flagged fallback rather than crashing a long pipeline. It reads nothing from the KB and writes nothing to it; it is pure plumbing.

## What it does NOT do

- It does **not** export any functions, classes, or decorators right now — it is a reserved name, not a working module.
- It is **not** the current source of retry/degrade/recover behavior; the live retry-with-feedback helper lives in `research/retry.py` (and similar per-module helpers) until the migration lands.
- It does **not** back any user-facing CLI subcommand or slash command — there is no `vaultlab errors …` command and nothing dispatches here.
- It does **not** define the project's exception *types* or domain errors (those live with the components that raise them, e.g. `KbRootNotConfigured` in `vaultlab.context`).
- It does **not** do logging, tracing, or progress reporting — that is `vaultlab.observability`'s job.

## Files

- `__init__.py` — placeholder module (docstring only; no exports). Reserved for future migration commits.
- `README.md` — this file.

## See also

- [`docs/architecture.md`](../../../docs/architecture.md) — top-level package map; the `errors/` line reads `# retry, degraded, llm_recover decorators`, recording the intended contents.
- [`research/retry.py`](../research/retry.py) — where the live retry-with-feedback helper (`retry_with_feedback` + `RetryResult` / `RetryAttempt` / `truncate_feedback`) currently lives.
- [`vaultlab.observability`](../observability/README.md) — rich progress + JSONL trace (the sibling cross-cutting concern for *seeing* what ran, vs. *recovering* from what failed); its README cross-references this package as its reliability counterpart.
- `NEXT_STEPS.md` (repo root) — tracks vaultlab's other not-yet-built scaffolding (the `stats/` package, the recipe corpus, contributor templates). Note: it does **not** currently track this `errors/` placeholder by name.
