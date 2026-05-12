---
name: journal-club
description: Generate a journal-club deck for a paper using the right narrative arc for its paper type. Classifies the paper (discovery / methods / dataset / clinical / materials / review / generic), picks the matching arc, fills slide content from the paper summary, and builds the .pptx. Supports English and simplified Chinese.
arguments: <doi-or-summary-path> [--type discovery|methods|dataset|clinical|materials|review] [--language en|zh-CN] [--short] [--out <path>]
---

# /journal-club <doi-or-summary-path>

> *"Pick the right narrative spine for the paper type — not the
> manuscript section order."*

Drives `vaultlab.slides.journal_club_arcs` + the existing
`vaultlab.slides.build_from_plan`. The skill is in the arc selection:

- A **discovery / mechanism paper** gets a `question-to-evidence` arc
  (phenomenon matters → mechanism unknown → hypothesis → design →
  evidence × 3 → model → limitations).
- A **methods / algorithm paper** gets a `problem-to-solution` arc
  (bottleneck → proposed difference → workflow → eval design →
  perf vs baselines → ablation → failure modes → reuse).
- A **dataset / atlas / benchmark paper** gets a `workflow-to-validation`
  arc (resource need → cohort design → generation+QC → landscape →
  validation → insight → access).
- A **clinical / trial paper** gets a `design-to-inference` arc.
- A **materials / engineering paper** gets a `property-to-mechanism` arc.
- A **review / perspective** gets an `evidence-map` arc.
- Otherwise: `journal_club_default` (claim-first).

Each arc has conclusion-style slide titles — "Why this phenomenon
matters" not "Background"; "Performance vs baselines" not "Results".

## Pre-flight

1. Resolve input:
   - DOI → look up frontmatter in `Wiki/Summaries/<doi>.md`
   - Path → read directly
2. If `--type` given, use that paper-type slug; otherwise
   `classify_paper_type(metadata)` from frontmatter.
3. Resolve `--language` (default `en`)
4. Resolve `--short` (default false; 12-16 slides per arc; short =
   8-10 slides, dropping subordinate evidence panels)

## Execution

### Step 1 — Classify + fetch arc

```python
from vaultlab.slides.journal_club_arcs import (
    classify_paper_type, get_arc, arc_to_slide_plan,
)

paper_type = "<--type>" or classify_paper_type(frontmatter)
arc = get_arc(paper_type, language="<--language>")
print(f"Paper-type: {paper_type} ({arc['default_logic']})")
```

### Step 2 — Convert arc to slide-plan skeleton

```python
plan = arc_to_slide_plan(
    arc,
    deck_title=frontmatter.get("title") or "(untitled)",
    deck_subtitle=f"{frontmatter.get('authors', [''])[0]} et al. ({frontmatter.get('year')})",
)
```

### Step 3 — Fill slides with paper content

For each slide in `plan["slides"][1:]` (skip the title slide), fill the
content from the paper summary, using the slide's `_purpose` (`context`,
`gap`, `claim`, `method`, `evidence`, `model`, `limitations`) to drive
which section of the summary to draw from:

- `context` ← `tldr`, abstract introduction
- `gap` / `claim` ← key_findings + Discussion summary
- `method` ← Methods + Figure 1
- `evidence` ← Key results (Figures 2-5)
- `model` ← Discussion's mechanistic model section
- `limitations` ← Discussion's caveats

Bullets must be ≤24 words per the slide hard-rules memory; titles must
be conclusion-style (already enforced by the arc); ≤5 section dividers.

### Step 4 — Build the .pptx

```python
from vaultlab.slides.deck import build_from_plan
build_from_plan(plan, out_path="<out>")
```

### Step 5 — Audit + render HTML preview

```python
from vaultlab.workflows.crosstalk import rigor_audit
from vaultlab.slides.audit_html import write_audit_report
from vaultlab.slides.preview_html import write_deck_preview

audit = rigor_audit(document=..., audit_kind="deck", ...)
write_audit_report("<deck>.audit.html", plan, audit)
write_deck_preview("<deck>.preview.html", plan)
```

## Output package

- `<deck>.pptx` — the actual deck
- `<deck>.audit.html` — rigor audit
- `<deck>.preview.html` — keynav HTML preview (browser-openable)
- `<deck>.plan.json` — the plan dict (for future `/reorder-slides`)

## When to use

- Standing lab meeting / journal club presentations
- Bobby's family-share Chinese-language paper summary workflow
  (`--language zh-CN`) — pair with the existing Chinese-PDF export
- Conference / short-talk variant — `--short` for 8-10 slides

## Related

- `vaultlab.slides.journal_club_arcs` — arc registry + classifier
- `vaultlab.slides.deck.build_from_plan` — the .pptx builder
- nature-paper2ppt skill at `nature-skills/skills/nature-paper2ppt/` —
  upstream source
- `/preview-deck` + `/reorder-slides` — post-build editing
