# vaultlab.manuscript

Publication-prose helpers for the last mile of a paper: polishing language to journal house-style, scaffolding a point-by-point reviewer-response letter, and drafting + auditing a Data Availability Statement.

> Plain-language background: the [vaultlab subsystems guide](../../../docs/) does not yet carry a dedicated "manuscript" chapter — the closest companions there are *Citation verification* and the polishing discipline. Architectural placement: [`docs/architecture.md`](../../../docs/architecture.md) (the `vaultlab.manuscript` node under Workflows). Note that the architecture sketch still describes a planned `ManuscriptProject` state object; the code that actually ships today is the three prose helpers documented below.

## What it is

When a researcher has finished the science and now has to make the *paper* pass an editor, three chores recur: tighten the prose to Nature/Cell/eLife house style, write a disciplined reply to every reviewer comment, and produce a Data Availability Statement that a FAIR-minded editor will accept. `vaultlab.manuscript` ships those three as addressable, testable data + thin helpers — the rule sets, taxonomies, repository registry, and templates live in code so they are versioned and queryable, while the actual prose transformation happens at slash-command time when the LLM consults them. The three pieces were absorbed from the MIT-licensed nature-skills bundle (Yuan Yizhe, SJTU). The `/polish`, `/respond`, and `/das-audit` skills are the user-facing front ends.

## Public surface

The package barrel (`__init__`) re-exports the three submodules themselves; the useful symbols live one level down. The HTML renderer (`respond_html`) is a real public module but is not re-exported by the barrel.

### `polish` — academic-prose rules + checkers

- `POLISH_RULES` — the 25 house-style rules as `PolishRule` records, grouped into seven categories (sentence architecture, hedging, section tense, vocabulary, citation integrity, overclaim, house style).
- `WORKFLOW_STEPS` — the ordered 12-step polishing workflow (sentence-split → tense-audit → … → plain-text-output).
- `BRITISH_ENGLISH_PAIRS` — the US→UK spelling table (60-odd entries: `color`→`colour`, `analyze`→`analyse`, …).
- `PolishRule` — one frozen rule record (`id`, `category`, `rule`, `rationale`).
- `Category` — the `Literal` of the seven rule domains.
- `rules_by_category()` — group `POLISH_RULES` into a `{category: [rules]}` map.
- `find_rule(rule_id)` — fetch one rule by its slug, or `None`.
- `check_sentence_length(text, *, max_words=30)` — flag sentences over the word cap; returns `(index, word_count, sentence)` tuples.
- `check_us_spelling(text)` — return `(us_token, uk_suggestion)` pairs, case-preserving.
- `write_polish_report(out_path, text, …)` — write a markdown report of the two checks above, with provenance sidecars.

### `respond` — reviewer-response letter scaffolding

- `CommentKind` — the reviewer-comment taxonomy (method question/critique, result challenge, overclaim, missing citation, missing experiment, …).
- `ActionType` — what the author does in response (`ACCEPT_TEXT`, `SOFTEN_CLAIM`, `DISAGREE_WITH_RATIONALE`, `AUTHOR_INPUT_NEEDED`, …).
- `ReviewerComment` — one comment plus its stable ID, classified kind, planned action, and evidence reference.
- `ResponseLetter` — the full point-by-point letter for one reviewer.
- `stable_id(reviewer, comment_index)` — mint the never-reordered `R<r>-C<n>` ID.
- `classify_comment(text)` — heuristic keyword classifier → a `CommentKind`.
- `suggest_action(kind)` — best-guess default `ActionType` for a kind (author overrides).
- `parse_reviewer_block(text, reviewer_index=1)` — parse a numbered reviewer block into scaffolded `ReviewerComment`s with kind + suggested action auto-filled.
- `render_response_letter(letter)` — emit the letter as markdown.
- `write_response_letter(out_path, letter, …)` — render + write the markdown letter with provenance sidecars.

### `respond_html` — the HTML view of a response letter

