---
name: polish
description: Polish academic prose for publication — apply the 25 nature-polishing rules + British-English vocabulary + sentence-length / hedging / overclaim checks across a markdown manuscript file. Returns a polished revision plus a diff-style audit report.
arguments: <manuscript-path> [--section results|methods|discussion|abstract|intro] [--check-only]
---

# /polish <manuscript-path>

> *"Apply the 25 prose rules + 12-step workflow before submission. Catch overlong sentences, mis-calibrated hedges, American spellings, overclaims, and house-style violations."*

Drives the `vaultlab.manuscript.polish` module across a manuscript file or
a single section. Two modes:

- **Default** — produces a polished revision + a diff-style audit
- **`--check-only`** — just runs the audits without rewriting prose

## What gets enforced

25 rules across 7 categories (see `vaultlab.manuscript.polish.POLISH_RULES`):

- **Sentence architecture (5):** ≤30 words, subject-first, active voice default, no stacked prepositions, one claim per sentence
- **Hedging calibration (4):** hedge-ladder match, no passive hedging, quantify when possible, preserve negative-results tone
- **Section tense (3):** results/methods past, discussion mixed
- **Vocabulary (4):** precise verbs, no intensifiers, British English, acronym-on-first-use
- **Citation integrity (3):** cite-only-read, 4-type attribution, no self-citation padding
- **Overclaim detection (3):** no absolutes, causation-vs-association, scope-fit
- **House style (3):** numbers/units, P-value format, CI vs SEM

## Pre-flight

1. Confirm the file exists and is markdown (or plain text)
2. If `--section` given, isolate that section only
3. Estimate work: count sentences > 30 words and US-spelling tokens

## Execution

### Step 1 — Run automated checks

```python
from pathlib import Path
from vaultlab.manuscript.polish import (
    check_sentence_length,
    check_us_spelling,
    POLISH_RULES,
    WORKFLOW_STEPS,
    write_polish_report,
)

text = Path("<manuscript-path>").read_text(encoding="utf-8")

# Automated checks
long_sentences = check_sentence_length(text, max_words=30)
us_words = check_us_spelling(text)

# v0.0.5 one-call writer — long-sentence + US-spelling findings as a
# markdown report with Red Line #2 provenance receipts. Use this for the
# `--check-only` fast path; the full polish pass below also runs it.
report_path = Path("<manuscript-stem>-polish-report.md")
write_polish_report(
    report_path,
    text,
    source_path="<manuscript-path>",
    max_words=30,
)
# Sidecars: <report_path>.provenance.json + <report_path>.method.md
```

### Step 2 — LLM polish pass (default mode)

If not `--check-only`, walk the 12-step workflow:

1. **sentence-split** — split the section into sentences
2. **section-id** — identify section type (drives tense + hedge rules)
3. **hourglass-check** — broad opening → narrow claim → broad implications
4. **tense-audit** — apply section-tense rules
5. **sentence-edit** — fix length, voice, structure, prepositions
6. **vocabulary-upgrade** — replace weak verbs / intensifiers; apply British English
7. **template-check** — compare to section template (results sentence template, etc.)
8. **citation-audit** — verify cited claims, tag attribution type
9. **house-style** — numbers, P-values, units, italics, error bars
10. **overclaim** — flag absolutes, causation, scope expansion
11. **proofreading** — typos, spacing, punctuation, capitalization
12. **plain-text-output** — emit clean MD

Apply rules one category at a time; do NOT batch all 25 rules into one
LLM call. Show before/after for each substantive change with the rule
ID that drove it.

### Step 3 — Render the audit as HTML

```python
from vaultlab.report import render_report, write_report
from vaultlab.report import components as c

sections = [
    c.tldr_box([
        f"{len(long_sentences)} sentences exceed 30 words",
        f"{len(us_words)} US-English tokens flagged for replacement",
        # ... any other diff stats
    ]),
    c.section(
        "Sentences > 30 words",
        c.matrix_table(
            ["#", "Words", "Sentence"],
            [[str(i), str(n), s[:200]] for i, n, s in long_sentences],
        ),
    ),
    c.section(
        "US → British English suggestions",
        c.matrix_table(
            ["US", "British"],
            [[us, uk] for us, uk in us_words[:60]],
        ),
    ),
]
write_report(
    "<manuscript-stem>-polish-audit.html",
    title="Polish audit — <manuscript-stem>",
    eyebrow="vaultlab · prose polish",
    sections=sections,
)
```

### Step 4 — Emit the polished revision

Write the revised text to `<manuscript-stem>-polished.md` (or
`-polished-<section>.md` if `--section` was given). Preserve all
frontmatter; do not rename the file.

## Output package

- `<stem>-polished.md` — full polished revision (unless `--check-only`)
- `<stem>-polish-audit.html` — interactive audit with per-rule findings,
  long-sentence list, US-spelling table
- `<stem>-polish-diff.md` — sentence-level before/after pairs with the
  rule ID driving each change

## Rules of engagement

- **Never invent claims.** Polish preserves meaning; if a claim is
  unsupported, flag it as an overclaim, don't strengthen it.
- **Hedging is not weakening.** Match hedge strength to evidence; "may
  reflect" is not weaker than "demonstrates" when evidence is
  correlational.
- **British English is mandatory** for Nature-family journals. Do not
  override unless the user names a US-style target (PNAS, JAMA, Science
  has its own rules).
- **Citation integrity** comes from `/cite audit`, not from this
  command. Polish does not re-verify; it relies on the citation audit
  having been run.

## Related

- `vaultlab.manuscript.polish` — the underlying rules module
- `/cite audit` — citation verification (must precede `/polish` for
  final-pass work)
- `vaultlab.report` — HTML report renderer
- nature-polishing skill at `nature-skills/skills/nature-polishing/` —
  upstream source
