---
name: adoption-evaluator-audit
description: Audit a vaultlab user-facing artifact (README, QUICKSTART, slash command spec, getting-started doc) from a fresh new user's perspective — what friction would they hit on their first 30 minutes? Where would they bounce off? Outputs structured JSON friction-list + missing recovery paths + strengths.
arguments: <file-path-or-artifact>
---

# /adoption-evaluator-audit <file-or-artifact>

> *"Imagine a labmate on a fresh laptop. Where would they get stuck?"*

Invokes the `adoption_evaluator` role on the named artifact. Predicts new-user friction points, surfaces missing recovery paths, and outputs a structured friction-list with severity ranking. Ground truth: vaultlab's `friction-findings-from-metabolism-run-2026-05-05.md` and the `conceptual-deep-dive-new-user-onboarding-2026-05-08.md` walkthrough.

## Lineage

Lifts:
- **adoption_evaluator role** from `vaultlab.roles.adoption_evaluator` (own work)
- **OpenClaw / gstack adoption pattern** — minimal-code, LLM-handles-per-machine-adaptation; predict where adaptation gaps surface
- **virtual-lab adoption notes** — friction-pattern catalog
- **friction-findings-from-metabolism-run** (own work) — authoritative reference for known patterns

## Pre-flight checklist

1. Resolve KB root + project config
2. Load `Sources/Notes/friction-findings-from-metabolism-run-2026-05-05.md` (or current friction-findings doc) as authoritative reference
3. **Read the artifact in full** — semantic reading per CLAUDE.md commitment #2
4. State-aware preflight: search `Output/adoption-evaluator-audit-*` for prior audits — if recent (<7d), default to `--variant`

## Execution

### Step 1 — Load adoption-context

Read:
- The artifact (README, QUICKSTART, slash command spec, etc.)
- friction-findings doc as authoritative reference
- Per-machine adaptation patterns: `vaultlab/scripts/bootstrap.{sh,ps1}`, `vaultlab/src/vaultlab/cli/__init__.py` (for `claude-setup`)
- Path discovery patterns: `vaultlab/src/vaultlab/context/locations.py`

### Step 2 — Run the role

Invoke the `adoption_evaluator` role. The role applies 7 friction-detection passes (missing dependencies, assumed knowledge, hard-coded paths, interactive prompts, sequence pitfalls, permission/path issues, recovery paths) and outputs structured JSON.

### Step 3 — Save + surface

Write the JSON + markdown rendering to `Output/Reports/adoption-evaluator-audit-<artifact-slug>-<date>.md`.

Surface to the user:
- The verdict (ship → ship_with_revisions → needs_minor_revision → needs_major_revision → bounce_risk)
- Top 3 frictions by severity, including the `what_they_see` field (concrete user-eye view)
- Any `recovery_paths_missing` items
- Path to full audit doc

### Step 4 — Recommended fixes

Each friction includes a `fix` field. Surface a one-line summary of recommended fixes in priority order: *"Top fix: add explicit `must run vaultlab claude-setup before slash commands work` between Step 2 and Step 5."*

## What this is NOT

- Not a journal-style audit (use `/journal-reviewer-audit`).
- Not a PI-readiness check (use `/pi-evaluator-audit`).
- Not a runtime test (it's prose-level prediction). Run a real-user simulation separately for ground truth.

## See also

- `vaultlab/src/vaultlab/roles/adoption_evaluator/{prompt.md,metadata.yaml}`
- `vaultlab/Sources/Notes/SPEC-meta-agent-roles-2026-05-07.md`
- `vaultlab/Sources/Notes/conceptual-deep-dive-new-user-onboarding-2026-05-08.md`
- `vaultlab/Sources/Notes/friction-findings-from-metabolism-run-2026-05-05.md`
