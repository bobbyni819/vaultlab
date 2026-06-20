---
title: Manuscript preflight
type: methodology
---

# Manuscript preflight

`vaultlab.manuscript.preflight` is the capstone pre-submission gate for reading a manuscript as a first-time reviewer. It combines the deterministic manuscript backbone with prepared reviewer-role passes and emits one severity-ranked fix queue.

## Backbone

`run_manuscript_preflight(...)` always runs without an LLM:

- `ClaimLedger.from_markdown(...).audit(...)` checks every tagged claim for figure, numeric, and Tier-3 citation support.
- `check_figure_text_consistency(...)` checks figure callouts, missing/cut figures, numeric mismatches, and conservative identity contradictions.
- Optional per-PNG `visual_qa_figure(..., run_vision=False)` runs when `run_visual_qa=True` and a figures directory is supplied.

Ledger, figure-text, and visual-QA problems are normalized into `FixItem(source, severity, message, where, fix)` records. Severities are ranked `error > warning > info`; visual QA maps `fail -> error`, `warn -> warning`, and `pass -> info`.

## Reviewer roles

The default reviewer passes are:

- `rigor_auditor`
- `methods_critic`
- `journal_reviewer`
- `expert_reviewer`
- `publication_guideline_compliance`
- `figure_reader`

Each role is prepared through `vaultlab.roles._invoke.prepare_audit(...)`. If no executor is supplied, no LLM is called; the report returns `PreparedRolePass` objects and an info fix item per prepared role so the caller can run the prompts later.

If an executor is injected, each prepared `AuditPrompt` is passed to it, successful mapping outputs are aggregated with `aggregate_audits(...)`, and role issues/concerns/checks are folded back into the same fix queue.

## Graceful degradation

Preflight never treats a missing role, missing journal YAML, unavailable KB context, absent executor, or failed role execution as fatal. It records a warning or info `FixItem` and keeps the deterministic backbone result available. This mirrors visual QA: the always-available deterministic checks are the gate; reviewer-role execution is advisory until a caller supplies an executor.
