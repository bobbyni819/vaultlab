---
name: respond
description: Draft a point-by-point reviewer response letter. Parses a reviewer block, classifies each comment, assigns stable R<n>-C<m> IDs, suggests an action per comment, and emits the letter as markdown plus an HTML interactive view. Two modes — scaffold (just structure + suggested actions) and full-draft (response prose included).
arguments: <reviewer-block-path> [--reviewer N] [--full-draft] [--manuscript <path>]
---

# /respond <reviewer-block-path>

> *"Turn a reviewer block into an editor-facing verification document — every concern gets an ID, kind, action, evidence reference, and (in full-draft mode) response prose."*

Drives the `vaultlab.manuscript.respond` module. Two modes:

- **Default — `--scaffold`** — parse + classify + ID + suggest action; leave response prose empty for the author
- **`--full-draft`** — also write response prose, citing evidence in the manuscript (requires `--manuscript`)

## Output structure (per comment)

Each comment is rendered as a markdown block:

```markdown
### R1-C2
> [reviewer's verbatim quote]

**Kind:** `overclaim`  **Action:** `SOFTEN_CLAIM`
**Where in revision:** §Discussion, p.14 lines 8-15

We thank the reviewer. We have softened the claim from "X causes Y" to
"X is associated with Y under the conditions tested" (Discussion, lines
8-15). The new wording is consistent with the observational nature of
the cohort design.
```

If `action == AUTHOR_INPUT_NEEDED`, the block ends with an explicit
⚠️ flag and a question for Bobby.

## 12-kind taxonomy

`CommentKind` covers: method_question, method_critique, result_question,
result_challenge, overclaim, novelty_question, missing_citation,
missing_experiment, presentation, scope, positive, editorial.

## 9 action types

`ActionType`: ACCEPT_TEXT, ACCEPT_ANALYSIS, ACCEPT_EXPERIMENT,
ACCEPT_FIGURE, ACCEPT_CITATION, SOFTEN_CLAIM, DISAGREE_WITH_RATIONALE,
AUTHOR_INPUT_NEEDED, DEFER_TO_FUTURE_WORK.

## Pre-flight

1. Confirm `<reviewer-block-path>` exists
2. Resolve `--reviewer` (default 1)
3. If `--full-draft`, confirm `--manuscript` is a real path

## Execution

### Step 1 — Parse + classify

```python
from pathlib import Path
from vaultlab.manuscript.respond import (
    parse_reviewer_block,
    render_response_letter,
    ResponseLetter,
    ActionType,
)

block = Path("<reviewer-block-path>").read_text(encoding="utf-8")
comments = parse_reviewer_block(block, reviewer_index=<N>)
```

`parse_reviewer_block` looks for `1.`, `2.`, `(1)`, `Comment 1:` etc. and
returns a list of `ReviewerComment` with `kind` + suggested `action` auto-filled.

### Step 2 — In full-draft mode, draft response prose

For each comment, draft response prose per the action:

- `ACCEPT_TEXT` — describe what prose changed
- `ACCEPT_ANALYSIS` — describe the new analysis + cite the figure/table
- `ACCEPT_EXPERIMENT` — describe the new experiment + cite the figure
- `ACCEPT_CITATION` — name the added reference + where it appears
- `SOFTEN_CLAIM` — show before / after quotes
- `DISAGREE_WITH_RATIONALE` — evidence-led pushback, cooperative tone
- `AUTHOR_INPUT_NEEDED` — explicit ⚠️ + open question

Set `evidence_ref` to a concrete location in the revised manuscript
("§Results, p.7 lines 12-18" or "Fig. 3c").

### Step 3 — Render

```python
from vaultlab.manuscript.respond import write_response_letter

letter = ResponseLetter(
    reviewer=<N>,
    opening="We thank the reviewer for the constructive comments...",
    comments=comments,
    closing="We hope these revisions address the reviewer's concerns.",
)
md_path = "response-to-reviewer-<N>.md"

# v0.0.5 one-call writer — renders the letter and writes Red Line #2
# provenance sidecars (.provenance.json + .method.md) next to the .md.
# Prefer this over plain Path(...).write_text(render_response_letter(...)).
write_response_letter(md_path, letter, inputs=["<reviewer-block-path>"])
```

### Step 4 — HTML view

Wrap in an interactive HTML for review:

```python
from vaultlab.report import render_report, write_report
from vaultlab.report import components as c
# Per-comment severity_cards, filter by action type, copy-comment button
```

## Tone discipline

- Always cooperative; the reviewer is helping the paper.
- Use first-person plural ("we", "our") and present tense.
- Disagree only with **scientific or scope-based** reasoning. No
  defensive language; no "as the reviewer should know".
- Acknowledge what's right before pushing back.

## Rules of engagement

- **Never invent.** Do not claim experiments, citations, or analyses
  exist that haven't been performed. Mark them `AUTHOR_INPUT_NEEDED`.
- **Stable IDs are permanent.** Once a comment has `R1-C3`, it stays
  `R1-C3` across revisions. Add new comments at the end.
- **Evidence-ref required** for every action except
  `AUTHOR_INPUT_NEEDED`. The editor needs to verify the change happened.

## Output package

- `response-to-reviewer-<N>.md` — point-by-point response letter
- `response-to-reviewer-<N>.html` — HTML view, color-coded by action
- `response-to-reviewer-<N>-open-questions.md` — list of items flagged
  `AUTHOR_INPUT_NEEDED` so Bobby can decide

## Related

- `vaultlab.manuscript.respond` — underlying scaffolding
- nature-response skill at `nature-skills/skills/nature-response/` —
  upstream source
- `/polish` — polish the response letter before sending
