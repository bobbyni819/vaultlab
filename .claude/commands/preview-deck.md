---
name: preview-deck
description: Generate a browser-openable HTML preview of a deck — arrow-key navigation, inline-embedded figures (base64), per-slide bullets + caption + references. Faster than opening PowerPoint; works on phone; shareable as a single .html file.
arguments: <plan-path-or-pptx> [--no-figures] [--out <path>]
---

# /preview-deck <plan-path-or-pptx>

> *"See your deck without opening PowerPoint — drop the HTML on the
> drive or share it as one file."*

Drives `vaultlab.slides.preview_html`. Renders a deck plan dict (JSON
or YAML) as an arrow-key navigable HTML slideshow. Figures are
inline-base64'd by default so the HTML is self-contained.

## Pre-flight

1. Resolve input:
   - If `<path>.json` → load as plan dict
   - If `<path>.yml` / `.yaml` → load as plan dict
   - If `<path>.pptx` → currently unsupported (TODO: extract plan from pptx); print TODO + exit
   - Otherwise: treat as a literal plan dict path

2. Resolve `--out` (default: same dir as input, `.html` suffix)

## Execution

```python
import json
from pathlib import Path
from vaultlab.slides.preview_html import write_deck_preview

plan = json.loads(Path("<plan-path>").read_text(encoding="utf-8"))
out_path = write_deck_preview(
    "<out-path>",
    plan,
    embed_figures=not <no-figures>,
)
print(f"wrote {out_path}")
print(f"to open: bobby-kb open {out_path.relative_to(kb_root)}")
```

## Output

- A single `.html` file containing:
  - Arrow-key navigable slides (← / →, Prev / Next buttons)
  - Per-slide title + type chip + bullets + caption + figure + references
  - Inline-base64 figures (no external image deps; opens offline)
  - Mobile-responsive (phone-friendly)

## When to use

- Verify a generated `.pptx` without opening PowerPoint
- Preview a plan dict before running the full `build_deck` pipeline
- Share a read-only deck preview with a collaborator (one .html file
  works as an email attachment or a Drive share)
- Open on the phone to skim slides on the go

## Related

- `vaultlab.slides.preview_html` — underlying renderer
- `vaultlab.slides.deck.build_deck` — the actual `.pptx` builder
- `/build-deck` — generate the `.pptx` from a plan
- `/reorder-slides` — drag/drop reorder a deck via HTML kanban
