# Changelog

All notable changes to vaultlab. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project follows semantic versioning where feasible (alpha → 0.x.y).

## [Unreleased]

Post-v0.0.6 work toward **v0.1.0** — figure-recipe subsystem completion, AI-co-scientist orchestration robustness, and figure-quality + flake fixes. All new orchestration features are **default-OFF** (no behavior change unless opted in).

### Added — figure-recipe subsystem (the v0.1.0 gate, NEXT_STEPS B7–B12)

- **≥3-anchor-paper rule ENFORCED** — `tests/test_vaultlab_figures/test_recipe_invariants.py` fails the build if any recipe's `ANCHOR_PAPERS` has < 3 entries (B12). Real verified anchors added to the 4 violators (umap_overlay, stat_test_panel, spatial_map_overlay, multi_panel_composite).
- **`vaultlab.figures.corpus`** — `build_sources_index` / `save_sources_index` / `load_sources_index` derive a checked-in `sources.json` from the recipes' `ANCHOR_PAPERS`, guarded by a staleness test (B7).
- **Smoke-render tests for all 11 recipes** — first real render coverage (B8).
- **`templates/recipe/` scaffold** — copyable `_recipe_name.py` + `_recipe_name.md` (B9).
- **`vaultlab.figures.publication.save.save_with_optional_contract`** — opt-in path for a recipe to honor a `FigureContract` (validate + SVG/PDF/TIFF triple-export at 600 dpi) without changing the default 300 dpi PNG+PDF (B11).

### Added — orchestration robustness (AI co-scientist; INSPIRATIONS.md lineage)

Six default-OFF patterns from "Towards an AI co-scientist" (Gottweis et al. 2025), independently cross-model reviewed:

- **Critic deep-verification + simulation** — `roles/methods_critic/prompt.md`.
- **Non-regression guard** — `runner.run_with_reflection(non_regression_guard=True)` adopts a refinement only if it drops no cited DOI and adds no unhedged / numeric-inconsistent claim.
- **Goal safety gate** — `workflows.crosstalk_policy.classify_goal_risk` + `NeedsHumanApproval` (high-precision; no false-positives on ordinary biology).
- **Convergence early-exit** — `crosstalk` meetings stop once the synthesizer output stabilises (`early_exit=True`; status `"converged"`).
- **Adaptive allocation** — `crosstalk_policy.rounds_for_spread` sizes the next run's rounds from `CrosstalkResult.critic_spread`.
- **Meta-review checklist** — `crosstalk.meta_review_checklist` + `CrosstalkResult.meta_review` surface recurring critic concerns for the next run.

### Fixed

- pandas-3.0 string-dtype (`"str"`) compatibility in the analysis stats test.
- Windows clock-skew flake — `kb.dossier.dossier_age_hours` clamps at 0 (was 2/5 flaky).
- **Figure quality (found by visually reviewing the rendered output):** marker_dot_plot size-legend no longer occludes the data column; pseudobulk_volcano labels de-crowded (default 6/side) + legend relocated + white-halo legibility.
- Parquet inputs raise an actionable error when no engine is installed; `pyarrow` added to the `dev` extra.
- Doc accuracy: deep_think comments say "crosstalk", not "round-table" (NEXT_STEPS C3).

## [0.0.6] — 2026-05-15

Patch release rolling up 12 commits of post-v0.0.5 follow-up work shipped on the same day. Test count grew 2040 → 2196. HTML pattern coverage matrix now closed at 18/20 ✅ (2 intentionally out-of-scope).

### Added — HTML pattern coverage closure (6 new consumers)

- **`vaultlab.report.pr_writeup_html`** — pattern #5. Release notes / iterate-session summaries with file-by-file table + before/after compare.
- **`vaultlab.report.flowchart_html`** — pattern #12. Annotated flowchart for pipeline phase explainers + KB ingest viz.
- **`vaultlab.report.incident_timeline_html`** — pattern #17. Postmortem timeline with log excerpts + followup checklist.
- **`vaultlab.report.visual_designs_html`** — pattern #2. Palette + layout swatches for figure-contract draft mode.
- **`vaultlab.report.component_variants_html`** — pattern #8. Contact-sheet of slide layouts / report primitives, grouped by tag.
- **`vaultlab.report.svg_figure_sheet_html`** — pattern #11. Copyable inline-SVG schematic library for architecture diagrams.

