# vaultlab.report

Turns any vaultlab result — an audit, a lit-arc, a reasoning chain, a status update, a triage board — into a single self-contained HTML file you can open in a browser, email, or read on your phone.

Plain-language overview: `G:/My Drive/Knowledge/vaultlab/Wiki/Concepts/vaultlab-subsystems.md`. Design rationale + the full pattern catalog live in this package's [`SKILL.md`](SKILL.md). (As of this writing `docs/architecture.md` does not yet have a `vaultlab.report` section.)

## What it is

When an agent produces complex work — a per-slide deck audit, a citation triage, a weekly status, a multi-round reasoning transcript — markdown is a lossy way to hand it back to a human: no tables that hold up, no SVG diagrams, no drag-and-drop, no copy-as-JSON paste-back. `vaultlab.report` is the answer to that. It's a **deep module**: one small entrypoint (`render_report`) plus a flat library of HTML component functions, and on top of those, a set of typed "consumer" renderers for the specific artifact shapes vaultlab produces. The output is always one `.html` document with inline CSS and vanilla JS — no framework, no CDN, no external assets — so it stays archive-friendly and offline-readable.

Everywhere else in vaultlab that emits a browser-readable report (slide audits, citation audits, project dossiers, deck previews, lit-arc narratives) ultimately renders through this package. The design follows Thariq Shihipar's "The Unreasonable Effectiveness of HTML" (Anthropic, 2026) — see `INSPIRATIONS.md`.

## Public surface

### Core renderer

