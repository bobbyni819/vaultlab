---
title: Manuscript state machine
type: methodology
---

# Manuscript state machine

`vaultlab.manuscript.state` is the durable "where is this manuscript?" dashboard for the figure-to-manuscript pipeline. It does not introduce new checks. It reuses `run_manuscript_preflight(...)` for the deterministic backbone and prepared reviewer passes, and `run_citation_gate(...)` for citation-tier status and promotion actions.

## Lifecycle ladder

The state machine reports five advancement gates over six ordered stages:

- `DRAFTING` - default stage before any gate passes.
- `EVIDENCE_LINKED` - every quantitative ledger claim has at least one numeric link and at least one figure link.
- `FIGURE_SYNCED` - figure-text consistency passes.
- `CITATION_TIERED` - every gated citation reaches Tier 3.
- `REVIEWER_AUDITED` - the preflight queue has no error-severity items and reviewer-role passes have actually been executed with an acceptable aggregate verdict.
- `SUBMISSION_READY` - every prior advancement gate passes.

`current_stage` is strict: the ladder stops at the first failing gate. A manuscript with linked evidence and synced figures but unexecuted reviewer roles stays at `CITATION_TIERED`, with reviewer execution listed as the blocker.

## Gate derivation

- Evidence blockers come from claim-ledger audit problems about missing numeric or figure links.
- Figure blockers come from `preflight.consistency.problems`.
- Citation blockers come from `run_citation_gate(...)` as `<citation_key> needs Tier-3`.
- Reviewer blockers come from error-severity preflight fix items, missing execution, missing aggregation, or an unacceptable aggregate reviewer verdict.
- Submission blockers summarize any lower gate blockers.

The unified `fix_queue` is `preflight.fix_queue` plus citation-gate promotion actions converted to `FixItem(source="citation_gate", severity="error", ...)`, then ranked by severity.

## Persistence

`ManuscriptState.to_json(path)` writes the dashboard atomically. `read_json(path)` restores stages and gates by enum value and reconstructs the persisted `FixItem` queue. `to_markdown()` renders the same state as a human-readable checklist with blockers and ranked fixes.
