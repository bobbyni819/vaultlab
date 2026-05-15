---
name: state-dashboard
description: Render a project state document (e.g. system-state-<date>.md or a hand-curated status digest) as an interactive HTML dashboard — Thariq Pattern #16 Weekly Status header + Pattern #6 Module Map + Pattern #15 Concept Explainer in one consumer. Single-file HTML, mobile-friendly, no external deps.
arguments: <state-md-or-json> [--out <path>]
---

# /state-dashboard <state-md-or-json>

> *"Turn your system-state doc into a one-page browser dashboard with
> shipped / in-flight / blockers, module map, and an optional concept
> explainer — share as a single .html."*

Drives `vaultlab.report.state_dashboard_html.write_state_dashboard_html`.
Eighth consumer of the `vaultlab.report` HTML stack (after the v0.0.5
weekly-status slice). Composes three Thariq HTML-effectiveness patterns
into one render:

| Pattern | Where |
|---|---|
| #16 Weekly Status header | Project chip, date, metric tiles, shipped / in-flight / blockers card grids |
| #6 Module Map | SVG arg-graph of the package map (`module_name, short_desc, downstream`) |
| #15 Concept Explainer *(optional)* | Inline diagram panel for the active research arc |

Every visual primitive comes from `vaultlab.report._components` — no
new components are introduced here.

## Input

A `StateDashboard` dataclass — pass it as JSON / YAML or build it in
Python. Recognised top-level fields:

- `project` — name chip (string)
- `date` — human-readable date label (string)
- `status_summary` — one-paragraph TL;DR
- `metrics` — `{metric_name: formatted_value}` (e.g. `{"tests": "1734 passing"}`)
- `shipped`, `in_flight`, `blockers` — list of `[title, description]` pairs
- `module_map` — list of `[module_name, short_desc, [downstream_modules]]`
- `concept_explainer` — optional dict with `title`, `summary`, `nodes`,
  `edges`, `hot_path` (omitted when `None`)

When the input is `.md`, Claude parses the doc into this shape before
calling the renderer — section headers map to shipped / in-flight /
blockers, the first paragraph becomes `status_summary`, and any
`module-map.json` next to the doc gets folded in.

## Pre-flight

1. Resolve `<state-md-or-json>`:
   - `.json` / `.yml` → load as dict, instantiate `StateDashboard(**dict)`
   - `.md` → parse sections into the dataclass (see below)
2. Resolve `--out` (default: same dir, `.html` suffix)

## Execution

```python
import json
import shlex
from pathlib import Path
from vaultlab.report.state_dashboard_html import (
    StateDashboard,
    write_state_dashboard_html,
)

raw_args = shlex.split("$ARGUMENTS") if "$ARGUMENTS" else []
positional: list[str] = []
out_arg: str | None = None
i = 0
while i < len(raw_args):
    tok = raw_args[i]
    if tok == "--out" and i + 1 < len(raw_args):
        out_arg = raw_args[i + 1]
        i += 2
    else:
        positional.append(tok)
        i += 1
src = " ".join(positional).strip()
src_path = Path(src)

if src_path.suffix in {".json", ".yml", ".yaml"}:
    payload = json.loads(src_path.read_text(encoding="utf-8"))
    state = StateDashboard(**payload)
else:
    # .md → YOU parse it. The doc-format convention (system-state-<date>.md)
    # uses H2 sections "Shipped", "In flight", "Blockers" with bullet items
    # of the form "- **<title>** — <description>". Metric tiles come from
    # a top-level YAML frontmatter "metrics:" key when present.
    md_text = src_path.read_text(encoding="utf-8")
    # Build the StateDashboard from the parsed sections...
    state = StateDashboard(
        project="<inferred>",
        date="<inferred>",
        status_summary="<TL;DR line>",
        shipped=[],
        in_flight=[],
        blockers=[],
        metrics={},
        module_map=[],
        concept_explainer=None,
    )

out_path = out_arg or src_path.with_suffix(".html")
written = write_state_dashboard_html(state, out_path)

print(f"wrote {written}")
print(f"to open: bobby-kb open {written}")
```

## Output

- A single `.html` file with:
  - **Top band**: project chip, date label, status summary as TL;DR box
  - **Metric tiles**: stat-card grid (numbers in big type)
  - **Card grids**: shipped (severity=good) / in-flight (severity=warn) /
    blockers (severity=bad)
  - **Module map**: SVG arg-graph with hover tooltips + card_grid legend
  - **Concept explainer** *(optional)*: inline mechanism diagram
- `<out>.provenance.json` + `<out>.method.md` sidecars (Red Line #2)

## When to use

- After writing a new `Sources/Notes/system-state-<date>.md`, render it
  to share with collaborators (or open on phone)
- Weekly retro — capture metrics + shipped/in-flight/blockers + module
  map in one page
- Quick project-status dashboard for a grant report or PI update

## Rules of engagement

- **Empty lists gracefully omit sections.** If `blockers=[]`, the
  blockers card grid disappears entirely — clean.
- **The module map is the package graph, not the file tree.** Use
  human-meaningful names (`vaultlab.research`, not `research/__init__.py`).
- **Concept explainer is opt-in.** Pass `concept_explainer=None` and the
  panel is omitted; pass a populated dict and you get an inline
  mechanism diagram next to the dashboard.

## Related

- `vaultlab.report.state_dashboard_html` — underlying renderer
- `vaultlab.report.weekly_status_html` — v0.0.5 weekly-status slice
  (same compositional shape, slightly simpler)
- `vaultlab.slides.audit_html` — same HTML grammar, used for deck audits
- `Wiki/Concepts/html-output-system.md` — full HTML output system concept
