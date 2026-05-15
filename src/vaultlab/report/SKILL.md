---
name: vaultlab-report
description: >-
  Render vaultlab artifacts (audits, lit-arc narratives, reasoning chains,
  dossiers, plans, status reports, editors) as self-contained HTML reports.
  Use when the output will be read by a human, shared with collaborators,
  archived, or opened on a phone. Prefer HTML over Markdown for any artifact
  longer than ~100 lines.
---

# vaultlab.report — HTML output for everything

The thesis (Thariq Shihipar, Anthropic, 2026): markdown has become the
bottleneck for how agents communicate complex work to humans. HTML preserves
information density (tables, SVG, embedded code, interactivity), is naturally
shareable (a single file you can email or host), and supports two-way
interaction (drag-drop, sliders, copy-as-JSON for paste-back into the next
prompt).

This module is vaultlab's deep-module HTML primitive. One entrypoint
(`render_report`) wraps a list of pre-rendered section strings into a
self-contained `.html` document with inline CSS + vanilla JS, no external
assets, mobile-responsive + print-friendly.

> **See also:** [`docs/html-pattern-coverage.md`](../../../docs/html-pattern-coverage.md)
> — the audit that maps each of Thariq's 20 HTML-effectiveness patterns to
> the primitives below. This SKILL.md is the *how*; the audit doc is the
> *what's-implemented-vs-missing* status.

## When to emit HTML vs Markdown

| Output | Format |
|--------|--------|
| Audit reports (deck, citations, manuscript) | **HTML** primary, MD fallback |
| Lit-arc narratives, reasoning chains | **HTML** primary |
| Project dossiers (SPEC-N) | **HTML** primary |
| Plan docs, exploration / SPEC docs | **HTML** primary |
| Weekly / state dashboards | **HTML** primary |
| Two-way editors (kanban, template, feature flags) | **HTML** only |
| Per-file frontmatter, KB notes, READMEs | **MD** (git-tracked, edited in Obsidian) |
| Throwaway scripts, one-line summaries | **MD** or stdout |
| Wiki concept articles | **MD** primary (Obsidian native), HTML render on demand |

The general rule: if a human opens the artifact in a browser, emit HTML; if a
human edits it in their text editor, keep MD.

## Choosing a primitive — quick reference

| You're trying to render | Use this primitive | Example consumer |
|---|---|---|
| Status summary with metric chips | `tldr_box` + `card_grid` | `vaultlab.report.weekly_status_html` |
| Side-by-side comparison (A vs B) | `compare_panel` | `vaultlab.report.approaches_compare_html` (2-up branch) |
| 3+ options with recommendation | `card_grid` with badge | `vaultlab.report.approaches_compare_html` (3+ branch) |
| Module dependency graph | `svg_arg_graph` | `vaultlab.report.state_dashboard_html` |
| Severity-ranked findings | `severity_card` | `vaultlab.slides.audit_html` |
| Per-row tabular data with status | `matrix_table` | `vaultlab.citations.report_html` |
| Time-ordered events | `timeline` | `vaultlab.workflows.reasoning_html` |
| Interactive deck (arrow-key nav) | `keynav_deck` | `vaultlab.slides.preview_html` |
| Two-way editor (drag/drop) | `kanban_board` | `vaultlab.report.editors.build_citation_triage_editor` |
| Editable template with diff | `template_editor` | `vaultlab.report.editors.build_deckplan_tuner` |
| Drill-down with details | `collapsible_step` | `vaultlab.kb.dossier_html` |
| Code/example/explanation tabs | `tabbed_block` | `vaultlab.kb.dossier_html` |
| Inline term definitions | `margin_glossary` | `vaultlab.slides.audit_html` |
| Boolean config knobs | grouped toggles + clipboard-copy | `vaultlab.report.feature_flag_editor` |
| Filter cards/rows by category | `filter_bar` | `vaultlab.slides.audit_html` |
| Inline status badge | `status_chip` | used inline by every consumer |
| Section wrapper with `<h2>` | `section` | used by every consumer |

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

