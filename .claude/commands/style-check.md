---
name: style-check
description: Apply Bobby's thesis/proposal writing rules to a prose draft — no em-dashes, no arrows, no filler, no rhetorical questions, define abbreviations, US English, capabilities-only honesty, plus the anti-AI-tell flow rules. Thin dispatcher to the polish engine and the canonical practice doc.
arguments: <draft.md> [--check-only]
---

# /style-check <draft.md>

> Applies the section-A writing rules from
> [`docs/writing-and-citation-practices.md`](../../docs/writing-and-citation-practices.md). This command
> is a thin dispatcher: it shares the single source of truth with `/polish`, it does not become a second
> divergent prose-checker. For Nature-family manuscript polishing, use `/polish`. For Bobby's thesis,
> proposal, and grant prose, use this.

Two modes:
- **Default** — flag every violation and propose the minimal rewrite, one rule category at a time.
- **`--check-only`** — list violations without rewriting.

## Deterministic rules (mechanical, safe to auto-flag)

- No em-dashes (—) in prose. Use commas, periods, or parentheses.
- No arrow symbols (→). Write "to", "then", or "into".
- Few colons. Prefer full sentences.
- No filler words: exactly, really, just, actually, of course, in turn, simply, clearly.
- No rhetorical questions.
- No short, snappy, AI-sounding sentences ("This is biology, not abstraction.").
- Every abbreviation defined at first use; real Greek letters (IFN-γ, not IFNG).
- **US English, not British.** This overrides the `/polish` British-English default. (When the engine
  StyleProfile lands on `feat/writing-citation-practices`, load `StyleProfile.from_yaml("bobby")` so US
  spelling is preserved rather than rewritten.)
- Capabilities-only for in-progress metrics; no brittle test percentages, counts, or runtimes; hedged voice.

## Judgment-level rules (apply with care; confirm with Bobby before a heavy rewrite)

The anti-AI-tell flow rules shape sentence rhythm and are not regex-checkable. Do not over-edit the
author's prose. If a pass would substantially rewrite a paragraph for flow alone, surface the proposed
change and ask before applying.

- Lead with the main clause.
- Reduce comma-stops; split clause-stacked sentences in two.
- Vary sentence length; avoid a run of same-length sentences.
- Plain language, concrete verbs and adjectives; rewrite long nested sentences and idioms
  ("closes the loop"); prefer plain verbs over jargon verbs ("controls" over "gates").

## Output

A revised draft (default mode) plus a short violation report grouped by rule. Save the report to
`<kb>/Output/<project>/style-check-<target>-<date>.md` so it serves as the audit trail. Then run the
section-G pre-ship checklist.
