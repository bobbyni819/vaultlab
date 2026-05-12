# HTML output — `vaultlab.report`

For human-readable artifacts longer than ~100 lines (audits, lit-arc
narratives, reasoning chains, dossiers, citation reports, deck previews),
vaultlab emits **single-file HTML** as the default format. One `.html`
file is the artifact — inline CSS, vanilla JS, no external dependencies.
Open in any browser; archive cleanly; share as an email attachment;
view on a phone.

This guide explains the system, the 15 component primitives, and how to
wire a new consumer.

## Why HTML, not markdown?

Markdown is great when a human will edit the file in their text editor
(frontmatter, KB notes, READMEs, slash command bodies). For *reading*,
markdown breaks down past about a hundred lines — no nav, no filters,
no embedded charts, no scannable card grids, no interactive widgets.

HTML solves all of those without giving up the "one file" property.

Background reading: Thariq Shihipar (Anthropic), *"The Unreasonable
Effectiveness of HTML"* — [thariqs.github.io/html-effectiveness](https://thariqs.github.io/html-effectiveness).
The 20-example gallery there is the pattern source for vaultlab's
component library.

## Quickstart

```python
from vaultlab.report import render_report, write_report
from vaultlab.report import components as c

html_str = render_report(
    title="Deck audit — multi-lung-short.pptx",
    eyebrow="vaultlab · slide audit",
    subtitle="14 slides · run 2026-05-12 14:32",
    sections=[
        c.tldr_box(["12 slides OK", "2 warnings", "0 errors"]),
        c.section(
            "Per-slide verdicts",
            c.filter_bar(
                [("All", "all"), ("Warnings", "warn"), ("Errors", "bad")],
                target_selector=".vl-cards .vl-card",
            ),
            c.card_grid([
                c.severity_card(
                    f"Slide {i}",
                    body="Title overflow at 56 chars (limit 48).",
                    severity="warn",
                    badges=[("title overflow", "warn")],
                    filter_key="warn",
                )
                for i in range(1, 4)
            ]),
        ),
    ],
)

write_report("audit.html", title="Audit", sections=[...])
```

Open `audit.html` in any browser.

## The universal dispatcher

If you have a result dict from any vaultlab primitive and don't want
to pick the consumer yourself:

```python
from vaultlab.report import render_artifact_html, write_artifact_html

# Auto-detects: deck-audit / litarc / reasoning / citation / dossier /
# response-letter based on the dict shape.
html_str = render_artifact_html(some_result_dict)

# Or write directly:
write_artifact_html("output.html", some_result_dict)

# Force a specific kind:
write_artifact_html("output.html", data, kind="reasoning")
```

The dispatcher is the Python counterpart to the `/audit-html` slash
command.

## The 6 consumers shipped with v0.0.4

Each consumer is a thin wrapper that converts a domain artifact (rigor
audit, lit-arc, etc.) into one or more `vaultlab.report` components and
calls `render_report`.

| Consumer | Domain artifact | Module |
|---|---|---|
| Deck audit | `rigor_audit` result + plan dict | `vaultlab.slides.audit_html` |
| Lit-arc narrative | Paper frontmatters + arc text | `vaultlab.research.litarc_html` |
| Reasoning chain | `CrosstalkResult` | `vaultlab.workflows.reasoning_html` |
| Citation audit | `AuditReport` | `vaultlab.citations.report_html` |
| Project dossier | `Dossier` | `vaultlab.kb.dossier_html` |
| Keynav .pptx preview | Deck plan dict | `vaultlab.slides.preview_html` |

Plus three two-way HTML editors in `vaultlab.report.editors`:
slide-reorder kanban, citation-triage kanban, deck-plan template tuner.

A seventh consumer added during /iterate: response-letter HTML
(`vaultlab.manuscript.respond_html`).

## The 15 primitives

All in `vaultlab.report.components` (aliased to `c` by convention):

| Primitive | Use |
|---|---|
| `tldr_box` | Accent box for the headline summary |
| `status_chip` | Inline severity/status badge |
| `card_grid` | Auto-fill responsive grid of cards |
| `severity_card` | One card — title, body, badges, thumbnail, actions, filter-key |
| `matrix_table` | Standard HTML table |
| `compare_panel` | Two-pane side-by-side |
| `collapsible_step` | Expandable `<details>` with optional file:line ref |
| `tabbed_block` | Tabbed content panes |
| `timeline` | Vertical timestamp/label/body events |
| `svg_arg_graph` | Inline SVG nodes + edges with optional hot-path |
| `kanban_board` | Drag-and-drop columns; copy-as-markdown/JSON exports |
| `template_editor` | `{{var}}` template with live preview on samples |
| `margin_glossary` | Inline term / definition callout |
| `keynav_deck` | Arrow-key navigable slide deck |
| `filter_bar` | Toggle visibility by `data-filter-key` |
| `section` | Wrap content in `<section>` with optional H2 |