- `render_report` — wrap a list of pre-rendered HTML section strings into a complete, self-contained HTML document. Levers (all keyword-only): `eyebrow` (legacy small label, auto-split into the breadcrumb), `subtitle` (italic serif lede), `meta` (free-form header band — dates, repo refs), `breadcrumb` (a list of trail segments or a single string), `chips` (pre-rendered `status_chip` strings for the header), `version` + `screen_label` (masthead / tooling labels), `theme` (`"light" | "dark" | "auto"`; a runtime toggle persists the user's choice in `localStorage` regardless), `include_js` (set `False` for a static, JS-free page), `footer`, and `lang`. The masthead always stamps an `offline` badge.
- `write_report` — same as `render_report` but writes the result to a path (creating parent dirs) and returns the resolved `Path`.
- `Theme` — the `"light" | "dark" | "auto"` literal accepted by `render_report`.
- `components` — the flat library of 17 HTML building blocks (re-exported as a module; `from vaultlab.report import components as c`): `status_chip`, `stats_row`, `tldr_box`, `severity_card`, `card_grid`, `matrix_table`, `compare_panel`, `collapsible_step`, `tabbed_block`, `timeline`, `svg_arg_graph`, `kanban_board`, `template_editor`, `margin_glossary`, `keynav_deck`, `filter_bar`, and `section`. All return HTML strings. Also exported here: the `Severity` literal and the `TimelineEvent` dataclass. `status_chip` carries a colorblind-safe glyph and accepts the canonical levels `pass` / `warn` / `fail` / `info` / `flag` / `neutral` — legacy `good` / `bad` are still accepted and normalised to `pass` / `fail`. `matrix_table`'s `sortable=` flag is reserved (not yet wired).
- `editors` — the two-way (drag/drop, copy-as-JSON / copy-as-markdown) editor builders (re-exported as a module). Each has a `build_*` (returns the HTML string) and a `write_*` (writes to disk) variant: `build_slide_reorder_editor` / `write_slide_reorder_editor`, `build_citation_triage_editor` / `write_citation_triage_editor`, `build_deckplan_tuner` / `write_deckplan_tuner`. (The editor `write_*` helpers, unlike the typed consumers below, do not drop a provenance receipt.)

### Universal dispatcher

- `render_artifact_html` — auto-detect the shape of a vaultlab result and route it to the matching renderer, returning an HTML string. Detection is by dataclass type first, then by a "first-match-wins" set of key probes (e.g. `rounds`+`final_output` → reasoning; `citations`+`by_status` → citation; `narrative`+`papers` → litarc; `project_slug`+`sections` → dossier; `reviewer`+`comments` → response-letter; `approaches`+`decision_rationale` → approaches-compare; and so on). `kind=` forces a specific renderer; `**extra` kwargs forward to the underlying consumer (e.g. `topic=` for litarc).
- `write_artifact_html` — same dispatch, but writes the file and also drops a provenance receipt next to it (via `vaultlab.provenance.write_receipts`).
- `ArtifactKind` — the literal of the **13** recognized kinds the dispatcher routes to: the six "external" shapes other packages produce (`deck-audit`, `litarc`, `reasoning`, `citation`, `dossier`, `response-letter`) plus seven of this package's typed consumers (`weekly-status`, `state-dashboard`, `approaches-compare`, `visual-designs`, `component-variants`, `svg-figure-sheet`, `feature-flag-editor`). Note the `flowchart`, `incident-timeline`, and `pr-writeup` consumers are **not** auto-detected — call their `build_*` / `write_*` functions directly.
- `UnknownArtifact` — raised when the dispatcher can't infer the shape (and no `kind=` was given), or when a forced `kind` has no renderer.

### Typed consumers (one dataclass + `build_*`/`write_*` pair each)

Each consumer takes a small dataclass describing the content and renders a purpose-shaped report. Every `write_*` here writes the `.html` and (best-effort, never blocking the HTML) a `vaultlab.provenance` receipt. Empty lists / dicts gracefully omit their section, so partial inputs still render a well-formed page:

- `WeeklyStatusReport` + `build_weekly_status_html` / `write_weekly_status_html` — TL;DR + a metrics card-grid + shipped (good) / in-flight (warn) / blocker (bad) severity grids + a carryover-for-next-week bullet list.
- `StateDashboard` + `build_state_dashboard_html` / `write_state_dashboard_html` — a project-state page (TL;DR, metrics, shipped / in-flight / blockers) plus a `vaultlab.*` module-dependency SVG graph laid out on a ring (`module_map` triples → `svg_arg_graph` + a legend card-grid) and an optional `concept_explainer` panel that draws a mechanism diagram with hot-path highlighting.
- `ApproachesCompare` + `Approach` + `build_approaches_compare_html` / `write_approaches_compare_html` — "Approach A / B / C" decision view with per-approach summary, pros, cons, an optional `estimated_effort` chip, and a `recommended` flag (RECOMMENDED badge + good accent). Two approaches render 2-up as a `compare_panel`; three+ as a `card_grid`. Optional `context` preamble + a closing `decision_rationale` "Why" box.
- `VisualDesigns` + `DesignOption` + `build_visual_designs_html` / `write_visual_designs_html` — 3–4 design directions side-by-side, each with a one-line rationale, an inline-SVG colour-swatch strip (colours validated against an injection-safe regex, bad values fall back to `#cccccc`), the literal colour codes, an optional `archetype` chip, and an optional trusted `inline_svg_preview` layout sketch.
- `ComponentInventory` + `ComponentVariant` + `build_component_variants_html` / `write_component_variants_html` — a contact-sheet inventory of component variants, each with an optional trusted `preview_html` thumbnail + tag chips. `group_by_tag` (default on) buckets variants into one section per first tag; off renders one flat grid.
- `FigureSheet` + `Schematic` + `build_svg_figure_sheet_html` / `write_svg_figure_sheet_html` — a library of stand-alone inline-SVG schematics, each in a framed block with a description, a copy-as-SVG button, and related-concept cross-ref pills.
- `Flowchart` + `FlowStep` + `build_flowchart_html` / `write_flowchart_html` — a left-to-right SVG flow diagram (entry step highlighted via hot-path) over a per-step `collapsible_step` list that drills into the step's description, typical duration, and known failure modes; unknown successors are dropped so partial graphs still render.
- `IncidentReport` + `IncidentChecklist` + `TimelineEntry` + `build_incident_timeline_html` / `write_incident_timeline_html` — a postmortem with an OPEN/RESOLVED + duration + per-severity chip band, then a tabbed block (chronological Timeline / Log excerpts / Followups checklist). Per-entry severity (`info`/`warning`/`error`/`resolution`) drives the chip colour.
- `PRWriteup` + `CommitEntry` + `FileChange` + `build_pr_writeup_html` / `write_pr_writeup_html` — a release-note / session writeup: TL;DR, a breaking-changes block, an optional before/after test-summary `compare_panel`, a per-file change `matrix_table` (rolled up across commits when no top-level file list is supplied), and per-commit `collapsible_step` detail.
- `FeatureFlagConfig` + `FlagGroup` + `build_feature_flag_editor` / `write_feature_flag_editor` — a structured boolean config as a single-file editor; grouped toggle cards plus Copy-defaults / Copy-current-as-JSON / Copy-diff-from-defaults buttons (the diff button emits only the flags the user changed, via a small embedded read-only script).

## How it fits

`vaultlab.report` sits at the **output edge** of the pipeline — it consumes results that other packages have already produced and turns them into a browser artifact. It reads nothing from the KB itself; its inputs are the in-memory dicts / dataclasses handed to it (a slide-audit result, a `CrosstalkResult`, a citation audit, a project dossier). Its outputs are `.html` files, typically written to a project's `Output/` folder.

It is the shared rendering backend for the many `*_html` consumers across the codebase — `vaultlab.slides.audit_html`, `vaultlab.slides.preview_html`, `vaultlab.citations.report_html`, `vaultlab.research.litarc_html`, `vaultlab.workflows.reasoning_html`, `vaultlab.kb.dossier_html`, `vaultlab.manuscript.respond_html` — all build their sections from this package's components and wrap them with `render_report`. The `render_artifact_html` dispatcher is the programmatic twin of the `/audit-html` slash command: hand it a result of (almost) any of these shapes and it figures out which renderer to call. `write_artifact_html` additionally writes a provenance receipt, keeping the "no silent outputs" contract.

Several slash commands route straight into this package: `/audit-html` (the dispatcher), `/state-dashboard` (→ `write_state_dashboard_html`), `/reorder-slides` (→ `editors.write_slide_reorder_editor`), and `/triage-citations` (→ `editors.build_citation_triage_editor`). There is no `vaultlab report` CLI subcommand — the package is reached via these commands, via the `*_html` consumers above, or by importing it directly. (The `vaultlab slides review --html` CLI path reuses the same visual system but renders through `vaultlab.slides.self_review`.)

The whole page shares one bundled visual system — a "printed lab notebook on warm paper" stylesheet (warm off-white paper, a single fountain-pen ink-blue accent, a colorblind-safe `pass`/`warn`/`fail`/`info`/`flag` status palette, hairline rules), with a dark theme on `[data-theme="dark"]` and a runtime toggle. The CSS exposes its tokens as CSS custom properties (canonical names `--paper*`, `--ink*`, `--rule*`, `--accent*`, `--pass`/`--warn`/`--fail`/`--info`/`--flag`), and a legacy-alias block keeps older inline-style names (`--bg`, `--ink-soft`, `--muted`, `--line`, `--good`/`--bad`) pointing at the same values so un-migrated consumers keep working.

## What it does NOT do

- It does **not** run analysis, search literature, or generate the content — it only formats results other packages compute. If a renderer is missing data, that's the caller's bug, not this package's.
- It does **not** load external assets. No CDN, no web fonts, no remote JS — every report is offline-readable by design. PRs that inline a `<script src=...>` are an anti-pattern (see `SKILL.md`).
- It does **not** escape pre-rendered HTML you pass into `body` / `content` slots. Labels are escaped; rich content you hand in is trusted verbatim, so the caller must escape any untrusted text there.
- It is **not** a React-style component framework. The components are flat string-returning functions on purpose; don't build component hierarchies, and compose existing primitives before inventing a new one.

## Files

- `__init__.py` — slim barrel; re-exports the core renderer, `components`, `editors`, the dispatcher, and every typed consumer.
- `html.py` — the `render_report` / `write_report` core; assembles the page shell from `_css.py` + `_js.py`.
- `_components.py` — the flat 17-function component library (`status_chip`, `stats_row`, `tldr_box`, `card_grid`, `severity_card`, `matrix_table`, `compare_panel`, `collapsible_step`, `tabbed_block`, `timeline`, `svg_arg_graph`, `kanban_board`, `template_editor`, `margin_glossary`, `keynav_deck`, `filter_bar`, `section`) plus the `Severity` literal and `TimelineEvent` dataclass.
- `_css.py` / `_js.py` — the bundled stylesheet and interactive JS (theme toggle, tabs, filters, drag/drop, clipboard copy).
- `dispatch.py` — `render_artifact_html` / `write_artifact_html`: shape detection + routing to the right consumer.
- `editors.py` — two-way editors (kanban reorder, citation triage, deck-plan template tuner).
- `weekly_status_html.py`, `state_dashboard_html.py`, `approaches_compare_html.py`, `visual_designs_html.py`, `component_variants_html.py`, `svg_figure_sheet_html.py`, `flowchart_html.py`, `incident_timeline_html.py`, `pr_writeup_html.py`, `feature_flag_editor.py` — the typed consumer renderers.
- `SKILL.md` — design rationale, the format-choice table (HTML vs MD), a "which primitive for which job" quick reference, and the full 20-pattern catalog mapped to consumers.

## See also

- [`SKILL.md`](SKILL.md) — the deep how-to for this package (read this when wiring a new consumer), including the format-choice table (HTML vs MD), the "which primitive for which job" quick reference, and the full 20-pattern catalog.
- `docs/html-pattern-coverage.md` — the audit mapping each HTML-effectiveness pattern to its vaultlab consumer (implemented vs candidate).
- `examples/html_report_gallery/` — the gallery script + reference HTML outputs for every shipped consumer.
- Slash commands that route here: `/audit-html`, `/state-dashboard`, `/reorder-slides`, `/triage-citations`.
- Consumer READMEs / modules: `vaultlab.slides` (audit + preview), `vaultlab.citations` (citation audit), `vaultlab.research` (lit-arc), `vaultlab.workflows` (reasoning), `vaultlab.kb` (dossier), `vaultlab.manuscript` (response letter).
- `INSPIRATIONS.md` — attribution to Thariq Shihipar's `html-effectiveness` gallery.
