---
name: reorder-slides
description: Generate a drag-drop HTML editor for a deck plan. User opens the .html in a browser, drags slides between sections (or to "Cut"), then clicks "Copy as JSON" to paste the new ordering back into the next prompt. Two-way HTML — vaultlab artifact becomes a tiny purpose-built editor.
arguments: <plan-path> [--sections <a,b,c>] [--out <path>]
---

# /reorder-slides <plan-path>

> *"Move slides around with drag/drop in the browser, then copy the
> new plan-dict back into the next vaultlab prompt."*

Drives `vaultlab.report.editors.build_slide_reorder_editor`. Renders
the deck plan as a kanban board grouped by section. User drags slides
between sections (or to a "Cut" bucket for removal), then clicks
"Copy as JSON" or "Copy as markdown" to export the new ordering.

This closes the loop: HTML becomes both the output of one operation
and the structured input to the next.

## Pre-flight

1. Resolve input: `<plan-path>` must be a JSON/YAML plan dict
2. Resolve `--sections` (optional explicit column order — defaults to
   the sections discovered in the plan, plus "Cut" at the end)
3. Resolve `--out` (default: same dir as input, `.reorder.html` suffix)

## Execution

```python
import json
from pathlib import Path
from vaultlab.report.editors import write_slide_reorder_editor

plan = json.loads(Path("<plan-path>").read_text(encoding="utf-8"))
sections = "<sections>".split(",") if "<sections>" else None

out_path = write_slide_reorder_editor(
    "<out-path>",
    plan,
    sections=sections,
)
print(f"wrote {out_path}")
print("Open in browser, drag slides between sections, then click 'Copy as JSON'.")
print(f"to open: bobby-kb open {out_path}")
```

## Output

A single `.html` file containing:

- A kanban board with one column per section + "Cut" bucket
- Each card: `<idx>. [<type>] <title>` for a slide
- Drag/drop between any columns
- "Copy as markdown" button → exports as nested bullet list
- "Copy as JSON" button → exports as `{section: [slide-labels]}`

## Workflow

1. Run `/reorder-slides <plan>` to generate the HTML editor
2. Open it in browser
3. Drag slides around until the new ordering feels right
4. Click "Copy as JSON"
5. Paste back into the next vaultlab prompt:
   "Here's the new ordering: `<paste>`. Rebuild the deck plan with this."
6. Claude regenerates the plan dict with slides in the new positions

## When to use

- After a draft deck has been generated and the slide order needs
  shuffling
- When a section needs to be removed but you want to see the slides
  pile up in "Cut" first
- For prelim/quals decks where the speaker wants to test multiple
  orderings without regenerating the deck six times

## Related

- `vaultlab.report.editors.build_slide_reorder_editor` — underlying
  renderer
- `/preview-deck` — render the *current* plan as a slideshow (read-only)
- `/build-deck` — generate the `.pptx` from a plan
- Pattern source: Thariq Shihipar's #18 triage board at
  thariqs.github.io/html-effectiveness/18-editor-triage-board.html