## Component primitives

All in `vaultlab.report._components`, also accessible via
`from vaultlab.report import components as c`. All return HTML strings; all
interactive variants depend on the JS bundled by `html.py` (auto-included
unless `include_js=False`).

| Primitive | Purpose | Interactive? |
|-----------|---------|--------------|
| `tldr_box` | Accent box with headline summary | no |
| `status_chip` | Inline severity/status badge | no |
| `card_grid` | Auto-fill responsive grid of cards | no |
| `severity_card` | One card with title/body/badges/thumbnail/actions | no |
| `matrix_table` | Standard HTML table | no (sortable in v0.0.5) |
| `compare_panel` | Two-pane side-by-side | no |
| `collapsible_step` | Expandable `<details>` with optional file:line | yes (native) |
| `tabbed_block` | Tabbed code/content panes | yes |
| `timeline` | Vertical ts/label/body events | no |
| `svg_arg_graph` | Inline SVG nodes+edges with optional hot-path | no |
| `kanban_board` | Drag-and-drop columns, copy-as-markdown/JSON | yes |
| `template_editor` | `{{var}}` template w/ live preview on samples | yes |
| `margin_glossary` | Inline term/definition callout | no |
| `keynav_deck` | Arrow-key navigable slide deck | yes |
| `filter_bar` | Toggle visibility of cards/rows by data-filter-key | yes |
| `section` | Wrap content in `<section>` with optional H2 | no |

## Pattern catalog

The 20 patterns below correspond to Thariq Shihipar's HTML-effectiveness
gallery (`thariqs.github.io/html-effectiveness`). Every primitive needed
already exists in `vaultlab.report._components`; 12 patterns have a real
vaultlab consumer wired, 8 are listed with a candidate consumer noted.
For the authoritative status table, see
[`docs/html-pattern-coverage.md`](../../../docs/html-pattern-coverage.md).

### Exploration & planning

#### Pattern 1: Three Code Approaches

**Primitive(s):** `compare_panel`, `card_grid`, `severity_card` from `vaultlab.report._components`

**When to use:** rendering an "Approach A / B / C" decision view with pros, cons, and a recommendation — e.g. SPEC backlog dossiers, ADRs, `/grill-me` outputs.

**Example:**

```python
from vaultlab.report import Approach, ApproachesCompare, build_approaches_compare_html

html = build_approaches_compare_html(
    ApproachesCompare(
        title="How to parallelize the plan",
        approaches=[
            Approach(name="A: Subagent dispatch", summary="...", pros=["isolated"], cons=["overhead"], recommended=True),
            Approach(name="B: Sequential", summary="...", pros=["simple"], cons=["slow"]),
        ],
        decision_rationale="A wins on throughput for >3 independent tasks.",
    )
)
```

**Consumer using it:** `vaultlab.report.approaches_compare_html.build_approaches_compare_html` — 2-up via `compare_panel`, 3+ via `card_grid` with a `RECOMMENDED` chip.

**Reference output:** `examples/html_report_gallery/output/` (regenerated via `python examples/html_report_gallery/run_gallery.py`).

#### Pattern 2: Visual Design Directions

**Primitive(s):** `card_grid` with inline SVG thumbnails

**When to use:** rendering 3-4 design directions side-by-side with rendered previews (e.g. figure-contract draft mode showing alternate panel layouts).

**Example:**

```python
from vaultlab.report import components as c

html = c.card_grid([
    c.severity_card("Direction A: minimal", body='<svg viewBox="0 0 100 60">...</svg>', severity="neutral"),
    c.severity_card("Direction B: dense", body='<svg viewBox="0 0 100 60">...</svg>', severity="neutral"),
])
```

**Status:** Primitive available, no consumer wired yet. Candidate consumer: `vaultlab.figures.contract_html` (figure-contract draft preview).

