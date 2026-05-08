---
name: journal-reviewer-audit
description: Audit a vaultlab artifact (deck, concept doc, manuscript section, lit-arc) the way a Cell-family or Nature reviewer would. Outputs structured JSON verdict + issues + strengths grounded in the project's target journal guidelines.
arguments: <file-path-or-artifact>
---

# /journal-reviewer-audit <file-or-artifact>

> *"Audit this manuscript draft as if you were a Cell Systems reviewer."*

Invokes the `journal_reviewer` role on the named artifact. Produces a structured journal-style audit report grounded in the target journal's guidelines (loaded from `External/journal-guidelines/`) and the eLife two-axis rubric (verdict + evidence_axis).

## Lineage

Lifts:
- **journal_reviewer role** from `vaultlab.roles.journal_reviewer` (own work, anchored on Cell Press editorial policy + Nature peer-review guide + eLife assessments)
- **eLife two-axis rubric** (significance × evidence) — from `elifesciences.org/about/elife-assessments`; canonical verdict schema across all target journals
- **Severity rubric** (fail/major/minor/style) — scientific peer-review convention
- **Structured-JSON output** — virtual-lab (Swanson Nature 2025) drift-prevention discipline

## Pre-flight checklist

1. Resolve KB root + project config; verify `target_journal` is set (e.g., `cell-systems`)
2. Load journal guidelines from `External/journal-guidelines/<target_journal>.md` + `_common.yaml`
3. **Read the artifact in full** — not skim. Semantic reading per CLAUDE.md commitment #2.
4. State-aware preflight: search `Output/journal-reviewer-audit-*` for prior audits of this same artifact — if recent (<7d), surface and default to `--variant` (audit what's new since)
5. Refuse-to-proceed if KB context preamble unavailable (per CLAUDE.md commitment #7)

## Execution

### Step 1 — Load context

Read:
- The artifact (deck markdown, concept doc, manuscript section)
- The project's KB context preamble (project dossier when SPEC-N ships, decisions log, recent outputs)
- The target journal's guidelines from `External/journal-guidelines/<journal>.md`
- The accessibility guidelines from `External/journal-guidelines/accessibility-and-color.md`

### Step 2 — Run the role

Invoke the `journal_reviewer` role with the artifact + context as the user prompt. The role's TASKS contract walks 7 audit checks (claim hedging, citation style, abstract-body alignment, figure captions, abbreviations, methodology-results-claim chain, strengths) and outputs structured JSON.

### Step 3 — Save the audit

Write the JSON output (and a human-readable markdown rendering of it) to `Output/Reports/journal-reviewer-audit-<artifact-slug>-<date>.md`. Receipts go alongside.

### Step 4 — Surface verdict inline

Surface to the user: the verdict (ship / ship_with_revisions / needs_minor_revision / needs_major_revision / reject), the evidence axis (exceptional → inadequate), the count of fail/major/minor/style issues, and the path to the full audit doc. *"Verdict: ship_with_revisions. Evidence: solid. 0 fail, 1 major, 3 minor, 2 style. Full audit: Output/Reports/journal-reviewer-audit-pentimalli-deck-2026-05-08.md"*

## What this is NOT

- Not a rewrite. Produces the issue-list; the writer applies fixes.
- Not a rigor audit (use `methods_critic` for statistical rigor).
- Not a PI-readiness check (use `/pi-evaluator-audit`).
- Not a figure compliance check (use `/publication-guideline-audit`).

## See also

- `vaultlab/src/vaultlab/roles/journal_reviewer/{prompt.md,metadata.yaml}`
- `External/journal-guidelines/_index.md`
- `vaultlab/Sources/Notes/SPEC-meta-agent-roles-2026-05-07.md`
