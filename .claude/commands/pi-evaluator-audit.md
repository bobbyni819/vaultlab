---
name: pi-evaluator-audit
description: Audit a vaultlab artifact from a PI's perspective — would I sign off on this for a grant submission? for a paper submission? what committee questions should you expect? Outputs structured JSON verdict + concerns + expected-questions grounded in the project's KB context and decisions log.
arguments: <file-path-or-artifact>
---

# /pi-evaluator-audit <file-or-artifact>

> *"Run this through PI eyes — would my advisor sign off on it?"*

Invokes the `pi_evaluator` role on the named artifact. Produces a structured PI-readiness verdict (would-sign-off-for-grant + would-sign-off-for-paper) plus a list of anticipated committee/reviewer questions, grounded in the project's specific context (decisions log, established findings, methodology commitments, prior audit history).

## Lineage

Lifts:
- **pi_evaluator role** from `vaultlab.roles.pi_evaluator` (own work)
- **eLife two-axis rubric** (significance × evidence) — canonical verdict schema
- **NIH grant-review scoring conventions** — verdict mapping (would-sign-off bar)
- **gstack review-checklist convention** (Garry Tan) — explicit committee-question generation

## Pre-flight checklist

1. Resolve KB root + project config
2. Load project context: dossier (when SPEC-N ships), decisions log, established findings, prior audits
3. **Read the artifact in full** — semantic reading per CLAUDE.md commitment #2
4. State-aware preflight: search `Output/pi-evaluator-audit-*` for prior audits of this artifact — if recent (<7d), default to `--variant`
5. Refuse-to-proceed if KB context preamble unavailable (per CLAUDE.md commitment #7) — the PI evaluator is project-context-dependent; running it without context produces generic boilerplate

## Execution

### Step 1 — Load project context

The PI evaluator is highly context-dependent — generic PI-style audit produces generic concerns. Pull the full layered context per SPEC-C / the researcher-pathway protocol:

- Project dossier (when SPEC-N ships) — section 8 surfaces project-specific PI concerns
- decisions-log.md — what methodology has the project committed to?
- Established findings (Wiki/Concepts/, audit reports) — what's already validated?
- Recent outputs (last 30 days) — what's the current arc?
- Lab-convention surface from the dossier

### Step 2 — Run the role

Invoke the `pi_evaluator` role with the artifact + full context. The role applies its 8 audit checks (statistical power, replication, cohort generalization, methodology alignment, hedging discipline, anticipated questions, strengths, verdict).

### Step 3 — Save + surface

Write the JSON + markdown rendering to `Output/Reports/pi-evaluator-audit-<artifact-slug>-<date>.md`.

Surface to the user:
- Both verdicts (grant + paper)
- Significance + evidence axes
- Top 3 concerns by severity
- The 3-5 anticipated questions in priority order
- Path to the full audit doc

### Step 4 — Practice prep

The expected_questions list is genuinely useful for the user's actual committee/reviewer prep. Surface them prominently in the conversation: *"prep for these 4 questions before your committee meeting: [...]"*. Optionally offer to generate a flashcard sidecar (per Phase 7.7 practice script + flashcard generator).

## What this is NOT

- Not a journal-style check (use `/journal-reviewer-audit`).
- Not a statistical rigor check (use `methods_critic`).
- Not a generic checklist — the value is in the project-specific anticipated questions.

## See also

- `vaultlab/src/vaultlab/roles/pi_evaluator/{prompt.md,metadata.yaml}`
- `vaultlab/Sources/Notes/SPEC-meta-agent-roles-2026-05-07.md`
- `vaultlab/Sources/Notes/conceptual-deep-dive-project-context-2026-05-08.md` — why project context matters for this role