Interactive components (tabs, kanban, editor, deck, filter) depend on
the inline JS bundled by `html.py`. The output stays self-contained —
no CDN, no external scripts.

## Two-way HTML — closing the loop

Some HTML outputs are not just read-only renderings — they're tiny
purpose-built editors. The user drags / edits / picks in the browser,
then clicks "Copy as JSON" or "Copy as markdown" to export the result
back into the next vaultlab prompt.

```python
from vaultlab.report import editors

# Slide reorder kanban
editors.write_slide_reorder_editor("reorder.html", deck_plan)

# Citation triage piles
editors.write_citation_triage_editor("triage.html", citations)

# Live-preview prompt tuner
editors.write_deckplan_tuner(
    "tuner.html",
    template="Slide {{n}}: {{title}}",
    samples=[{"n": "3", "title": "Visium overview"}, {"n": "5", "title": "..."}],
)
```

Pattern source: Thariq's gallery #18 (triage board), #19 (feature-flag
editor), #20 (prompt tuner).

## Smoke test + reference: the gallery

```bash
python examples/html_report_gallery/run_gallery.py
```

Runs all 6 consumers + 3 editors against realistic-shaped fake data and
writes the results to `examples/html_report_gallery/output/`. Open the
`index.html` to see every output side by side. Use the script as a
reference when wiring a new consumer.

The gallery has a CI test (`tests/test_examples/test_html_gallery.py`)
that imports the script as a module and verifies every output is
generated and parses as valid HTML.

## Design tokens

The bundled CSS exposes CSS custom properties; override them in your
own `<style>` block to retheme without forking:

```
--ink, --ink-soft, --muted          text greys
--line, --line-soft                 borders
--bg, --bg-soft                     backgrounds
--accent, --accent-soft             indigo brand
--good, --good-bg, --good-line      green
--warn, --warn-bg, --warn-line      amber
--bad, --bad-bg, --bad-line         red
--shadow                            card hover lift
--code-bg, --code-ink               dark code blocks
```

Slate + indigo by default. System fonts (no web font load).
Mobile breakpoint at 768px. `@media print` hides export bars + filter
chrome.

## Writing a new consumer

Pattern (mirroring the 6 shipped consumers):

```python
from vaultlab.report import components as c
from vaultlab.report import render_report


def build_my_artifact_html(domain_obj, *, title=None):
    # 1. Compute summary stats from the domain object
    n_items = len(domain_obj.items)
    severity_counts = ...

    # 2. Build header chips
    summary_chips = [c.status_chip(f"{n_items} items", "neutral")]
    summary_chips.append(c.status_chip(f"{severity_counts['bad']} errors", "bad"))

    # 3. Build per-item cards
    cards = [
        c.severity_card(
            item.title,
            body=item.description,
            severity=item.severity,
            badges=[(item.kind, item.severity)],
            filter_key=item.severity,
        )
        for item in domain_obj.items
    ]

    # 4. Compose sections
    sections = [
        c.section(
            None,
            c.tldr_box([f"{n_items} items audited.", ...]),
            f'<div style="margin: 14px 0;">{"".join(summary_chips)}</div>',
        ),
        c.section(
            "Items",
            c.filter_bar([("All", "all"), ("Errors", "bad")], target_selector=".vl-cards .vl-card"),
            c.card_grid(cards),
        ),
    ]

    # 5. Render
    return render_report(
        title=title or "My artifact",
        eyebrow="vaultlab · my domain",
        sections=sections,
    )
```

Tests should:
- Assert the output starts with `<!doctype html>` and parses cleanly.
- Assert the right severity/filter keys appear.
- Include an XSS test — pass `<script>alert(1)</script>` as input and
  verify it's escaped to `&lt;script&gt;` in the output.
- Test that `write_X` materializes a real file on disk.

## When NOT to use HTML

- **Edit-me files** — frontmatter, KB notes, READMEs, slash commands,
  role prompts. Keep as markdown so they version-control and merge well.
- **Short stdout output** — one-line summaries, status pings. Just print.
- **API responses** — JSON.
- **Wiki concept articles** — markdown primary (Obsidian-native). Use
  `render_artifact_html(kind="dossier")` to generate an HTML *view* of
  a wiki article on demand if the user wants to share it.

## Related

- `src/vaultlab/report/SKILL.md` — when-to-use HTML vs MD guidance,
  loaded by the model when invoking `vaultlab.report` operations.
- `Wiki/Concepts/html-output-system.md` (KB) — concept article for
  cross-project recall.
- `INSPIRATIONS.md` — attribution to Thariq Shihipar and the
  nature-skills bundle (Yuan Yizhe, SJTU).
- `Output/Plans/html-and-nature-skills-2026-05-12.html` — the v0.0.4
  plan that drove the system.
