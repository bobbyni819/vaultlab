# SPEC-E sub-goal 2.4 — Crosstalk Invocation Policy

Status: COMPLETE 2026-05-15

## Summary

Adds `vaultlab.workflows.crosstalk_policy` with a deterministic
`should_invoke(CrosstalkContext) -> bool` gate function and the
companion `skip_reason()` helper. Wires the gate into the three
highest-value entrypoints that currently invoke crosstalk
unconditionally when `crosstalk_runner` is supplied. Every wired
site records the policy decision in its provenance manifest so
audits can reconstruct why a given run was or wasn't a round-table.

## Module

`src/vaultlab/workflows/crosstalk_policy.py`

- `TaskKind = Literal[...]` — 8 known kinds (4 fire, 4 skip).
- `FIRE_KINDS` / `SKIP_KINDS` — frozen sets for fast membership.
- `@dataclass CrosstalkContext` — `task_kind` (default `synthesis`),
  `n_evidence_sources`, `n_rounds_budget`, `has_human_review_after`.
- `should_invoke(ctx)` — pure deterministic; see SKILL.md for the
  full decision table.
- `skip_reason(ctx)` — `None` when firing, short string when skipping.

Also re-exported from `vaultlab.workflows` for convenience:

```python
from vaultlab.workflows import CrosstalkContext, should_invoke, skip_reason
```

## SKILL.md

`src/vaultlab/workflows/crosstalk_policy.md` — decision rules,
TaskKind table, provenance sidecar shape, call-site map, followups.

## Tests

`tests/test_vaultlab_workflows/test_crosstalk_policy.py` — 19 tests:

- Each of the 4 FIRE kinds → True.
- Each of the 4 SKIP kinds → False.
- Budget override (`n_rounds_budget > 0`) beats kind, including
  unknown kinds.
- Zero / negative budget does NOT trigger the override.
- Unknown task kind defaults to True (forward-compat).
- Empty / default context fires.
- Context attribute defaults / optional fields plumb through.
- `skip_reason` returns human-readable string when skipping, None
  when firing.
- Determinism (same input → same output across 20 calls).

## Wired call sites

1. **`vaultlab.research.lineage.run_lit_arc` (picker meeting)** —
   `task_kind="synthesis"`, `n_evidence_sources=len(candidates)`,
   `n_rounds_budget=crosstalk_n_rounds`. Recorded in lineage_arc
   provenance manifest as `crosstalk_picker_invoked`,
   `crosstalk_picker_skip_reason`, `crosstalk_picker_task_kind`.

2. **`vaultlab.research.lineage.run_lit_arc` (arc meeting)** —
   `task_kind="manuscript_draft"`, `n_evidence_sources=len(summaries)`,
   `n_rounds_budget=crosstalk_n_rounds`. Recorded as
   `crosstalk_arc_invoked`, `crosstalk_arc_skip_reason`,
   `crosstalk_arc_task_kind`.

3. **`vaultlab.slides.deck.build_deck_from_lineage_result`** —
   `task_kind="journal_club"`, `n_evidence_sources=len(summaries)`,
   `n_rounds_budget=crosstalk_n_rounds`. Recorded in deck provenance
   manifest as `crosstalk_invoked`, `crosstalk_skip_reason`,
   `crosstalk_task_kind`, `crosstalk_n_rounds`.

## Decisions

- The gate **records** the decision but doesn't yet **branch** to a
  separate single-pass code path. All three current call sites already
  guard the crosstalk path with `picker_mode == "adversarial" and
  crosstalk_runner is not None` (or equivalent), so the actual control
  flow lives in those mode flags. The policy adds an auditable
  reason-code beside that decision and a programmatic hook future
  refactors can use to short-circuit without changing every entrypoint.
  All three call sites pass `n_rounds_budget=crosstalk_n_rounds`,
  which means today's behaviour (already opted-in) always invokes
  crosstalk — the policy decision is `True` and the audit trail
  records that.
- The `rigor_audit` call inside `vaultlab.slides.deck` is a single-
  auditor `INDIVIDUAL` meeting — not a round-table — so the policy
  gate doesn't apply.
- The `vaultlab.workflows.deep_think` builders return `WorkflowPlan`
  objects rather than firing the meeting at runtime, so the policy
  gate is not wired there in this pass. When that path actually
  invokes the round-table directly (vs returning a plan dict), the
  gate should be added.

## Followups

- Add a per-call override (e.g. env var `VAULTLAB_CROSSTALK_FORCE`)
  for token-cost emergencies.
- Calibrate the policy on `n_evidence_sources` — single-paper
  synthesis tasks might not need the round-table.
- Wire the gate into the deep-think workflow once it directly
  invokes the round-table at runtime.
- Add a one-shot CLI: `vaultlab crosstalk explain --kind synthesis
  --budget 0` that prints the decision + reason for an arbitrary
  context, so script authors can debug without writing a REPL.

## Verification

```
pytest tests/test_vaultlab_workflows/  -> 104 passed (was 85 + 19 new)
pytest tests/test_vaultlab_invariants/ -> 8 passed (unchanged)
pytest tests/test_vaultlab_research/ tests/test_vaultlab_slides/ -> 827 passed
```
