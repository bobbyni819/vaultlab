# vaultlab.cache

A reserved slot for vaultlab's content-addressable caches. **It is a placeholder today — no public API, no working cache code yet.**

For the plain-language tour of vaultlab's subsystems see the [subsystems guide](../../../docs/) (`vaultlab-subsystems.md` in the KB); for the architectural map see [`docs/architecture.md`](../../../docs/architecture.md), where this package is sketched as "Content-addressable caches."

## What it is

`vaultlab.cache` is where the project intends to centralize **content-addressable caching** — storing the result of an expensive operation under a key derived from its inputs, so a later run that asks the same question gets the cached answer instead of paying for it twice. The architecture map reserves this package for that role. As of now the module is an empty stub (`__init__.py` carries only the docstring *"Placeholder. Will be populated by migration commits."*), so nothing imports it and it exposes nothing callable.

The caching that vaultlab actually does today lives next to the code that needs it, not here. The clearest example is the literature pipeline: `vaultlab.research.acquisition` resolves a deterministic on-disk path for each fetched PDF (`cache_path_for`) so a re-run recognizes an already-downloaded paper and short-circuits the download. That is a working cache; it simply has not been migrated into this package.

## Public surface

None. The package exports no symbols — `__init__.py` is a docstring-only placeholder, and no other module in the codebase imports from `vaultlab.cache`. Treat it as **reserved namespace**, not a usable API.

If you are looking for caching behavior that exists now, see `vaultlab.research.acquisition.cache_path_for` (the cached-PDF short-circuit in the acquisition waterfall), not this package.

## How it fits

Nothing reads from or writes to `vaultlab.cache` yet, so it sits outside the live pipeline. Its intended place is as a shared utility layer the capability subpackages (research acquisition, summarization, figure/recipe rendering, LLM-call results) could lean on instead of each rolling its own cache directory. When it is populated, the natural consumers are the same expensive, repeatable operations that already cache by hand today — PDF acquisition first among them.

## What it does NOT do

- It does **not** provide any cache, key derivation, eviction, or storage backend right now — it is an empty placeholder.
- It is **not** where vaultlab's current caching lives; that is `vaultlab.research.acquisition` (PDF short-circuit) and other per-package locations.
- It does **not** persist the project's knowledge or state — durable memory is the KB (`vaultlab.kb`), not a cache. A cache is for recomputable results, never the source of truth.
- It is **not** safe to depend on yet; importing it gets you a module with no functions or classes.

## Files

- `__init__.py` — placeholder module; docstring only, no exports. To be populated by later migration commits.

## See also

- [`docs/architecture.md`](../../../docs/architecture.md) — the architectural map that reserves this package for content-addressable caches.
- `vaultlab.research.acquisition` — where the working PDF cache (`cache_path_for`, cached-fetch short-circuit) lives today.
- [`vaultlab.kb`](../kb/) — the durable knowledge layer (distinct from a cache: the KB is the source of truth, a cache is disposable).
- `NEXT_STEPS.md` (repo root) — tracks not-yet-built pieces like this one.
