# vaultlab.report

Turns any vaultlab result — an audit, a lit-arc, a reasoning chain, a status update, a triage board — into a single self-contained HTML file you can open in a browser, email, or read on your phone.

Plain-language overview: `G:/My Drive/Knowledge/vaultlab/Wiki/Concepts/vaultlab-subsystems.md`. Design rationale + the full pattern catalog live in this package's [`SKILL.md`](SKILL.md). (As of this writing `docs/architecture.md` does not yet have a `vaultlab.report` section.)

## What it is

When an agent produces complex work — a per-slide deck audit, a citation triage, a weekly status, a multi-round reasoning transcript — markdown is a lossy way to hand it back to a human: no tables that hold up, no SVG diagrams, no drag-and-drop, no copy-as-JSON paste-back. `vaultlab.report` is the answer to that. It's a **deep module**: one small entrypoint (`render_report`) plus a flat library of HTML component functions, and on top of those, a set of typed "consumer" renderers for the specific artifact shapes vaultlab produces. The output is always one `.html` document with inline CSS and vanilla JS — no framework, no CDN, no external assets — so it stays archive-friendly and offline-readable.

Everywhere else in vaultlab that emits a browser-readable report (slide audits, citation audits, project dossiers, deck previews, lit-arc narratives) ultimately renders through this package. The design follows Thariq Shihipar's "The Unreasonable Effectiveness of HTML" (Anthropic, 2026) — see `INSPIRATIONS.md`.

## Public surface

### Core renderer

- `render_report` — wrap a list of pre-rendered HTML section strings into a complete, self-contained HTML document (masthead, breadcrumb, header, sections, footer, optional dark-theme toggle).
- `write_report` — same as `render_report` but writes the result to a path and returns it.
- `Theme` — the `"light" | "dark" | "auto"` literal accepted by `render_report`.
- `components` — the flat library of HTML building blocks (re-exported as a module; `from vaultlab.report import components as c`). Includes `tldr_box`, `status_chip`, `card_grid`, `severity_card`, `matrix_table`, `compare_panel`, `collapsible_step`, `tabbed_block`, `timeline`, `svg_arg_graph`, `kanban_board`, `template_editor`, `margin_glossary`, `keynav_deck`, `filter_bar`, `stats_row`, and `section`. All return HTML strings.
- `editors` — the two-way (drag/drop, copy-as-JSON) editor builders (re-exported as a module): `build_slide_reorder_editor`, `build_citation_triage_editor`, `build_deckplan_tuner`.

### Universal dispatcher

- `render_artifact_html` — auto-detect the shape of a vaultlab result (deck audit, lit-arc, reasoning chain, citation audit, dossier, response letter, plus the typed consumers below) and route it to the matching renderer, returning an HTML string. Pass `kind=` to force a specific renderer.
- `write_artifact_html` — same dispatch, but writes the file and also drops a provenance receipt next to it.
- `ArtifactKind` — the literal of recognized artifact kinds the dispatcher routes to.
- `UnknownArtifact` — raised when the dispatcher can't infer the shape (and no `kind=` was given).

### Typed consumers (one dataclass + `build_*`/`write_*` pair each)

Each consumer takes a small dataclass describing the content and renders a purpose-shaped report:

- `WeeklyStatusReport` + `build_weekly_status_html` / `write_weekly_status_html` — TL;DR + metrics + shipped / in-flight / blocker grids.
- `StateDashboard` + `build_state_dashboard_html` / `write_state_dashboard_html` — project state with a `vaultlab.*` module-dependency SVG graph.
- `ApproachesCompare` + `Approach` + `build_approaches_compare_html` / `write_approaches_compare_html` — "Approach A / B / C" decision view with pros, cons, and a recommendation (2-up as a compare panel, 3+ as a card grid).
- `VisualDesigns` + `DesignOption` + `build_visual_designs_html` / `write_visual_designs_html` — 3–4 design directions side-by-side with rendered previews.
- `ComponentInventory` + `ComponentVariant` + `build_component_variants_html` / `write_component_variants_html` — an inventory of component variants with thumbnails.
- `FigureSheet` + `Schematic` + `build_svg_figure_sheet_html` / `write_svg_figure_sheet_html` — a library of stand-alone SVG schematics with copy-as-SVG buttons.
- `Flowchart` + `FlowStep` + `build_flowchart_html` / `write_flowchart_html` — an annotated flowchart whose nodes open drill-down explainers.
- `IncidentReport` + `IncidentChecklist` + `TimelineEntry` + `build_incident_timeline_html` / `write_incident_timeline_html` — a postmortem with a chronological timeline + per-phase drill-down.
- `PRWriteup` + `CommitEntry` + `FileChange` + `build_pr_writeup_html` / `write_pr_writeup_html` — a release-note-style writeup of what changed, why, and how.
- `FeatureFlagConfig` + `FlagGroup` + `build_feature_flag_editor` / `write_feature_flag_editor` — a structured boolean config as a single-file editor; flip toggles, copy the diff back as JSON.