Each writes provenance sidecars per Red Line #2. Coverage doc updated; KB mirror synced.

### Added — Phase 7.3 finish

- **`vaultlab.slides.time_budget.audit_time_budget`** — per-slide and total presentation time estimation; flags over-budget decks. Heuristics keyed on slide kind.
- **`vaultlab.slides.qa_anticipator.anticipate_qa`** — LLM-driven with heuristic fallback; surfaces likely audience questions per slide.
- **`vaultlab.slides.version_diff.diff_decks`** — slide-level diff between two .pptx versions with field-level change records.

`self_review.review_deck` integrated to optionally call all three.

### Added — Composability + crosstalk + audit polish

- **Workflow Provenance unification** — `vaultlab.workflows._provenance.Provenance` gains a `params: dict[str, Any]` field, unifying receipt shape with `vaultlab.provenance.ProvenanceRecord`. Deep-think crosstalk wiring migrated to use the new `params` dict (legacy tags/notes retained for back-compat).
- **Deep-think crosstalk wiring** — `should_invoke` gate wired into `plan_deep_think_round`, `plan_deep_think_with_ensemble_critic`, and `run_deep_think_with_ensemble_critic`. Decisions recorded in provenance manifests.
- **Speaker-notes structure audit** — `self_review` flags empty-notes-on-figure-slide (critical), missing mental-map heading (warning), <100-word or >500-word scripts (warning). Title/divider slides exempt.
- **WCAG color-contrast check** — `self_review` per text shape; <3.0 → critical, 3.0-4.5 → warning. Conservative on themed colors.
- **Inset-axes detection** — `vaultlab.figures.understand.whitespace.classify_panel_layout` now returns `single_plot_with_inset` for corner-inset figures; layout dispatch routes them to single-plot layouts.
- **Dispatch wiring for new consumers** — `vaultlab.report.dispatch._detect_kind` recognizes `WeeklyStatusReport`, `StateDashboard`, `FeatureFlagConfig`, `ApproachesCompare`, `PRWriteup`, `Flowchart`, `IncidentReport`, `VisualDesigns`, `ComponentInventory`, `FigureSheet`.

### Added — Slash commands for v0.0.5 primitives

`/full-reader`, `/run-analysis`, `/state-dashboard`, `/review-deck`, `/triage-citations`. `/polish`, `/respond`, `/das-audit` updated to write provenance sidecars per Red Line #2. Auto-copied to claude-config KB.

### Added — KB enrichment

- 6 new Wiki/Concepts pages: `audit-manifest-contract`, `nature-reader-absorption`, `html-output-system` (rewritten), `crosstalk-and-dispatch`, `kb-primitives`, `v0.0.5-release`. Bidirectional wikilinks. KB indexes regenerated via `vaultlab.kb.build_indexes`.
- Master state doc `Sources/Notes/system-state-2026-05-15.md` written.

### Added — Test coverage

