# spec-d-kb-setup-primitive

**Slug:** `spec-d-kb-setup-primitive`
**Status:** completed
**North-star sub-goal:** 2.3 (SPEC-D — KB setup + lint primitives)
**Plan file:** `.claude/goals/vaultlab-north-star-plan.md`
**Pairs with:** sub-goal 2.2 (`spec-c-kb-retrieval-upgrade`)

## Outcome

Promote `scaffold_kb` and `lint_kb` (already implemented under
`src/vaultlab/kb/setup.py`) to the `vaultlab.kb` public surface so a new
KB can be created and validated in code without reaching into the
submodule path. The north-star plan calls out these as ergonomic short
names (`setup`, `lint`); we export both the canonical SPEC-D names and
the short aliases so external callers can pick whichever reads better in
their codebase.

## Discovery — what was already there

`scaffold_kb` + `lint_kb` had already shipped in `src/vaultlab/kb/setup.py`
(321 lines, full SPEC-D semantics — canonical folder set, domain
extensions registry, severity-ranked `LintFinding` / `LintReport`, naming
convention check, stale-index detection, render_markdown audit doc).
Tests in `tests/test_vaultlab_kb/test_setup.py` already covered 18
cases. The only missing piece for sub-goal 2.3 was the **public-API
contract** — the names weren't exposed at the package level.

This is consistent with sub-goal 2.2's note in
`spec-c-kb-retrieval-upgrade.md`:

> CLI wiring (success criterion #4 — `bobby-kb index --kb <name>`
> calling the new builder) is deferred to sub-goal 2.3
> (`spec-d-kb-setup-primitive`) which already plans to refresh the CLI
> surface together with `setup`/`lint`.

So 2.3 = the public-surface promotion, not a re-implementation.

## Decisions

- **Dual names** in `vaultlab.kb.__init__`. Canonical
  `scaffold_kb` / `lint_kb` / `LintFinding` carry the full SPEC-D
  semantics; ergonomic `setup` / `lint` / `LintIssue` aliases are bound
  via `setup = scaffold_kb` etc. so there is one source of truth and
  the aliases can never drift. Test
  `test_aliases_point_to_canonical_objects` enforces the identity
  contract.
- **No CLI wiring.** `src/vaultlab/cli/kb/__init__.py` is still a
  placeholder; the top-level CLI dispatcher is a minimal hand-rolled
  switch, not click. Documented as a followup. (`vaultlab init` and
  `vaultlab demo` are the only KB-adjacent CLI entries today.)
- **No spec-doc template duplication.** `scaffold_kb` writes
  `START_HERE.md` + `_Index.md` + `_Catalog.md` + `_Log.md` (the
  Bobby-canonical 4 files), not a `_KB-Architecture-Spec.md`. Kept the
  existing template set rather than introducing a 5th file — the spec
  doc the brief mentions is the human-readable
  `tools/knowledge-base-specification.md`, which is referenced from
  `setup.py`'s module docstring.
- **No refactor of `setup.py`.** The 321-line implementation is sound;
  rewriting it would burn tokens without changing behavior. Just added
  the alias layer + a 6-test public-API surface test file.

## Files touched

- `src/vaultlab/kb/__init__.py` — added imports + 3 aliases + updated
  module docstring + expanded `__all__`.
- `tests/test_vaultlab_kb/test_public_api.py` (new) — 6 tests covering
  the SPEC-D public-API contract (canonical names, short aliases, alias
  identity, scaffold via alias, lint via alias, LintIssue ↔ LintFinding
  isinstance check).
- `.claude/goals/spec-d-kb-setup-primitive.md` (this file).

## Test counts

- `tests/test_vaultlab_kb/test_setup.py` — 18 passed (pre-existing).
- `tests/test_vaultlab_kb/test_public_api.py` — 6 passed (new).
- Full kb suite — 274 passed (up from 268).
- Invariants suite — 8/0 (unchanged).

## EVIDENCE

Populated on completion — see git commit hash on commit landing.