#### Pattern 3: Implementation Plan

**Primitive(s):** `timeline`, `svg_arg_graph`, `tldr_box`

**When to use:** rendering a multi-phase plan with milestones, a dependency graph, and a headline summary — e.g. reasoning chains, crosstalk plans, multi-round agent outputs.

**Example:**

```python
from vaultlab.report import components as c

html = c.section(
    "Implementation plan",
    c.tldr_box(["3 phases", "6 milestones", "blocked by SPEC-F"]),
    c.timeline([
        ("2026-05-15", "Phase 1: spec frozen", "Dispatch contract written."),
        ("2026-05-22", "Phase 2: subagent harness", "Parallel dispatch lands."),
        ("2026-06-01", "Phase 3: cost-aware routing", "Task-weight defaults shipped."),
    ]),
)
```

**Consumer using it:** `vaultlab.workflows.reasoning_html.build_reasoning_report_html` — multi-round agent reasoning chains rendered as timelines with collapsible per-round details.

**Reference output:** `examples/html_report_gallery/output/reasoning.html`.

### Code review & understanding

#### Pattern 4: Annotated Pull Request

**Primitive(s):** `severity_card`, `margin_glossary`, `filter_bar`

**When to use:** rendering per-item critique with severity tags, drill-down evidence, and the ability to filter by severity — e.g. slide audits, citation audits, manuscript reviews.

**Example:**

```python
from vaultlab.report import components as c, render_report

sections = [
    c.section(
        "Per-slide verdicts",
        c.filter_bar([("All", "all"), ("Errors", "bad"), ("Warnings", "warn")],
                     target_selector=".vl-cards .vl-card"),
        c.card_grid([
            c.severity_card("Slide 3", body="Title overflow.", severity="warn",
                            filter_key="warn"),
            c.severity_card("Slide 7", body="Missing alt text.", severity="bad",
                            filter_key="bad"),
        ]),
    ),
]
html = render_report(title="Deck audit", sections=sections)
```

**Consumer using it:** `vaultlab.slides.audit_html.build_audit_report_html` (per-slide critique) + `vaultlab.citations.report_html.build_citation_audit_html` (per-citation cards).

**Reference output:** `examples/html_report_gallery/output/deck-audit.html`, `citation-audit.html`.

#### Pattern 5: PR Writeup for Reviewers

**Primitive(s):** `matrix_table`, `compare_panel`, `tldr_box`

**When to use:** rendering a release-note-style writeup of what changed, why, and how — e.g. v0.0.X changelog with before/after code excerpts and a coverage matrix.

**Example:**

```python
from vaultlab.report import components as c

html = c.section(
    "What changed",
    c.matrix_table(
        columns=["Module", "Before", "After"],
        rows=[
            ["vaultlab.report", "15 primitives", "16 primitives (+filter_bar)"],
            ["vaultlab.slides", "Markdown audit", "HTML audit"],
        ],
    ),
    c.compare_panel("Before", "<pre>...</pre>", "After", "<pre>...</pre>"),
)
```

**Status:** Primitive available, no consumer wired yet. Candidate consumer: `vaultlab.release.changelog_html` (v0.0.5 changelog HTML view).

#### Pattern 6: Module Map

**Primitive(s):** `svg_arg_graph`, `card_grid`

**When to use:** rendering a dependency or module graph of a codebase / pipeline / experiment, paired with legend cards explaining each node.

**Example:**

```python
from vaultlab.report import components as c

html = c.section(
    "vaultlab module map",
    c.svg_arg_graph(
        nodes=[
            {"id": "report", "x": 100, "y": 100, "label": "report"},
            {"id": "slides", "x": 300, "y": 100, "label": "slides"},
            {"id": "research", "x": 300, "y": 220, "label": "research"},
        ],
        edges=[("slides", "report"), ("research", "report")],
        hot_path=["slides", "report"],
    ),
)
```