## How it fits

`vaultlab.report` sits at the **output edge** of the pipeline — it consumes results that other packages have already produced and turns them into a browser artifact. It reads nothing from the KB itself; its inputs are the in-memory dicts / dataclasses handed to it (a slide-audit result, a `CrosstalkResult`, a citation audit, a project dossier). Its outputs are `.html` files, typically written to a project's `Output/` folder.

It is the shared rendering backend for the many `*_html` consumers across the codebase — `vaultlab.slides.audit_html`, `vaultlab.slides.preview_html`, `vaultlab.citations.report_html`, `vaultlab.research.litarc_html`, `vaultlab.workflows.reasoning_html`, `vaultlab.kb.dossier_html`, `vaultlab.manuscript.respond_html` — all build their sections from this package's components and wrap them with `render_report`. The `render_artifact_html` dispatcher is the programmatic twin of the `/audit-html` slash command: hand it a result of (almost) any of these shapes and it figures out which renderer to call. `write_artifact_html` additionally writes a provenance receipt, keeping the "no silent outputs" contract.

## What it does NOT do

- It does **not** run analysis, search literature, or generate the content — it only formats results other packages compute. If a renderer is missing data, that's the caller's bug, not this package's.
- It does **not** load external assets. No CDN, no web fonts, no remote JS — every report is offline-readable by design. PRs that inline a `<script src=...>` are an anti-pattern (see `SKILL.md`).
- It does **not** escape pre-rendered HTML you pass into `body` / `content` slots. Labels are escaped; rich content you hand in is trusted verbatim, so the caller must escape any untrusted text there.
- It is **not** a React-style component framework. The components are flat string-returning functions on purpose; don't build component hierarchies, and compose existing primitives before inventing a new one.

## Files

- `__init__.py` — slim barrel; re-exports the core renderer, `components`, `editors`, the dispatcher, and every typed consumer.
- `html.py` — the `render_report` / `write_report` core; assembles the page shell from `_css.py` + `_js.py`.
- `_components.py` — the flat component library (`status_chip`, `card_grid`, `severity_card`, `timeline`, `svg_arg_graph`, `kanban_board`, `template_editor`, `filter_bar`, `section`, …).
- `_css.py` / `_js.py` — the bundled stylesheet and interactive JS (theme toggle, tabs, filters, drag/drop, clipboard copy).
- `dispatch.py` — `render_artifact_html` / `write_artifact_html`: shape detection + routing to the right consumer.
- `editors.py` — two-way editors (kanban reorder, citation triage, deck-plan template tuner).
- `weekly_status_html.py`, `state_dashboard_html.py`, `approaches_compare_html.py`, `visual_designs_html.py`, `component_variants_html.py`, `svg_figure_sheet_html.py`, `flowchart_html.py`, `incident_timeline_html.py`, `pr_writeup_html.py`, `feature_flag_editor.py` — the typed consumer renderers.
- `SKILL.md` — design rationale, the format-choice table (HTML vs MD), a "which primitive for which job" quick reference, and the full 20-pattern catalog mapped to consumers.

## See also

- [`SKILL.md`](SKILL.md) — the deep how-to for this package (read this when wiring a new consumer).
- `docs/html-pattern-coverage.md` — the audit mapping each HTML-effectiveness pattern to its vaultlab consumer (implemented vs candidate).
- `examples/html_report_gallery/` — the gallery script + reference HTML outputs for every shipped consumer.
- Consumer READMEs / modules: `vaultlab.slides` (audit + preview), `vaultlab.citations` (citation audit), `vaultlab.research` (lit-arc), `vaultlab.workflows` (reasoning), `vaultlab.kb` (dossier).
- `INSPIRATIONS.md` — attribution to Thariq Shihipar's `html-effectiveness` gallery.
