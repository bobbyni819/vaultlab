# SPEC-F sub-goal 2.5 — Task-Weight Dispatch

Status: COMPLETE 2026-05-15

## Summary

Adds `vaultlab.workflows.task_weight` — a `classify(task) → Weight`
function plus a configurable `Weight → model_id` mapping. Lightweight
tasks (format conversion, extraction) route to Haiku, single-paper
work to Sonnet, and heavy synthesis / manuscript / response work to
Opus. Cost-conscious users can override the mapping via
`~/.config/vaultlab/dispatch.json` (or the `VAULTLAB_DISPATCH_CONFIG`
environment variable for tests and CI).

This module is intentionally pure / side-effect free — no LLM calls,
no network, no I/O outside reading a single JSON config. It returns
plain model id strings; the caller wires whichever Anthropic SDK
helper they use.

## Module

`src/vaultlab/workflows/task_weight.py`

- `Weight = Literal["light", "medium", "heavy"]`
- `@dataclass TaskSpec` — `kind`, `n_inputs`, `output_kind`,
  `requires_synthesis`.
- `classify(task)` — pure deterministic; see SKILL.md for the
  decision rules and matrix.
- `model_for_weight(weight, config_path=None)` — resolves
  `model_id`, honoring user overrides; falls back to defaults on
  malformed JSON / IO error so the dispatcher never crashes the
  caller.
- `model_for_task(task, config_path=None)` — sugar over the two.
- `WEIGHT_TO_DEFAULT_MODEL` — exported defaults:
  - `light`  → `claude-haiku-4-5`
  - `medium` → `claude-sonnet-4-6`
  - `heavy`  → `claude-opus-4-7`

Symbols are re-exported from `vaultlab.workflows` for convenience:

```python
from vaultlab.workflows import (
    TaskSpec, Weight, WEIGHT_TO_DEFAULT_MODEL,
    classify, model_for_weight, model_for_task,
)
```

## Decision rules (from SKILL.md)

| Kind                                              | Single input | n > 5    | requires_synthesis |
|---------------------------------------------------|--------------|----------|---------------------|
| `extract` / `convert` / `format` / `render`       | `light`      | `light`  | `heavy`             |
| `summarize` / `single_paper_read` / `abstract_only` | `medium`   | `heavy`  | `heavy`             |
| `polish` / `respond` / `manuscript_draft` / `deep_think` / `synthesize` / `synthesis` | `heavy` | `heavy` | `heavy` |
| Unknown kind                                       | `medium`    | `heavy`  | `heavy`             |

Decision order in `classify`:

1. `requires_synthesis=True` → `heavy`
2. Heavy-kind set membership → `heavy`
3. Light-kind set membership → `light`
4. `n_inputs > 5` → `heavy`
5. Medium-kind with `n_inputs == 1` → `medium`
6. Otherwise → `medium` (safe default)

## SKILL.md

`src/vaultlab/workflows/task_weight.md` — task-kind matrix, override
mechanism, provenance integration example, list of wired
entrypoints.

## Example config

`examples/configs/dispatch.json` — starter file matching the defaults.
A test (`test_examples_dispatch_json_matches_defaults`) keeps the
example in sync with `WEIGHT_TO_DEFAULT_MODEL`.

## Tests

`tests/test_vaultlab_workflows/test_task_weight.py` — 37 tests:

- Heavy-kind matrix (6 parametrized)
- Light-kind matrix (4) + light-kind small-batch stays light (4)
- Medium-kind matrix (3)
- Batch upgrade rule: `n_inputs > 5` → heavy (3 parametrized);
  threshold-of-5 stays medium (1)
- `requires_synthesis` forces heavy (2)
- Unknown kind defaults to medium (1) + batches still upgrade (1)
- Default mapping with no config (1) + default-constant matches (1)
- Full config override (1) + partial keeps defaults (1)
- Unknown keys ignored (1) + malformed JSON falls back (1) +
  non-object root falls back (1)
- `VAULTLAB_DISPATCH_CONFIG` env-var path resolution (1)
- `model_for_task` chains correctly (2)
- Re-exports from `vaultlab.workflows` (1)
- `examples/configs/dispatch.json` matches defaults (1)

Full suite: `pytest tests/test_vaultlab_workflows/` → 141 passed.
Invariants: `pytest tests/test_vaultlab_invariants/` → 8/0 (unchanged).

## Wired entrypoint

`vaultlab.research.full_reader.build_paper_reader` —

- Added optional `weight: Weight | None = None` kwarg.
- When `None`, auto-classifies the task as `TaskSpec(kind="single_paper_read", n_inputs=1)` → `medium`.
- Resolved model id is recorded in the provenance manifest:
  - `ProvenanceRecord.model = resolved_model`
  - `params["weight"] = resolved_weight`
  - `params["model"] = resolved_model`
- All 15 existing `test_full_reader.py` tests continue to pass — the
  wiring is non-breaking.

Chosen because it already writes provenance via `write_receipts`,
has a clear single-task semantic (one paper → one reader), and is
the most-used research entrypoint touched in sub-goal 2.1
(nature-reader absorption). Other entrypoints (manuscript polish,
respond, deep-think, batched_reader when it lands) can be wired in
follow-ups using the same pattern documented in `task_weight.md`.

## Files changed

- `src/vaultlab/workflows/task_weight.py` — new (179 LOC)
- `src/vaultlab/workflows/task_weight.md` — new (SKILL.md)
- `src/vaultlab/workflows/__init__.py` — re-exports
- `examples/configs/dispatch.json` — new starter config
- `tests/test_vaultlab_workflows/test_task_weight.py` — new (37 tests)
- `src/vaultlab/research/full_reader.py` — wiring + provenance fields
- `.claude/goals/spec-f-task-weight-dispatch.md` — this file

## Constraints honored

- Stayed inside `src/vaultlab/workflows/`,
  `tests/test_vaultlab_workflows/`, `examples/configs/`, and the
  single wired entrypoint (`full_reader.py`).
- Did NOT touch `src/vaultlab/analysis/` or `src/vaultlab/report/`.
- Used the exact model IDs from CLAUDE.md: `claude-haiku-4-5`,
  `claude-sonnet-4-6`, `claude-opus-4-7`.
- Renamed module to `task_weight.py` (not `dispatch.py`) to avoid
  collision with the existing `vaultlab.report.dispatch`.
