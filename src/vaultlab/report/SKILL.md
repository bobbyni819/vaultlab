---
name: vaultlab-report
description: >-
  Render vaultlab artifacts (audits, lit-arc narratives, reasoning chains,
  dossiers, plans) as self-contained HTML reports. Use when the output will
  be read by a human, shared with collaborators, archived, or opened on a
  phone. Prefer HTML over Markdown for any artifact longer than ~100 lines.
---

# vaultlab.report — HTML output for everything

The thesis (Thariq Shihipar, Anthropic, 2026): markdown has become the
bottleneck for how agents communicate complex work to humans. HTML preserves
information density (tables, SVG, embedded code, interactivity), is naturally
shareable (a single file you can email or host), and supports two-way
interaction (drag-drop, sliders, copy-as-JSON for paste-back into the next
prompt).

This module is vaultlab's deep-module HTML primitive. One entrypoint
(``render_report``) wraps a list of pre-rendered section strings into a
self-contained ``.html`` document with inline CSS + vanilla JS, no external
assets, mobile-responsive + print-friendly.

## When to emit HTML vs Markdown

| Output | Format |
|--------|--------|
| Audit reports (deck, citations, manuscript) | **HTML** primary, MD fallback |
| Lit-arc narratives, reasoning chains | **HTML** primary |
| Project dossiers (SPEC-N) | **HTML** primary |
| Plan docs, exploration / SPEC docs | **HTML** primary |
| Per-file frontmatter, KB notes, READMEs | **MD** (git-tracked, edited in Obsidian) |
| Throwaway scripts, one-line summaries | **MD** or stdout |
| Wiki concept articles | **MD** primary (Obsidian native), HTML render on demand |

The general rule: if a human opens the artifact in a browser, emit HTML; if a
human edits it in their text editor, keep MD.

## API

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
                [("All", "all"), ("Errors", "bad"), ("Warnings", "warn")],
                target_selector=".vl-cards .vl-card",
            ),
            c.card_grid([
                c.severity_card(
                    "Slide 3",
                    body="Title 56 chars (limit 48); bullet 3 exceeds 24 words.",
                    severity="warn",
                    badges=[("title overflow", "warn"), ("bullet len", "warn")],
                    filter_key="warn",
                    actions=[("Copy plan dict", '{"slide": 3, ...}')],
                ),
            ]),
        ),
    ],
)

# Or write directly to disk:
write_report("audit-multi-lung-short.html", title="...", sections=[...])
```

## 15 component primitives

All in ``vaultlab.report._components`` (re-exported as
``vaultlab.report.components``). All return HTML strings; all interactive
variants depend on the JS bundled by ``html.py`` (auto-included unless
``include_js=False``).

| Primitive | Purpose | Interactive? |
|-----------|---------|--------------|
| ``tldr_box`` | Accent box with headline summary | no |
| ``status_chip`` | Inline severity/status badge | no |
| ``card_grid`` | Auto-fill responsive grid of cards | no |
| ``severity_card`` | One card with title/body/badges/thumbnail/actions | no |
| ``matrix_table`` | Standard HTML table | no (sortable in v0.0.5) |
| ``compare_panel`` | Two-pane side-by-side | no |
| ``collapsible_step`` | Expandable ``<details>`` with optional file:line | yes (native) |
| ``tabbed_block`` | Tabbed code/content panes | yes |
| ``timeline`` | Vertical ts/label/body events | no |
| ``svg_arg_graph`` | Inline SVG nodes+edges with optional hot-path | no |
| ``kanban_board`` | Drag-and-drop columns, copy-as-markdown/JSON | yes |
| ``template_editor`` | ``{{var}}`` template w/ live preview on samples | yes |
| ``margin_glossary`` | Inline term/definition callout | no |
| ``keynav_deck`` | Arrow-key navigable slide deck | yes |
| ``filter_bar`` | Toggle visibility of cards/rows by data-filter-key | yes |
| ``section`` | Wrap content in ``<section>`` with optional H2 | no |

## Design tokens (CSS variables)

The bundled CSS exposes these custom properties so consumers can override
without forking the stylesheet:

```
--ink, --ink-soft, --muted          → text greys
--line, --line-soft                 → borders
--bg, --bg-soft                     → backgrounds
--accent, --accent-soft             → indigo brand
--good / --warn / --bad             → semantic colors + matching bg/border
--shadow                            → card hover lift
--code-bg, --code-ink               → <pre> dark block
```

Slate + indigo palette. System fonts (no web font load). Mobile breakpoint
at 768px. ``@media print`` hides export bars + filter chrome.

## Anti-patterns

Do not:

- Inline scripts that load external JS (CDN, jsDelivr, etc.). Reports stay
  archive-friendly and offline-readable.
- Render unescaped user content. ``_components`` escapes labels but trusts
  pre-rendered HTML in ``body`` / ``content`` positions — callers must
  escape there.
- Bake the rendered date or git SHA into the section content (looks like
  a diff on re-runs). Use the bundled footer or the ``meta`` slot in the
  header instead.
- Build framework-style component hierarchies. These are flat string
  functions, on purpose.

## Test strategy

``tests/test_vaultlab_report/test_html.py`` snapshot-tests:

- A minimal report end-to-end
- Each of the 15 primitives in isolation
- That ``render_report`` output round-trips through ``html.parser`` cleanly
- That ``write_report`` materializes a readable file

Tests do not render in a browser. Visual verification is a manual step the
first time a new consumer is wired (Bobby opens the file).

## Related

- ``vaultlab/Output/Plans/html-and-nature-skills-2026-05-12.html`` — full plan
- ``vaultlab/INSPIRATIONS.md`` — attribution to thariqs/html-effectiveness +
  Yuan Yizhe / nature-skills.
- ``feedback_doc_persistence_baked_in`` — features must persist as code, not
  one-off artifacts; this primitive is the persistence vehicle for HTML
  output across vaultlab.