- **Crosstalk no-lit-search tests** (task #117) — 12 new no-arc tests in `tests/test_vaultlab_workflows/test_crosstalk_no_lit_search.py`. Verifies crosstalk fires without prior lineage_result; covers policy + plan-build + e2e execution + provenance + cross-primitive composition.
- **Test-suite memory pressure fix** — `tests/test_vaultlab_slides/conftest.py` adds an autouse `gc.collect()` after every slides test, breaking the python-pptx ↔ lxml reference cycle that caused `zipfile.MemoryError` on Windows under suite-level memory pressure.

### Changed

- README: refreshed for v0.0.5 with a "What's new" highlights block + "Simpler install (recommended)" subsection.



Big release. Bundles the previously in-flight v0.0.4 work (HTML output system, nature-skills absorption, manuscript subpackages, two-way editors) with 19 north-star plan sub-goals shipped on 2026-05-14/15. All 4 red lines (no fabrication, no silent failures, no user-data loss, no vendor lock-in) are now mechanically enforced by an always-on CI invariant suite. Test count grew from 1734 → 2040.

### Added — North-star plan execution (2026-05-15)

- **Sub-goal 1.1 — Red-line invariant tests + CI workflow.** `tests/test_vaultlab_invariants/test_red_lines.py` enforces all 4 red lines via static analysis. `.github/workflows/invariants.yml` runs on every push (~2s, no fixtures). Suite: 8 passed / 0 xfail.
- **Sub-goal 1.2 — Audit-manifest contract.** Every artifact-producing entrypoint writes `<output>.provenance.json` + `<output>.method.md` sidecars via `vaultlab.provenance.write_receipts`. Wired into `slides/render`, `figures/publication/save`, `citations/reporter`, `manuscript/{polish,respond,data_availability}`, `report/dispatch`, and `kb/start_here`.
- **Sub-goal 1.3 — Per-module standalone integration tests.** 8 new `test_standalone.py` files prove each public-API module is end-to-end runnable from a fresh `tmp_path` with no prior vaultlab state.
- **Sub-goal 1.4 — `vaultlab demo` command.** Single-command demo produces an audit-clean 7-slide journal-club deck from bundled OA sample data in ~1.1s. Fully offline, no API keys. `src/vaultlab/data/demo/` ships in the wheel.
- **Sub-goal 1.5 — Clean-VM onboarding test.** `Dockerfile.onboarding` + `.github/workflows/onboarding.yml` verify `pip install vaultlab → vaultlab demo` completes in <30 min on a clean container (Criterion #4 proof).
- **Sub-goal 2.1 — `vaultlab.research.full_reader`.** Bilingual figure-aware full-paper Markdown reader; closes the last nature-skills gap (7 of 7 nature-skills absorbed).
- **Sub-goal 2.2 — KB retrieval upgrade (SPEC-C).** `vaultlab.kb.retrieve_by_frontmatter` + `vaultlab.kb.build_indexes` (generates `_Index.md` / `_Catalog.md` / `_BackLinks.md`). Layered retrieval cascade per the researcher-pathway thinking memory.
- **Sub-goal 2.3 — KB setup + lint as primitives (SPEC-D).** Public-API surface for `vaultlab.kb.setup` / `vaultlab.kb.lint` (canonical aliases for existing `scaffold_kb` / `lint_kb`).
- **Sub-goal 2.4 — Crosstalk invocation policy (SPEC-E).** `vaultlab.workflows.crosstalk_policy.should_invoke(ctx)` gates round-table firing by task kind. Wired into `lineage.run_lit_arc` (picker + arc) and `slides.deck.build_deck_from_lineage_result`. Skip-decisions recorded in provenance.
- **Sub-goal 2.5 — Task-weight dispatch (SPEC-F).** `vaultlab.workflows.task_weight.classify(task) → light/medium/heavy` + `model_for_weight(weight, config_path)` resolution. Defaults: light=Haiku, medium=Sonnet, heavy=Opus. Configurable via `~/.config/vaultlab/dispatch.json`. Wired into `research.full_reader`.
- **Sub-goal 2.6 — Result-analysis pipeline (SPEC-A).** `vaultlab.analysis.run_pipeline(project_dir)` consumes tidy CSV/Parquet results and produces figures + methods paragraph + provenance manifests. Scope discipline enforced: rejects raw-data formats (.fastq/.bam/.h5ad/.nd2/.czi/.mzml).
- **Sub-goal 3.1 — Examples seed workflows.** `examples/journal-club/`, `examples/manuscript-section/`, `examples/citation-cleanup/` — each with README + `run.py` + inputs + expected outputs. Runnable offline.
- **Sub-goal 3.2 — Adoption surface.** Three-example rule generalized in CONTRIBUTING.md. New `.github/ISSUE_TEMPLATE/testimony.md`. README link block above the fold.
- **Sub-goal 3.3 — GitHub Discussions live.** Discussions enabled + welcome thread at https://github.com/bobbyni819/vaultlab/discussions/1. Criterion #1's testimony channel is now LIVE.
- **Sub-goal 4.1 — HTML pattern coverage audit.** `docs/html-pattern-coverage.md` maps all 20 patterns from Thariq's gallery: 12 ✅ / 8 🟡 / 0 ❌.
- **Sub-goal 4.2 — Top-4 unimplemented HTML patterns.** `vaultlab.report.state_dashboard_html` (composite #16+#15+#6), `feature_flag_editor` (#19), `approaches_compare_html` (#1). Earlier slice: `weekly_status_html` (#16).
- **Sub-goal 4.3 — `vaultlab.report` SKILL.md catalog.** Decision table + per-pattern catalog covering all 20 patterns + every primitive.
- **Sub-goal 5.1 — Meta-agent roles (SPEC-B) audit.** 4 roles (`journal_reviewer`, `expert_reviewer`, `adoption_evaluator`, `publication_guideline_compliance`) verified shipped.
- **Sub-goal 5.2 — 4 slide deck templates.** `investor_pitch`, `lab_meeting`, `conference_talk`, `journal_club` builders. Each respects hard slide rules (Roboto, 28/24/18pt, no overlap, descriptive titles).
- **Sub-goal 5.3 — 4 slide layouts.** `equation_slide`, `table_slide`, `comparison_table_slide`, `acknowledgments_grid_slide`. Native python-pptx tables; hard-rule conformant.
- **Sub-goal 5.4 — Slide self-review pass.** `vaultlab.slides.self_review.review_deck(pptx)` reads each rendered slide and returns a unified `ReviewReport`. CLI: `vaultlab slides review <pptx>`. HTML rendering via existing `audit_html` builder.
- **Sub-goal 5.5 — Granular custom-figure handling.** `is_single_plot(image)` predicate + `suggest_figure_layout()` dispatcher. Single-plot figures (volcano, UMAP, single bar) no longer get panel-cut.
- **Destructive-op hardening** — `dry_run` kwarg on `vaultlab.context.user_memory.forget` + `vaultlab.context.meetings.ingest_transcript`. Closes the last invariant xfail under Red Line #3.

### Added — HTML output system (Track A — was v0.0.4 in flight)

- **`vaultlab.report` package** — HTML output for vaultlab artifacts. One entrypoint (`render_report(title, sections, ...)`) wraps 15 composable component primitives (`tldr_box`, `card_grid`, `severity_card`, `matrix_table`, `compare_panel`, `collapsible_step`, `tabbed_block`, `timeline`, `svg_arg_graph`, `kanban_board`, `template_editor`, `status_chip`, `margin_glossary`, `keynav_deck`, `filter_bar`, `section`) into a self-contained single-file HTML document with inline CSS + vanilla JS, no external assets. Mobile-responsive + print-friendly. Modeled on Thariq Shihipar's "Unreasonable Effectiveness of HTML" gallery (Anthropic, 2026).

### Added — HTML output system (Track A)

- **`vaultlab.report` package** — HTML output for vaultlab artifacts. One entrypoint (`render_report(title, sections, ...)`) wraps 15 composable component primitives (`tldr_box`, `card_grid`, `severity_card`, `matrix_table`, `compare_panel`, `collapsible_step`, `tabbed_block`, `timeline`, `svg_arg_graph`, `kanban_board`, `template_editor`, `status_chip`, `margin_glossary`, `keynav_deck`, `filter_bar`, `section`) into a self-contained single-file HTML document with inline CSS + vanilla JS, no external assets. Mobile-responsive + print-friendly. Modeled on Thariq Shihipar's "Unreasonable Effectiveness of HTML" gallery (Anthropic, 2026).
- **HTML deck-audit report** — `vaultlab.slides.audit_html.build_audit_report_html(plan, audit)`. Severity-filtered per-slide cards, jump-to-source, XSS-hardened. Replaces the long-form MD audit.
- **HTML lit-arc narrative** — `vaultlab.research.litarc_html.build_litarc_report_html(...)`. Tier-filtered paper cards, frontmatter chips, optional SVG citation graph, basic markdown rendering for the narrative.
- **HTML reasoning-chain report** — `vaultlab.workflows.reasoning_html.build_reasoning_report_html(result)`. Color-coded per-role rounds, expandable prompt+output, JSON pretty-printing in synthesizer outputs.
- **HTML citation audit report** — `vaultlab.citations.report_html.build_citation_audit_html(audit)`. Filterable per-citation cards, copy-DOI buttons, hallucination flag chips, action-items table.
- **HTML project-dossier report** — `vaultlab.kb.dossier_html.build_dossier_report_html(dossier)`. Tabbed 9-section navigation, freshness badge, per-section source list, all-sources appendix.
- **HTML keynav .pptx preview** — `vaultlab.slides.preview_html.build_deck_preview_html(plan)`. Arrow-key navigable slideshow with inline-embedded base64 figures; browser-openable, no PowerPoint needed.

### Added — Two-way HTML editors (Track D)

- **Slide reorder editor** — `vaultlab.report.editors.build_slide_reorder_editor(plan)`. Drag slides between sections (or to "Cut"); export new ordering as JSON/markdown.
- **Citation triage editor** — `vaultlab.report.editors.build_citation_triage_editor(citations)`. 5-pile kanban for accept/reject/flag verdicts; auto-bucket by existing status; JSON export.
- **Deck-plan tuner** — `vaultlab.report.editors.build_deckplan_tuner(template, samples)`. Live-preview `{{var}}` template editor with 2-3 sample papers, token counter, copy-prompt button.

### Added — nature-skills absorption (Track B + C)

- **`vaultlab.figures.contract`** + `contract.md` SKILL: figure-contract discipline that must precede plotting code. 4 archetypes (`FigureArchetype`), NMI pastel palette, mandatory rcParams, `triple_export(fig, stem)` for SVG+PDF+TIFF. Validation raises `ContractViolation` on hard failures; soft warnings flag suboptimal commitments. Absorbed from nature-figure (Yuan Yizhe, SJTU).
- **`vaultlab.slides.journal_club_arcs`**: 7 paper-type narrative arcs (discovery / methods / dataset / clinical / materials / review / generic) with conclusion-first slide titles. English + simplified-Chinese variants. Heuristic `classify_paper_type(metadata)` from frontmatter. Absorbed from nature-paper2ppt.
- **`vaultlab.manuscript.polish`**: 25 prose rules across 7 categories + 12-step polishing workflow + 65+ British-English replacement pairs + `check_sentence_length`/`check_us_spelling` helpers. Absorbed from nature-polishing.
- **`vaultlab.manuscript.respond`**: Reviewer response letter scaffolding. `CommentKind` taxonomy (12 types), `ActionType` enum (9 actions), `ReviewerComment`/`ResponseLetter` dataclasses, `R<n>-C<m>` stable IDs, heuristic classifier, numbered-list parser, markdown renderer. Absorbed from nature-response.
- **`vaultlab.manuscript.data_availability`**: 15-repository registry (GEO, SRA, GenBank, ENA, PRIDE, MassIVE, PDB, EMPIAR, IDR, EGA, dbGaP, Dryad, Zenodo, OSF, GitHub) with regex identifier formats + URL templates + DAS citation prose, 14-item FAIR checklist, 6 statement-pattern templates (`DAScenario`), heuristic `audit_statement(text)` flagging vague "reasonable request" / unrestricted human data / missing identifiers. Absorbed from nature-data.
- **`vaultlab.citations.export`**: ENW / RIS / Zotero RDF exporters with author-string normalization, HTML-escaped RDF, no-fabrication rule. `write_export(path, citations, fmt=None)` auto-infers format from extension. Absorbed from nature-citation.

### Inspirations / attribution

- New entries in `INSPIRATIONS.md` for Thariq Shihipar (PATTERN: HTML-first thesis) and Yuan Yizhe's nature-skills (PATTERN+CONCEPT: 5 of 7 SKILL.md bundles absorbed as Python primitives, MIT, no source-code copy).

### Test coverage

1734 tests pass (+184 from v0.0.3 baseline of 1550).

## [0.0.3] — 2026-05-10

### Added

- **Four audit roles** using the eLife two-axis rubric (significance × evidence): `journal_reviewer`, `expert_reviewer`, `adoption_evaluator`, `publication_guideline_compliance`. Each has a slash command (`/journal-reviewer-audit`, `/expert-reviewer-audit`, `/adoption-evaluator-audit`, `/publication-guideline-audit`) and returns structured JSON verdicts with concrete fixes. `expert_reviewer` simulates a PI/advisor doing a read-through with full project context.
- **Project Dossier** (`/refresh-dossier <project>`) — a 9-section auto-compiled standing mental model per project (origin, current state, methodology commitments, established findings, frontier, literature backdrop, cross-project connections, anticipated reviewer questions, recent rolling tail). Refreshes daily by default; loaded as first-layer context before any non-trivial primitive.
- **Bundled journal-publication guidelines** for Cell-family, Nature, eLife, and bioRxiv at `vaultlab/data/journal_guidelines/*.yaml` (enforceable rules) and `External/journal-guidelines/*.md` (verbatim prose). Auto-loaded into audit-role prompts.
- **Five new figure recipes** (library now 6 → 11 archetypes): `pseudobulk_volcano`, `stacked_bar`, `cci_heatmap`, `spatial_neighborhood`, `metabolite_pathway_map`. Each anchored to a published reference layout.
- **KB scaffolding + lint** (`/init-kb`, `/audit-kb`) — `vaultlab.kb.setup.scaffold_kb` creates the canonical 11-folder + 4-file structure including `START_HERE.md` with the maintenance rules embedded. `vaultlab.kb.setup.lint_kb` returns a severity-ranked report.
- **Tool auto-discovery from literature** — when `/lit-arc` reads a paper that introduces a software tool, `vaultlab.kb.tools_index.discovery` detects the signature, extracts metadata, and writes a stub to `packages/discovered/`. `/find-tool-for <task>` queries across curated + discovered + external repos.
- **SPEC-first development discipline** — `templates/SPEC.md` is the canonical template (Goal / Acceptance criteria / Edge cases / How to verify / References / Implementation steps / Definition of done). New features are authored as SPECs before being built.

### Changed

- **Polite-pool identity (User-Agent + Unpaywall mailto) is now configurable per-user** via `VAULTLAB_POLITE_POOL_EMAIL` env var or `~/.config/vaultlab/config.json`. Falls back to an anonymous no-reply address when neither is set. Previously hardcoded to the maintainer's email — every install attributed API queries to one person.
- `expert_reviewer` (formerly named `pi_evaluator` in development) speaks in the PI/advisor archetype (the senior reader with full project oversight) but scales to non-academic users — solo researchers, postdocs, industry, lab heads.
- Audit roles output verdicts on the eLife rubric (`landmark`/`fundamental`/`important`/`valuable`/`useful` × `exceptional`/`compelling`/`convincing`/`solid`/`incomplete`/`inadequate`) — the same vocabulary across `journal_reviewer`, `expert_reviewer`, and `publication_guideline_compliance` so audits can be compared.
- README + module docstrings reworded for matter-of-fact technical voice; over-promotional taglines removed.

### Fixed

- Loader-level role tests updated to include the four new audit roles in `EXPECTED_ROLE_IDS` and `ROUND_TRIP_SIGNATURES`.

### Test coverage

1527 tests pass.

---

## [0.0.2] — 2026-04-28

Initial PyPI release. Trusted Publisher wired for future tag-push releases.