**Consumer using it:** `vaultlab.report.state_dashboard_html.build_state_dashboard_html` — `vaultlab.*` package graph + legend cards.

**Reference output:** generated by `state_dashboard_html` consumer (see audit doc sub-goal 4.2).

### Design & prototypes

#### Pattern 7: Living Design System

**Out of scope.** See [Out of scope](#out-of-scope) below — vaultlab has only 2 palettes; a token-swatch HTML is overkill for so few tokens.

#### Pattern 8: Component Variants

**Primitive(s):** `card_grid` in dense mode

**When to use:** rendering an inventory of component variants with rendered thumbnails — e.g. slide-layout inventory showing title+bullets / figure-only / divider / etc.

**Example:**

```python
from vaultlab.report import components as c

html = c.card_grid([
    c.severity_card("title_bullets", body='<img src="layouts/title_bullets.png">'),
    c.severity_card("figure_only", body='<img src="layouts/figure_only.png">'),
    c.severity_card("divider", body='<img src="layouts/divider.png">'),
], min_width=200)
```

**Status:** Primitive available, no consumer wired yet. Candidate consumer: `vaultlab.slides.layout_inventory_html` (slide-layout catalog).

#### Pattern 9: Animation Sandbox

**Out of scope.** See [Out of scope](#out-of-scope) below — annotation timing should "just work" per the slide hard rules; not a user-tunable surface.

#### Pattern 10: Clickable Flow

**Primitive(s):** `keynav_deck`

**When to use:** rendering an interactive walkthrough of a multi-step flow (clickable arrows or keyboard navigation between states) — e.g. deck preview, pipeline phase walkthrough.

**Example:**

```python
from vaultlab.report import components as c

html = c.keynav_deck([
    ("Step 1", "<p>Survey papers</p>"),
    ("Step 2", "<p>Extract findings</p>"),
    ("Step 3", "<p>Write narrative</p>"),
])
```

**Consumer using it:** `vaultlab.slides.preview_html.build_deck_preview_html` — arrow-key navigable HTML preview of generated `.pptx` decks.

**Reference output:** `examples/html_report_gallery/output/deck-preview.html`.

### Diagrams & presentations

#### Pattern 11: SVG Figure Sheet

**Primitive(s):** `svg_arg_graph` + clipboard-copy actions

**When to use:** rendering a library of stand-alone SVG schematics with copy-as-SVG buttons — e.g. mechanism diagrams, pathway sketches, generic-shape inventory.

**Example:**

```python
from vaultlab.report import components as c

svg = c.svg_arg_graph(
    nodes=[{"id": "x", "x": 100, "y": 100, "label": "X"},
           {"id": "y", "x": 300, "y": 100, "label": "Y"}],
    edges=[("x", "y")],
)
html = c.card_grid([
    c.severity_card("Signaling cascade A", body=svg,
                    actions=[("Copy SVG", svg)]),
])
```

**Status:** Primitive available, used inline by `vaultlab.research.litarc_html` (citation graphs) but not as a standalone schematic library. Candidate consumer: `vaultlab.figures.svg_gallery_html` (mechanism-diagram library).

#### Pattern 12: Annotated Flowchart

**Primitive(s):** `svg_arg_graph`, `collapsible_step`

**When to use:** rendering a flowchart where each node opens a drill-down explainer when clicked or expanded — e.g. research-pipeline phase explainer.

**Example:**

```python
from vaultlab.report import components as c

html = c.section(
    "Research pipeline phases",
    c.svg_arg_graph(
        nodes=[{"id": "p1", "x": 80, "y": 80, "label": "Survey"},
               {"id": "p2", "x": 240, "y": 80, "label": "Reason"},
               {"id": "p3", "x": 400, "y": 80, "label": "Write"}],
        edges=[("p1", "p2"), ("p2", "p3")],
    ),
    c.collapsible_step("Phase 1: Survey", "<p>Pulls Tier-A papers...</p>"),
    c.collapsible_step("Phase 2: Reason", "<p>Adaptive multi-agent...</p>"),
)
```

**Status:** Primitive available, no consumer wired yet. Candidate consumer: `vaultlab.workflows.pipeline_explainer_html` (research-pipeline phase walkthrough).

#### Pattern 13: Arrow-Key Slide Deck

**Primitive(s):** `keynav_deck`

**When to use:** rendering a generated `.pptx` (or any structured slide list) as a browser-navigable preview before exporting binary.

**Example:**

```python
from vaultlab.report import components as c

html = c.keynav_deck([
    ("Title", "<h2>Lit-arc: SARS-CoV-2 spike</h2>"),
    ("Why", "<p>Mechanism remains contested.</p>"),
    ("Take-home", "<blockquote>Spike + ACE2 = entry.</blockquote>"),
])
```

**Consumer using it:** `vaultlab.slides.preview_html.build_deck_preview_html` (same consumer as Pattern #10).

**Reference output:** `examples/html_report_gallery/output/deck-preview.html`.

### Research & learning

#### Pattern 14: How a Feature Works

**Primitive(s):** `tldr_box`, `collapsible_step`, `tabbed_block`, `margin_glossary`

**When to use:** rendering a self-contained explainer of a feature / paper / KB concept with a headline summary, drill-downs, multi-perspective tabs, and inline glossary terms.

**Example:**

```python
from vaultlab.report import components as c

html = c.section(
    "How abstract_recall works",
    c.tldr_box("Cascade through 6 sources, prefer corpus over network."),
    c.tabbed_block({
        "Overview": "<p>...</p>",
        "Code": "<pre>from vaultlab.research import abstract_recall</pre>",
        "Cascade order": "<ol><li>corpus</li><li>KB stub frontmatter</li>...</ol>",
    }),
    c.collapsible_step("Why CrossRef before PubMed?",
                       "<p>CrossRef is faster; PubMed has more abstracts for Cell/Elsevier.</p>"),
    c.margin_glossary("DOI", "Digital Object Identifier — canonical paper ID."),
)
```

**Consumer using it:** `vaultlab.kb.dossier_html.build_dossier_report_html` — 9-section project dossier with tabbed view + freshness badge.

**Reference output:** `examples/html_report_gallery/output/dossier.html`.

#### Pattern 15: Concept Explainer

**Primitive(s):** `svg_arg_graph` with `hot_path`, plus custom click-to-highlight JS

**When to use:** rendering an interactive mechanism diagram where clicking a node or row highlights the corresponding edges in an embedded SVG — e.g. lit-arc CCI heatmap with click-to-highlight, biology mechanism walkthrough.

**Example:**

```python
from vaultlab.report import components as c

html = c.svg_arg_graph(
    nodes=[
        {"id": "macrophage", "x": 100, "y": 100, "label": "Macrophage"},
        {"id": "tcell", "x": 300, "y": 100, "label": "T cell"},
        {"id": "ifn", "x": 200, "y": 220, "label": "IFN-γ"},
    ],
    edges=[("macrophage", "ifn"), ("ifn", "tcell")],
    hot_path=["macrophage", "ifn", "tcell"],
)
```

**Consumer using it:** `vaultlab.report.state_dashboard_html.build_state_dashboard_html` — optional inline explainer panel with hot-path highlighting (composite consumer covering #6 + #15).

#### Pattern 16: Weekly Status

**Primitive(s):** `tldr_box`, `card_grid`, `severity_card`

**When to use:** rendering a weekly / state status update with TL;DR + metrics + shipped / in-flight / blocker grids — e.g. `system-state-<date>.md` HTML view, `/weekly` output.

**Example:**

```python
from vaultlab.report import WeeklyStatusReport, build_weekly_status_html

html = build_weekly_status_html(WeeklyStatusReport(
    week_label="Week of 2026-05-15",
    project="vaultlab",
    tldr="HTML pattern coverage closed at 12/20 with 4 new consumers.",
    shipped=[("approaches_compare_html", "Pattern #1 wired."),
             ("feature_flag_editor", "Pattern #19 wired.")],
    in_flight=[("state_dashboard_html", "Patterns #6 + #15 in review.")],
    blockers=[],
    metrics={"commits": "12", "tests": "1734 passing"},
))
```

**Consumer using it:** `vaultlab.report.weekly_status_html.build_weekly_status_html` — TL;DR + metrics + shipped/in-flight/blocker grids.

### Reports

#### Pattern 17: Incident Timeline

**Primitive(s):** `timeline`, `tabbed_block`

**When to use:** rendering a postmortem with chronologically ordered events and per-phase drill-down (what happened / what we tried / what we learned).

**Example:**

```python
from vaultlab.report import components as c

html = c.section(
    "Incident: pipeline OOM on 2026-05-13",
    c.timeline([
        ("14:02", "Detection", "Batch reader killed by OOM."),
        ("14:15", "Mitigation", "Switched to streaming reader."),
        ("14:40", "Resolution", "Pipeline resumed; 150 papers processed."),
    ]),
    c.tabbed_block({
        "What happened": "<p>...</p>",
        "What we tried": "<p>...</p>",
        "What we learned": "<p>...</p>",
    }),
)
```

**Status:** Primitive available, no consumer wired yet. Candidate consumer: `vaultlab.workflows.postmortem_html` (pipeline postmortem HTML).

### Custom editors (two-way HTML)

#### Pattern 18: Ticket Triage Board

**Primitive(s):** `kanban_board`

**When to use:** rendering a drag-and-drop board where the user re-buckets items and exports the new mapping as JSON / markdown to paste into the next prompt — e.g. citation accept/reject piles, slide reorder, paper triage.

**Example:**

```python
from vaultlab.report.editors import build_citation_triage_editor

html = build_citation_triage_editor(
    citations=[
        {"authors": "Smith et al.", "year": "2024", "claim": "Mechanism X is contested",
         "status": "verified_fulltext"},
        {"authors": "Jones et al.", "year": "2023", "claim": "Mechanism Y is novel",
         "status": "unverified"},
    ],
    title="Citation triage — lit-arc 2026-05-15",
)
```

**Consumer using it:** `vaultlab.report.editors.build_citation_triage_editor` + `build_slide_reorder_editor`.

**Reference output:** `examples/html_report_gallery/output/citation-triage.html`, `slide-reorder.html`.

#### Pattern 19: Feature Flag Editor

**Primitive(s):** grouped HTML toggles + clipboard-copy actions (composed in `feature_flag_editor`)

**When to use:** rendering a structured boolean config (e.g. dispatch routing, pipeline phase toggles, figure-recipe parameters) as a single-file editor where the user flips checkboxes and copies the diff back into a JSON config.

**Example:**

```python
from vaultlab.report import FeatureFlagConfig, FlagGroup, build_feature_flag_editor

html = build_feature_flag_editor(FeatureFlagConfig(
    title="Vaultlab dispatch routing",
    groups=[
        FlagGroup(title="Pipeline phases", flags=[
            ("verify", True, "Run data verification phase."),
            ("reason", True, "Run multi-agent reasoning phase."),
            ("write", False, "Auto-emit manuscript draft (manual gate by default)."),
        ]),
    ],
))
```

**Consumer using it:** `vaultlab.report.feature_flag_editor.build_feature_flag_editor` — grouped toggles + Copy diff / Copy current / Copy defaults.

#### Pattern 20: Prompt Tuner

**Primitive(s):** `template_editor`

**When to use:** rendering a `{{var}}` template that the user edits live with 2-3 sample contexts streaming the rendered output — e.g. deck-plan template tuner, prompt-template editor, message-skeleton tuner.

**Example:**

```python
from vaultlab.report.editors import build_deckplan_tuner

html = build_deckplan_tuner(
    template="Slide {{n}}: {{title}}\n  - {{bullet1}}\n  - {{bullet2}}",
    samples=[
        {"n": "1", "title": "Why", "bullet1": "Mechanism contested",
         "bullet2": "Therapeutic gap"},
        {"n": "2", "title": "Approach", "bullet1": "scRNA-seq",
         "bullet2": "CODEX validation"},
    ],
)
```

**Consumer using it:** `vaultlab.report.editors.build_deckplan_tuner`.

**Reference output:** `examples/html_report_gallery/output/deckplan-tuner.html`.

## Out of scope

Two patterns from Thariq's gallery are deliberately not wired into vaultlab:

- **#7 Living Design System (token swatches)** — vaultlab has 2 palettes
  (`NMI_PASTEL` + `Nature-2026`). A token-swatch HTML is overkill for so few
  tokens; this pattern is for design systems with 100+ tokens.
- **#9 Animation Sandbox** — annotation timing is not a tunable users want
  to fiddle with; vaultlab's default annotation timing should "just work"
  per the slide hard rules (`feedback_slide_hard_rules`).

Rationale source: [`docs/html-pattern-coverage.md`](../../../docs/html-pattern-coverage.md).

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
at 768px. `@media print` hides export bars + filter chrome.

## Anti-patterns

Do not:

- Inline scripts that load external JS (CDN, jsDelivr, etc.). Reports stay
  archive-friendly and offline-readable.
- Render unescaped user content. `_components` escapes labels but trusts
  pre-rendered HTML in `body` / `content` positions — callers must
  escape there.
- Bake the rendered date or git SHA into the section content (looks like
  a diff on re-runs). Use the bundled footer or the `meta` slot in the
  header instead.
- Build framework-style component hierarchies. These are flat string
  functions, on purpose.
- Invent a new primitive when an existing one composes. The audit
  ([`docs/html-pattern-coverage.md`](../../../docs/html-pattern-coverage.md))
  found zero missing primitives across all 20 patterns; if a new consumer
  feels like it needs new infrastructure, compose the existing ones first.

## Test strategy

`tests/test_vaultlab_report/test_html.py` snapshot-tests:

- A minimal report end-to-end
- Each of the primitives in isolation
- That `render_report` output round-trips through `html.parser` cleanly
- That `write_report` materializes a readable file

Per-consumer tests live next to each consumer module:

- `tests/test_vaultlab_slides/test_audit_html.py`
- `tests/test_vaultlab_citations/test_report_html.py`
- `tests/test_vaultlab_workflows/test_reasoning_html.py`
- `tests/test_vaultlab_kb/test_dossier_html.py`
- `tests/test_vaultlab_slides/test_preview_html.py`
- `tests/test_vaultlab_research/test_litarc_html.py`
- `tests/test_vaultlab_report/test_weekly_status_html.py`
- `tests/test_vaultlab_report/test_state_dashboard_html.py`
- `tests/test_vaultlab_report/test_approaches_compare_html.py`
- `tests/test_vaultlab_report/test_feature_flag_editor.py`
- `tests/test_vaultlab_report/test_editors.py`

Tests do not render in a browser. Visual verification is a manual step
the first time a new consumer is wired (open the file from
`examples/html_report_gallery/output/`).

## Related

- [`docs/html-pattern-coverage.md`](../../../docs/html-pattern-coverage.md)
  — coverage audit (status per pattern, bidirectional link).
- `examples/html_report_gallery/` — gallery script + reference outputs for
  every shipped consumer.
- `vaultlab/Output/Plans/html-and-nature-skills-2026-05-12.html` — the
  v0.0.4 plan that drove this system.
- `vaultlab/INSPIRATIONS.md` — attribution to `thariqs/html-effectiveness`
  + Yuan Yizhe / nature-skills.
- `feedback_doc_persistence_baked_in` — features must persist as code, not
  one-off artifacts; this primitive is the persistence vehicle for HTML
  output across vaultlab.
