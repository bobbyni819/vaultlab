# Changelog

All notable changes to vaultlab. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project follows semantic versioning where feasible (alpha → 0.x.y).

## [Unreleased] — v0.0.4 in progress

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
