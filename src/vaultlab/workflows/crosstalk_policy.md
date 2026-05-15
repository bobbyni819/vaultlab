# Crosstalk Invocation Policy (SPEC-E, sub-goal 2.4)

The `vaultlab.workflows.crosstalk` module ships a multi-agent
round-table (analyst → critic → synthesizer, up to 5 rounds). Today
the round-table fires on every caller that opts into it, which wastes
tokens on mechanical tasks where a single-pass call would do.

This skill documents the **policy** function that decides whether
crosstalk fires for a given task.

## Public surface

```python
from vaultlab.workflows.crosstalk_policy import (
    CrosstalkContext,
    should_invoke,
    skip_reason,
)

ctx = CrosstalkContext(task_kind="synthesis", n_evidence_sources=12)
if should_invoke(ctx):
    result = adversarial_arc_meeting(...)
else:
    result = single_pass_arc(...)
```

`should_invoke(ctx) -> bool` is pure and deterministic. Same input,
same output. No LLM calls. No I/O.

`skip_reason(ctx) -> str | None` mirrors `should_invoke`:

- Returns `None` when the round-table fires.
- Returns a short human-readable string when it skips. Embed in
  provenance manifests as `params.crosstalk_skip_reason` so audits can
  reconstruct why a given run was or wasn't a round-table.

## Decision rules

In order:

1. **Budget override.** If `ctx.n_rounds_budget > 0`, the caller has
   explicitly chosen to fire with that many rounds. The policy honours
   the budget regardless of `task_kind`.
2. **Fire kinds.** `task_kind` in `{synthesis, manuscript_draft,
   deep_think, journal_club}` → fire.
3. **Skip kinds.** `task_kind` in `{mechanical, extraction,
   single_paper_summary, audit_render}` → skip.
4. **Default.** Unknown task kinds fire (favor rigor over cost — per
   Bobby's `feedback_pipeline_run_through_tier_b` memory: crosstalk is
   part of the pipeline by default, not a gated luxury).

## Task kinds

| Kind                   | Default | Use when                                                |
|------------------------|---------|---------------------------------------------------------|
| `synthesis`            | FIRE    | Cross-evidence reasoning across N papers / datasets     |
| `manuscript_draft`     | FIRE    | Drafting a paper section that integrates evidence       |
| `deep_think`           | FIRE    | The classic analyst+expert+critic+synth cycle           |
| `journal_club`         | FIRE    | Deep analysis of a single paper for journal-club deck   |
| `mechanical`           | SKIP    | Format conversion, type coercion, no judgement needed   |
| `extraction`           | SKIP    | "Parse this PDF / pull these fields" — pure extraction  |
| `single_paper_summary` | SKIP    | One paper in → one summary out, no cross-paper logic    |
| `audit_render`         | SKIP    | Render a known-good audit object to HTML / MD / etc.    |

Add new kinds by extending the `TaskKind` literal and updating
`FIRE_KINDS` or `SKIP_KINDS` in `crosstalk_policy.py`. The forward-
compat rule (unknown kinds default to fire) means a new caller can
ship a new kind without breaking the world; the cost is a token spend
until the policy is updated.

## Provenance sidecar (cost tracking)

Every crosstalk-using entrypoint records the policy decision in its
provenance manifest's `params` block:

```json
{
  "params": {
    "crosstalk_invoked": true,
    "crosstalk_skip_reason": null,
    "crosstalk_task_kind": "synthesis",
    "crosstalk_n_rounds": 3
  }
}
```

When skipped:

```json
{
  "params": {
    "crosstalk_invoked": false,
    "crosstalk_skip_reason": "task_kind='mechanical' is mechanical/extraction; single-pass suffices",
    "crosstalk_task_kind": "mechanical",
    "crosstalk_n_rounds": 0
  }
}
```

Auditors can then ask "across the last 100 lit-arc runs, how many
fired crosstalk?" by scanning provenance sidecars, no LLM call
required.

## Wired call sites (sub-goal 2.4)

The gate is wired at the three highest-value entrypoints that already
opt into crosstalk via a `crosstalk_runner` knob:

1. **`vaultlab.research.lineage` — adversarial picker meeting.**
   Picker decides which top-N papers feed a `/lit-arc` summarisation
   pass. Default kind: `synthesis` (cross-paper reasoning over
   candidate abstracts).
2. **`vaultlab.research.lineage` — adversarial arc meeting.**
   Arc writes the 3-paragraph history → development → SOTA narrative.
   Default kind: `manuscript_draft` (this becomes the lineage doc).
3. **`vaultlab.slides.deck` — adversarial deck-plan meeting.**
   Plans the journal-club slide deck. Default kind: `journal_club`.

The `rigor_audit` call inside `vaultlab.slides.deck` runs a single
auditor role (no round-table) so the policy gate doesn't apply — it
already IS a single-pass call.

## Followups

- The `n_evidence_sources` and `has_human_review_after` fields on
  `CrosstalkContext` are plumbed but not consulted yet. Future
  calibration could route `n_evidence_sources < 3` to single-pass
  even for synthesis kinds.
- A future revision could expose a per-call override (e.g. an
  environment variable `VAULTLAB_CROSSTALK_FORCE=skip`) for token-
  cost emergencies.
- The deep-think workflow (`vaultlab.workflows.deep_think`) builds
  *plans* rather than directly invoking the crosstalk meeting helpers;
  the policy could be wired there too once that path actually fires
  the round-table at runtime instead of returning a plan dict.
