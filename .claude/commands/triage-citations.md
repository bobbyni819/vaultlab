---
name: triage-citations
description: Generate a drag-drop HTML editor for triaging citations. Each citation starts in a pile based on its verification status (Accept / Reject / Needs review / Pending / Flag for plagiarism). User drags between piles in the browser, then clicks "Copy as JSON" to paste the verdict map back into the next prompt.
arguments: <citations-json> [--out <path>] [--title "<panel title>"]
---

# /triage-citations <citations-json>

> *"Drag citations between accept / reject / needs-review / flag piles
> in the browser, then paste the verdict map back into the next
> vaultlab prompt — HTML is the two-way I/O surface."*

Drives `vaultlab.report.editors.build_citation_triage_editor`. Renders
each citation as a card in a kanban board with five piles:

| Pile | When |
|---|---|
| **Pending** | Default — citation not yet verified |
| **Accept** | Verified full-text or verified abstract |
| **Reject** | Contradicted by source |
| **Needs review** | API-confirmed (DOI resolved) but no full-text check yet |
| **Flag for plagiarism** | Suspect — looks like a hallucinated or fabricated reference |

Drag, drop, then click "Copy as JSON" or "Copy as markdown" to export
the new verdict map. This closes the loop: HTML becomes both the output
of one operation (citation audit) and the structured input to the next
(re-running the manuscript with a curated citation list).

## Input shape

A JSON list of citation dicts. Each entry recognised keys:

- `authors` (string or list — "Smith et al.")
- `year`
- `title` *or* `claim` (the text snippet for the card)
- `status` — one of `verified_fulltext`, `verified_abstract`,
  `api_confirmed`, `unverified`, `suspect`, `contradicted`. Drives the
  initial pile assignment.
- `doi`, `pmid`, `evidence_url` — carried but not displayed on the card

Anything else in the dict is ignored by the renderer.

## Pre-flight

1. Resolve `<citations-json>` — must be a JSON array
2. Resolve `--out` (default: same dir, `.triage.html` suffix)
3. Resolve `--title` (default: `"Citation triage"`)

## Execution

```python
import json
import shlex
from pathlib import Path
from vaultlab.report.editors import write_citation_triage_editor

raw_args = shlex.split("$ARGUMENTS") if "$ARGUMENTS" else []
positional: list[str] = []
out_arg: str | None = None
title_arg: str = "Citation triage"
i = 0
while i < len(raw_args):
    tok = raw_args[i]
    if tok == "--out" and i + 1 < len(raw_args):
        out_arg = raw_args[i + 1]
        i += 2
    elif tok == "--title" and i + 1 < len(raw_args):
        title_arg = raw_args[i + 1]
        i += 2
    else:
        positional.append(tok)
        i += 1
src = Path(" ".join(positional).strip())
citations = json.loads(src.read_text(encoding="utf-8"))
if not isinstance(citations, list):
    raise SystemExit("citations-json must be a JSON array of citation dicts")

out_path = Path(out_arg) if out_arg else src.with_suffix(".triage.html")
written = write_citation_triage_editor(out_path, citations, title=title_arg)

print(f"wrote {written}")
print("Open in browser, drag citations between piles, then click 'Copy as JSON'.")
print(f"to open: bobby-kb open {written}")
```

## Output

A single `.html` file containing:

- A kanban board with five columns (Pending / Accept / Reject /
  Needs review / Flag for plagiarism)
- Each card: `[N] <authors> (<year>) — <claim or title, truncated>`
- Drag/drop between any columns
- "Copy as markdown" button → exports as nested bullet list
- "Copy as JSON" button → exports as `{pile_name: [card_labels]}`

## Workflow

1. Run `/cite audit <manuscript>` to get a citation audit report.
2. Export the citations list as JSON (the audit report already has
   per-citation status fields).
3. Run `/triage-citations <citations.json>` to open the kanban editor.
4. Open the HTML in your browser; drag suspicious citations to
   "Flag for plagiarism", drag any false-rejects back to "Accept".
5. Click "Copy as JSON".
6. Paste back into the next prompt:
   "Here's the curated verdict: `<paste>`. Update the manuscript with
   only the accepted citations."

## When to use

- After `/cite audit` flags a mixed accept / suspect / unverified pile
  and you need to make per-citation human-in-the-loop decisions.
- Before running `/manuscript-section ... review` to lock in which
  citations the next draft is allowed to keep.
- For a quick visual audit on a long bibliography — easier than
  scrolling a CSV.

## Rules of engagement

- **The editor doesn't modify your citations.** It produces a verdict
  map — you paste it back into the next prompt for the downstream
  consumer to act on.
- **Flag for plagiarism is for suspect citations**, not for content
  disagreement. Use Reject for "this citation contradicts the claim".
- **Pile names are stable.** The export uses the literal pile names —
  downstream tooling matches on exactly those strings.

## Test plan

- Empty list → renders a board with five empty columns and a TL;DR
  box that reads `0 citations to triage`.
- 10-citation list with mixed `status` values → each card lands in the
  correct initial pile per the status map.
- Verdict round-trip: drag one card from Pending → Accept, click
  "Copy as JSON" → output contains the moved label under the `"Accept"`
  key.

## Related

- `vaultlab.report.editors.build_citation_triage_editor` — underlying
  renderer
- `/cite audit` — produce the citation audit feeding this command
- `/reorder-slides` — sibling kanban editor for deck plans
- Pattern source: Thariq Shihipar #18 triage board at
  thariqs.github.io/html-effectiveness/18-editor-triage-board.html
