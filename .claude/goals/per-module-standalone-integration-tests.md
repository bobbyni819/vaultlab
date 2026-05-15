# Sub-goal: Per-module standalone integration tests

_Created: 2026-05-15_
_Parent goal: `.claude/goals/vaultlab-north-star.md` (Criterion #3 — "plug-in companion")_
_Status: COMPLETE_

## Outcome

9 new standalone integration tests (1 per public-API module; figures
gets 2 tests). Each exercises a primary entrypoint from a fresh
`tmp_path` fixture with `HOME` / `USERPROFILE` / `XDG_CONFIG_HOME`
isolated. External APIs are mocked. All 9 pass; the invariant suite
still passes 8/0.

```
$ pytest tests/test_vaultlab_*/test_standalone.py -v
9 passed in 0.46s
```

## Modules covered (8/8)

| Module | Entrypoint exercised | Test file |
|---|---|---|
| `vaultlab.research` | `ResearchClient.search` (with mocked `unified_search`) | `tests/test_vaultlab_research/test_standalone.py` |
| `vaultlab.figures` | `FigureContract` + `validate_contract`; `acquire_figures` (empty-DOI fast-path) | `tests/test_vaultlab_figures/test_standalone.py` |
| `vaultlab.citations` | `audit_file` on a tmp_path markdown file (extraction-only, no `research_client`) | `tests/test_vaultlab_citations/test_standalone.py` |
| `vaultlab.slides` | `build_from_plan` writing a real `.pptx` from a 2-slide dict plan | `tests/test_vaultlab_slides/test_standalone.py` |
| `vaultlab.manuscript` | `polish.write_polish_report` writing a report + provenance receipts | `tests/test_vaultlab_manuscript/test_standalone.py` |
| `vaultlab.kb` | `setup.scaffold_kb` + `semantic_search.search` round-trip | `tests/test_vaultlab_kb/test_standalone.py` |
| `vaultlab.workflows` | `plan_synthesis` returning a `WorkflowPlan` against a fresh KB skeleton | `tests/test_vaultlab_workflows/test_standalone.py` |
| `vaultlab.report` | `write_report` producing a self-contained `.html` file | `tests/test_vaultlab_report/test_standalone.py` |

## Decisions and findings

### What gets mocked

- **`vaultlab.research`** — `unified_search` is monkeypatched to return a
  hard-coded `Paper`. Rationale: the public surface (`ResearchClient` +
  `Paper` round-trip) is what we want to certify is plug-in usable; the
  HTTP layer is not vaultlab's responsibility. We also write a tiny
  `research_apis.json` with one fake NCBI key into `tmp_path` and point
  `VAULTLAB_RESEARCH_API_CONFIG` at it, then call
  `vaultlab.research.config.reload()` to clear the module-level cache.
- **`vaultlab.citations`** — no mock. Calling `audit_file` without a
  `research_client` runs extraction-only, which is purely text-based.
  This proves the extraction half of the citations pipeline is plug-in
  usable from any fresh state.
- **`vaultlab.figures` (acquire_figures)** — no mock. The empty-DOI
  fast-path returns `source="unavailable"` immediately, which is the
  documented contract. No network call ever happens.
- **`vaultlab.manuscript`** — no mock. The polish checkers
  (`check_sentence_length`, `check_us_spelling`) are pure-Python; the
  LLM-driven 12-step workflow is not exercised because
  `write_polish_report` is the artifact-producing entrypoint and that
  one does not call an LLM.
- **`vaultlab.slides`, `vaultlab.kb`, `vaultlab.workflows`,
  `vaultlab.report`** — no mocks needed. These are pure-Python /
  filesystem operations on fresh `tmp_path`.

### What got isolated

Each test monkeypatches `HOME`, `USERPROFILE`, and `XDG_CONFIG_HOME` to
`tmp_path` so that even if the underlying code reaches for
`~/.config/`, it lands inside the temp dir.

### Module-init quirks observed (NOT BLOCKED, just noted)

- **`vaultlab.kb.__init__.py`** is still a one-line placeholder
  ("Will be populated by migration commits."). The real public
  entrypoints live in submodules (`vaultlab.kb.setup`,
  `vaultlab.kb.semantic_search`). The test imports the submodules
  directly — when the package `__init__` is backfilled the imports
  can be flattened. This is consistent with the migration spec; not a
  bug, not a blocker.
- **`vaultlab.figures.__init__.py`** re-exports only the acquisition
  layer (`Figure`, `FigureAcquisitionResult`, `acquire_figures`,
  `acquire_figures_for_corpus`, `figure_cache_dir`). The
  `FigureContract` API lives in `vaultlab.figures.contract` and is
  documented in `contract.md`. The test imports `FigureContract`
  directly from the submodule. If we want a single front-door import
  surface, the `__init__` could re-export `FigureContract` /
  `validate_contract` / `apply_rcparams` / `triple_export` — but
  that's a separate cosmetic decision and not in this sub-goal's scope.
- **`vaultlab.research.config`** caches the loaded config at
  module-level. Tests that change the config path must call
  `vaultlab.research.config.reload()` first. We do this in the research
  standalone test.

## Modules NOT covered

None blocked. All 8 enumerated modules got a passing standalone test.

## Constraints honored

- No source file was modified — only test files and this goal doc were
  added.
- `src/vaultlab/research/full_reader.py` and
  `src/vaultlab/figures/contract.py` (the two files other agents are
  touching) were READ from but never edited.
- Git hooks were not skipped.

## Evidence

- 9 new tests in `tests/test_vaultlab_*/test_standalone.py`
- Test run: `pytest tests/test_vaultlab_*/test_standalone.py -v` →
  `9 passed in 0.46s`
- Invariant suite still green: `pytest tests/test_vaultlab_invariants/ -q`
  → `8 passed in 1.32s`
