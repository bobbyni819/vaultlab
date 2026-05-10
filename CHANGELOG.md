# Changelog

All notable changes to vaultlab. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project follows semantic versioning where feasible (alpha → 0.x.y).

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
