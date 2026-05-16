# HTML pattern coverage audit

**Date:** 2026-05-15
**Sub-goal:** 4.1 of the north-star plan (`.claude/goals/vaultlab-north-star-plan.md`)
**Source:** the 20 patterns from `G:/My Drive/Knowledge/vaultlab/Output/Plans/html-and-nature-skills-2026-05-12.html` (Section 8), originally derived from Thariq's HTML-effectiveness gallery (`thariqs.github.io/html-effectiveness`).

This audit answers: for each of Thariq's 20 patterns, is the underlying primitive implemented in `vaultlab.report`? Is a real vaultlab consumer using it? What's left?

> **See also:** [`src/vaultlab/report/SKILL.md`](../src/vaultlab/report/SKILL.md) —
> the per-pattern catalog with minimal usage examples + consumer pointers
> (sub-goal 4.3). This audit is the *status*; the SKILL.md is the *how-to-use*.

## Legend

- ✅ **Implemented** — primitive exists AND ≥1 real vaultlab consumer uses it
- 🟡 **Partial** — primitive exists but no consumer wired yet (component is callable; nobody calls it from a real output)
- ⛔ **Out of scope** — primitive exists; intentionally not wired for vaultlab (see "Out-of-scope" section)
- ❌ **Missing** — primitive not in `vaultlab.report` at all
- 🆕 **Editor variant** — implemented via `vaultlab.report.editors` (interactive two-way HTML)

## Coverage table

### Exploration & planning

| # | Pattern | Status | Primitive | Real consumer |
|---|---|---|---|---|
| 1 | Three Code Approaches | ✅ | `compare_panel`, `card_grid` | `vaultlab.report.approaches_compare_html.build_approaches_compare_html` — 2-up via `compare_panel`, 3+ via `card_grid` with RECOMMENDED badge; sub-goal 4.2 |
| 2 | Visual Design Directions | ✅ | `card_grid` + inline SVG | `vaultlab.report.visual_designs_html.build_visual_designs_html` — palette swatches (auto-built SVG) + optional layout-preview SVG per option + archetype chip; sub-goal 4.5 |
| 3 | Implementation Plan | ✅ | `timeline`, `svg_arg_graph`, `tldr_box` | `vaultlab.workflows.reasoning_html.build_reasoning_report_html` for crosstalk plans; this very plan doc is HTML |

### Code review & understanding

| # | Pattern | Status | Primitive | Real consumer |
|---|---|---|---|---|
| 4 | Annotated Pull Request | ✅ | `severity_card`, `margin_glossary` | `vaultlab.slides.audit_html.build_audit_report_html` (per-slide critique with severity tags) + `vaultlab.citations.report_html.build_citation_audit_html` (per-citation cards) |
| 5 | PR Writeup for Reviewers | ✅ | `matrix_table`, `compare_panel`, `collapsible_step` | `vaultlab.report.pr_writeup_html.build_pr_writeup_html` — TL;DR + breaking chips + before/after test summary + per-file roll-up table + per-commit collapsibles; sub-goal 4.4 |
| 6 | Module Map | ✅ | `svg_arg_graph`, `card_grid` | `vaultlab.report.state_dashboard_html` (composite consumer) — `vaultlab.*` package graph + legend cards; sub-goal 4.2 |

### Design & prototypes

| # | Pattern | Status | Primitive | Real consumer |
|---|---|---|---|---|
| 7 | Living Design System | ⛔ | `card_grid` + clipboard-copy | Out of scope — vaultlab has 2 palettes, too few for a token-swatch view to earn its keep |
| 8 | Component Variants | ✅ | `card_grid` dense mode | `vaultlab.report.component_variants_html.build_component_variants_html` — contact-sheet of variants with tag-based grouping (one section per first-tag) + optional inline preview HTML per row; sub-goal 4.5 |
| 9 | Animation Sandbox | ⛔ | `template_editor` w/ slider | Out of scope — annotation timing is not a user-tunable parameter |
| 10 | Clickable Flow | ✅ | `keynav_deck` | `vaultlab.slides.preview_html.build_deck_preview_html` (arrow-key nav HTML preview of decks) |

### Diagrams & presentations

