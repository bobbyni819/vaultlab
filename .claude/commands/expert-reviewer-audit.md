---
name: expert-reviewer-audit
description: Audit a vaultlab artifact from a domain-expert reviewer's perspective — would a senior reviewer sign off on this for a grant or proposal? for a paper or report? what questions should you expect from an expert reader? Outputs structured JSON verdict + concerns + expected expert questions grounded in the project's KB context and decisions log.
arguments: <file-path-or-artifact>
---

# /expert-reviewer-audit <file-or-artifact>

> *"Run this through expert eyes — would a senior peer reviewer sign off on it?"*

Invokes the `expert_reviewer` role on the named artifact. Produces a structured readiness verdict (would-sign-off-for-grant + would-sign-off-for-paper) plus a list of anticipated expert questions, grounded in the project's specific context (decisions log, established findings, methodology commitments, prior audit history).

Works for solo researchers, postdocs, industry researchers, lab heads — anyone facing peer review, grant review, conference review, or expert internal scrutiny. Not anchored in academic-PI structure.

## Lineage

Lifts:
- **expert_reviewer role** from `vaultlab.roles.expert_reviewer` (own work)
- **eLife two-axis rubric** (significance × evidence) — canonical verdict schema
- **NIH grant-review scoring conventions** — verdict mapping (would-sign-off bar)
- **gstack review-checklist convention** (Garry Tan) — explicit reviewer-question generation
- **Conference review conventions** (NeurIPS, ICML, etc.) — reviewer-question discipline

## Pre-flight checklist

1. Resolve KB root + project config
2. Load project context: dossier (when SPEC-N ships), decisions log, established findings, prior audits
3. **Read the artifact in full** — semantic reading per CLAUDE.md commitment #2
4. State-aware preflight: search `Output/expert-reviewer-audit-*` for prior audits of this artifact — if recent (<7d), default to `--variant`
5. Refuse-to-proceed if KB context preamble unavailable (per CLAUDE.md commitment #7) — the expert reviewer is project-context-dependent; running it without context produces generic boilerplate

## Execution

### Step 1 — Load project context

The expert reviewer is highly context-dependent — generic expert-style audit produces generic concerns. Pull the full layered context per SPEC-C / the researcher-pathway protocol:

- Project dossier (when SPEC-N ships) — surfaces project-specific reviewer concerns
- decisions-log.md — what methodology has the project committed to?
- Established findings (Wiki/Concepts/, audit reports) — what's already validated?
- Recent outputs (last 30 days) — what's the current arc?
- Field-convention surface from the dossier

### Step 2 — Run the role

Invoke the `expert_reviewer` role with the artifact + full context. The role applies its 8 audit checks (statistical power, replication, generalization, methodology alignment, hedging, expected questions, strengths, verdict).

### Step 3 — Save + surface

Write the JSON + markdown rendering to `Output/Reports/expert-reviewer-audit-<artifact-slug>-<date>.md`.

Surface to the user:
- Both verdicts (grant + paper)
- Significance + evidence axes
- Top 3 concerns by severity
- The 3-5 anticipated expert questions in priority order
- Path to the full audit doc

### Step 4 — Practice prep

The expert_questions list is genuinely useful for the user's actual review prep. Surface them prominently in the conversation: *"prep for these 4 questions before submission: [...]"*. Optionally offer to generate a flashcard sidecar (per Phase 7.7 practice script + flashcard generator).

## What this is NOT

- Not a journal-style check (use `/journal-reviewer-audit`).
- Not a statistical rigor check (use `methods_critic`).
- Not a generic checklist — the value is in the project-specific anticipated questions.

## See also

- `vaultlab/src/vaultlab/roles/expert_reviewer/{prompt.md,metadata.yaml}`
- `vaultlab/Sources/Notes/SPEC-meta-agent-roles-2026-05-07.md`
- `vaultlab/Sources/Notes/conceptual-deep-dive-project-context-2026-05-08.md` — why project context matters for this role