- `build_response_letter_html(letter, …)` — render a `ResponseLetter` (or an equivalent dict) as single-file HTML with colour-coded action badges, a filter bar, and `AUTHOR_INPUT_NEEDED` cards called out in red.
- `write_response_letter_html(out_path, letter, …)` — build and write that HTML view.

### `data_availability` — DAS templates, FAIR checklist, repository registry

- `REPOSITORIES` — registry of common data repositories (`Repository` records: slug, name, domain, identifier regex, URL + citation templates) covering GEO, SRA, ENA, PRIDE, PDB, EMPIAR, IDR, EGA, dbGaP, Dryad, Zenodo, OSF, GitHub, and more.
- `FAIR_CHECKLIST` — the 14 FAIR items as `FAIRItem` records, grouped by principle.
- `Repository` / `FAIRItem` / `FAIRPrinciple` — the record types and the FAIR-principle `Literal`.
- `DAScenario` — the six DAS scenarios (public deposit, restricted human, on-request, supplementary-only, internal-only, code-archived).
- `StatementAuditFinding` — one audit finding with a `blocker`/`major`/`minor` severity.
- `statement_template(scenario)` — fetch a DAS prose template for a scenario.
- `audit_statement(text)` — heuristic audit of a candidate DAS (e.g. flags "available on reasonable request" with no contact, human data with no restriction clause, no accession identifier at all).
- `write_data_availability_statement(out_path, statement, …)` — write the DAS plus its audit findings, with provenance sidecars.

## How it fits

This package sits at the **manuscript / submission** end of the pipeline, downstream of the figure and analysis work. The rule sets and templates are static data the LLM reads at slash-command time; the helpers are pure-Python checks and renderers over text you supply. It does **not** read the knowledge base itself — callers (the slash commands) feed it the draft text or reviewer block. Every `write_*` helper depends on `vaultlab.provenance` (`ProvenanceRecord` + `write_receipts`) to drop `*.provenance.json` and `*.method.md` sidecars next to each output, so a polish report / response letter / DAS carries its own audit trail (Red Line #2: no silent failures). `respond_html` additionally consumes `vaultlab.report` (`_components` + `render_report`) to build its single-file HTML view. Outputs are markdown / HTML files that land in a project's `Output/` folder for the human to review.

## What it does NOT do

- It does **not** rewrite your prose automatically. The checkers *flag* long sentences and US spellings and the rules are *consulted by the LLM* — the package itself does no text transformation.
- It does **not** verify citations or check whether a claim is true; that is `vaultlab.citations`. `classify_comment` and `audit_statement` are keyword/heuristic, not semantic.
- It does **not** track manuscript sections, figures, or draft versions. The `ManuscriptProject` state object sketched in the architecture doc is not implemented here.
- It does **not** fetch papers, run analyses, or submit anything to a journal — it operates only on text you hand it.

## Files

- `__init__.py` — slim barrel; re-exports the `polish`, `respond`, and `data_availability` submodules.
- `polish.py` — the 25 prose rules, 12-step workflow, British-English table, sentence/spelling checkers, and report writer.
- `respond.py` — comment taxonomy, action map, classifier, reviewer-block parser, and markdown letter renderer.
- `respond_html.py` — single-file HTML view of a `ResponseLetter` (consumer of `vaultlab.report`).
- `data_availability.py` — repository registry, FAIR checklist, DAS scenario templates, and the DAS auditor.

No sibling `.md` docs ship inside the package today; the per-skill prose (when-to-load guidance, tone, difficult-case playbooks) lives in the `SKILL.md` files the docstrings reference.

## See also

- `.claude/commands/polish.md`, `.claude/commands/respond.md`, `.claude/commands/das-audit.md` — the user-facing slash commands that drive these helpers.
- [`../citations/README.md`](../citations/README.md) — citation verification (the semantic check this package deliberately leaves out).
- [`../provenance/`](../provenance/) — the receipt layer every `write_*` helper here depends on.
- [`../report/`](../report/) — the HTML report grammar `respond_html` builds on.
- [`docs/architecture.md`](../../../docs/architecture.md) — where `vaultlab.manuscript` sits in the overall system.