| # | Pattern | Status | Primitive | Real consumer |
|---|---|---|---|---|
| 11 | SVG Figure Sheet | ✅ | `svg_arg_graph` + copy | `vaultlab.report.svg_figure_sheet_html.build_svg_figure_sheet_html` — standalone schematic library; each diagram framed with copy-SVG button + related-concept chips; sub-goal 4.5 |
| 12 | Annotated Flowchart | ✅ | `svg_arg_graph`, `collapsible_step` | `vaultlab.report.flowchart_html.build_flowchart_html` — LTR rank-laid SVG + per-step expandable detail with duration / failure-mode badges; sub-goal 4.4 |
| 13 | Arrow-Key Slide Deck | ✅ | `keynav_deck` | `vaultlab.slides.preview_html.build_deck_preview_html` (same as #10) |

### Research & learning (highest-fit category)

| # | Pattern | Status | Primitive | Real consumer |
|---|---|---|---|---|
| 14 | How a Feature Works | ✅ | `tldr_box`, `collapsible_step`, `tabbed_block`, `margin_glossary` | `vaultlab.kb.dossier_html.build_dossier_report_html` (9-section dossier with tabbed view + freshness badge) |
| 15 | Concept Explainer | ✅ | custom JS over `svg_arg_graph` | `vaultlab.report.state_dashboard_html` (composite consumer) — optional inline explainer panel with hot-path highlighting; sub-goal 4.2 |

### Reports

| # | Pattern | Status | Primitive | Real consumer |
|---|---|---|---|---|
| 16 | Weekly Status | ✅ | `tldr_box`, `card_grid`, `severity_card` | `vaultlab.report.weekly_status_html.build_weekly_status_html` — TL;DR + metrics + shipped / in-flight / blocker grids; commit 6bd6dc6 |
| 17 | Incident Timeline | ✅ | `timeline`, `tabbed_block` | `vaultlab.report.incident_timeline_html.build_incident_timeline_html` — minute-by-minute timeline + tabbed log excerpts + followup checklist; sub-goal 4.4 |

### Custom editors (two-way HTML)

| # | Pattern | Status | Primitive | Real consumer |
|---|---|---|---|---|
| 18 | Ticket Triage Board | 🆕✅ | `kanban_board` | `vaultlab.report.editors.build_citation_triage_editor` + `build_slide_reorder_editor` |
| 19 | Feature Flag Editor | ✅ | grouped toggles + clipboard-copy | `vaultlab.report.feature_flag_editor.build_feature_flag_editor` — grouped toggles + Copy diff / Copy current / Copy defaults; sub-goal 4.2 |
| 20 | Prompt Tuner | 🆕✅ | `template_editor` | `vaultlab.report.editors.build_deckplan_tuner` |

## Summary

- **Total patterns:** 20
- **✅ Implemented (primitive + consumer):** 18 (#1, #2, #3, #4, #5, #6, #8, #10, #11, #12, #13, #14, #15, #16, #17, #18, #19, #20)
- **🟡 Partial (primitive exists, no consumer yet):** 0
- **⛔ Out of scope (intentionally not wired):** 2 (#7 design tokens, #9 animation sandbox)
- **❌ Missing (no primitive):** 0

**Matrix complete.** Every in-scope Thariq pattern now has a real vaultlab consumer; the two out-of-scope patterns are documented below.

**Sub-goal 4.2 update (2026-05-15):** patterns #1, #6, #15, #16, #19 all shipped. Patterns #6 + #15 wired as the composite `state_dashboard_html` consumer per the audit's recommendation; #1 and #19 ship as standalone consumers (`approaches_compare_html`, `feature_flag_editor`). See `.claude/goals/html-patterns-top4-implementation.md`.

**Sub-goal 4.4 update (2026-05-15):** patterns #5, #12, #17 all shipped as standalone consumers — `pr_writeup_html`, `flowchart_html`, `incident_timeline_html`. Each writes Red Line #2 provenance sidecars. See `.claude/goals/html-patterns-pr-flowchart-incident.md`.

**Sub-goal 4.5 update (2026-05-15):** patterns #2, #8, #11 all shipped as standalone consumers — `visual_designs_html`, `component_variants_html`, `svg_figure_sheet_html`. Matrix now 18 implemented / 0 partial / 2 out-of-scope. See `.claude/goals/html-patterns-matrix-complete.md`.

## Top-5 highest-fit-for-vaultlab patterns to wire next

Prioritization criteria: (a) directly serves a real research workflow Bobby or a target adopter would use; (b) reuses existing primitives without inventing new ones; (c) low engineering cost (one consumer module).

| Rank | Pattern | Proposed consumer | Why high-fit |
|---|---|---|---|
| 1 | #16 Weekly Status | HTML view of `system-state-<date>.md` + `/weekly` output | Bobby writes a state doc every few days; HTML view replaces brittle markdown render and adds the velocity bar. Direct work-log improvement. |
| 2 | #15 Concept Explainer | Interactive lit-arc mechanism explainer (CCI heatmap with click-to-highlight) | Lit-arc narratives are vaultlab's most-used output; making the central mechanism diagram interactive is high-leverage for both Bobby and adopters. |
| 3 | #6 Module Map | HTML render of `system-state-<date>.md` showing the module graph | Pairs with #16; adopters needing to learn vaultlab's surface benefit. Reuses `svg_arg_graph`. |
| 4 | #19 Feature Flag Editor | Two-way HTML editor for `~/.config/vaultlab/dispatch.json` (SPEC-F) | Couples nicely with SPEC-F (task-weight dispatch); adopters tune model routing per-workflow. Extends `template_editor`. |
| 5 | #1 Three Code Approaches | SPEC-A/B/C/D/E/F dossier HTML output | The pending SPEC backlog already calls for "approach A/B/C with trade-offs" presentation; this is the natural HTML home. |

## Out-of-scope for vaultlab

- **#7 Living Design System (token swatches)** — vaultlab has 2 palettes (NMI_PASTEL + Nature-2026). A token-swatch HTML is overkill for so few tokens; this pattern is for design systems with 100+ tokens.
- **#9 Animation Sandbox** — annotation timing is not a tunable user wants to fiddle with; vaultlab's default annotation timing should "just work" per the slide hard rules.

## Recommended next sub-goal

**Sub-goal 4.2 (in the north-star plan) should target patterns #16 + #15 + #6.** Together they form a "vaultlab state dashboard" HTML output (`/state-html` slash command) that:

1. Renders the most-recent `system-state-<date>.md` as HTML
2. Embeds an `svg_arg_graph` module map of `vaultlab.*` packages
3. Adds an interactive mechanism explainer for the currently-active lit-arc

Estimated effort: one `/goal "build vaultlab.report.state_html consumer + /state-html slash command"` invocation.

## Followup tracking

- This audit's findings update sub-goal 4.2's success criteria. The plan's "top-5" target stays the same in cardinality but the specific patterns chosen are now justified by data.
- Sub-goal 4.3 (catalog SKILL.md) landed 2026-05-15 — see [`src/vaultlab/report/SKILL.md`](../src/vaultlab/report/SKILL.md) for the per-pattern catalog with import-verified examples. Bidirectionally cross-linked.
