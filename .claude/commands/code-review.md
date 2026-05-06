---
name: code-review
description: Audit a collaborator's notebook or script via rigor_auditor + decisions-log cross-reference. Pre-built draft message to the author for review-feedback delivery.
arguments: <file-path-or-author-name>
---

# /code-review <file-or-author>

> "Rachel pushed `Crypt_Panel_SI_vs_Colon.ipynb` overnight. Audit it."

Multi-pass code review: `rigor_auditor` role checks claim grounding + page-marker integrity + overclaim detection in the code's comments and outputs. Cross-references analytical decisions against the project's `decisions-log.md` to flag any conventions the new code drifts from. Drafts a structured-feedback message to the author for delivery (Teams or email — pending explicit user confirmation).

## Lineage

Lifts:
- **rigor_auditor** role from `vaultlab.roles.rigor_auditor` (own work, anchored on PaperQA2's evidence-grounding discipline)
- **gstack-style review checklist** (Garry Tan's gstack) — markdown-defined review criteria, explicit pass/fail per criterion
- **NotebookLM-style hover-quote** convention (Google) — quoted line citations in the review output

## Pre-flight checklist

1. Resolve KB root + project config
2. **Read the file** in full (not skim — semantic reading per CLAUDE.md commitment #2)
3. Read `decisions-log.md` — what analytical conventions has this project adopted?
4. If `<author-name>` instead of file path: glob recent commits by that author (`git log --author=<name> --since='30d' --name-only`) and review their most recent notebooks/scripts
5. State-aware preflight: search `Output/code-review-*` for prior reviews of this same file — if recent (<7d), default to `--variant` (review what's new since)

## Execution

### Step 1 — Code reading + claim extraction

Read the file. Extract:
- Every numerical claim in comments (e.g., *"95% accuracy"*, *"R²=0.97"*)
- Every method choice (statistical test, model, threshold)
- Every analytical assumption (preprocessing steps, sample stratification, missingness handling)

### Step 2 — Cross-reference vs project conventions

For each method choice in Step 1, check:
- Does `decisions-log.md` mandate a specific choice for this analysis class?
- Does the reviewed code match? If not — flag as `convention-drift`.

### Step 3 — `rigor_auditor` pass

Spawn `rigor_auditor` with system prompt including:
- The KB context preamble (commitment #7)
- The full code (not summary)
- The relevant decisions-log entries
- The role's mandated TASKS contract (read `roles/rigor_auditor/prompt.md` directly)

`rigor_auditor` outputs structured JSON:

```json
{
  "passed": false,
  "issues": [
    {"severity": "major", "line": 42, "issue": "claims 95% accuracy but no test set held out"},
    {"severity": "minor", "line": 88, "issue": "unhedged 'is leakage' should be 'is consistent with leakage'"},
    {"severity": "convention", "line": 15, "issue": "uses pearson; project decisions-log mandates spearman after Round 8"}
  ]
}
```

### Step 4 — Render review doc

Write to `<kb_root>/<project>/Output/code-review-<file-slug>-<date>.md`:

```markdown
# Code review: <file>

Author: <name>
Reviewed: <date>
Commit: <hash>

## ✅ What's good

- <strength 1, with cell/line ref>
- <strength 2>

## ⚠️ What to question

- **Line N:** <issue>. Suggested fix: <code>.
  - Project convention check: <reference to decisions-log>

## ❌ What's wrong

- **Line N:** <issue>. Required fix: <code>.

## Convention drift

- **Line N:** <code> uses <method>. Project decision (Round X): <other method>. Reconcile?
```

### Step 5 — Draft message to author

Compose a message for the author (BUT do not send — explicit confirmation required):

```
Hi <name>,

I audited <file> from your <date> push. Saw N strengths, M issues, K convention drifts.

Strengths: <2-3 bullets>
Most important to discuss: <top 1 issue>
Full review at: <path-to-review-doc>

Want to chat through the convention-drift items? <project-relevant time slot>

— <your name>
```

Show the message to Bobby. Wait for explicit *"send to <name> via Teams"* or *"draft an email"* before invoking `bobby_teams.send_message` or `bobby_outlook.create_draft`.

### Step 6 — Reply

*"Reviewed `<file>`: <N strengths, M issues, K drifts>. Top issue: <highest-severity>. Drafted a message to <author> — want me to send it via Teams, save as email draft, or just file the review doc?"*

## When to invoke

- Collaborator pushed code overnight (per `/catch-up` surfacing recent commits)
- User says *"audit Rachel's notebook"*, *"review this script"*, *"check what X did"*
- Before merging a PR (auto-trigger via CLAUDE.md hook in future)

## When NOT to invoke

- Reviewing your OWN code in flight (use `methods_critic` directly, not full /code-review)
- Style-only review (linters / formatters cover this — don't burn LLM calls)

## Follow-up

If the author responds, log their response into `decisions-log.md` (so future sessions know which conventions Rachel pushed back on, etc.).
