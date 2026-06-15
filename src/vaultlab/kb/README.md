# vaultlab.kb

The growing brain: an ordinary folder of plain-text (Obsidian-style markdown) notes that every vaultlab task reads from before it starts and writes back to when it finishes — plus the primitives that scaffold, lint, index, search, and route paths inside it.

> Plain-language companion: the **"knowledge base (memory)"** section of `vaultlab-subsystems.md` (in the KB) explains the *why* for a non-engineer. Architectural sketch: [`docs/architecture.md`](../../../docs/architecture.md) (`### vaultlab.kb`). This README is the developer-facing map of what you can call.

## What it is

A knowledge base in vaultlab is one plain folder per research project, organized into three shelves with different rules — `Sources/` (immutable inputs you fed in), `Wiki/` (LLM-written summaries, concepts, project state), and `Output/` (finished deliverables). `vaultlab.kb` is the package that owns that folder: it scaffolds the canonical layout, lints an existing KB against the schema, builds the auto-generated table-of-contents indexes, retrieves notes by frontmatter, searches their text, and is the single source of truth for *where each kind of file goes*. It exists because META PRINCIPLE #4 — "the KB is the smartness" — only works if the layout is enforced by code rather than remembered by an agent; the schema doc (`tools/knowledge-base-specification.md`) is the human canon, and this package is its machine-enforceable counterpart. Nearly every other vaultlab subsystem (research, figures, slides, analysis, dossier, feedback) reaches through `vaultlab.kb.paths` to decide where to write and reads back through retrieval/search before it acts.

## Public surface

These are the symbols exported from the package root (`vaultlab.kb.__init__`):

- `scaffold_kb` (alias `setup`) — create the canonical folder skeleton for a new project KB and populate `START_HERE.md`, `_Index.md`, `_Catalog.md`, `_Log.md`.
- `lint_kb` (alias `lint`) — audit an existing KB folder against the canonical schema; returns a severity-ranked `LintReport`.
- `build_indexes` — (re)generate `_Index.md`, `_Catalog.md`, and `_BackLinks.md` from frontmatter + wikilink scanning; deterministic (re-running on an unchanged tree produces a byte-identical result).
- `retrieve_by_frontmatter` — return every markdown file under a KB whose YAML frontmatter matches a filter (AND across keys; `set` values give OR-within-a-key).
- `LintReport` — the structured lint result; carries `.findings`, a `.summary` count, and `.passed` / `.shippable` predicates, and can `render_markdown()`.
- `LintFinding` (alias `LintIssue`) — one lint issue: `severity` (`fail`/`warn`/`info`), `kind`, `path`, `message`, suggested `fix`.
- `ScaffoldError` — raised when `scaffold_kb` hits a precondition failure (folder already exists without `force=True`, or an unknown domain-extension key).

The rest of the subpackage is real and importable, just not yet re-exported from the root — reach it by module path:

- `vaultlab.kb.paths` — the canonical path router. Every file-writing module routes through here. Covers `Sources/` inputs (`pdf_path`, `fulltext_md_path`, `article_stub_path`, `search_log_path`), `Wiki/` LLM content (`summary_path`, `concept_path`, the `papers_index_path` / `papers_index_md_path` corpus ledger, and the per-project state files `project_state_path` / `project_decisions_path` / `project_intake_path` / `project_papers_path` / `project_lineage_pointer_path`), and `Output/` deliverables (`project_dir`, `deck_path`, `deck_plan_path`, `figure_path`, `evidence_path`, `run_dir`, `turn_path`, `transcript_path`) — plus the slug/label helpers (`slugify_topic`, `slugify_doi`, `author_year_label`, `format_author_lastname`, `ensure_parent`). The slug/label helpers absorb the real-world mess: `slugify_doi` strips URL prefixes + stray file extensions and lowercases; `format_author_lastname` recovers the surname from NCBI (`Last F`), CSL (`Last, First`), and OpenAlex (`F. Last`, `J. Kennedy-Darling`) forms, normalizing unicode hyphens.
- `vaultlab.kb.semantic_search` — `search(...)` over the KB returning ranked `SearchHit`s (path + score + snippet); TF-IDF baseline always available (pure-Python, no deps), optional `sentence-transformers` embedding backend that falls back to TF-IDF with a warning if the dep is missing. `index_kb(...)` pre-builds the index (mostly useful for the embeddings backend; TF-IDF is fast enough to skip it). Scans the canonical `Sources/` / `Wiki/` / `Output/` subdirs by default.
- `vaultlab.kb.ingest` — `ingest(...)` dispatcher that turns a markdown / PDF / BibTeX / RIS file or a whole folder into one or more normalized `KbDocument`s (kind + title + body + source + frontmatter metadata + slug). Implemented today: markdown (preserves frontmatter), pdf (pypdf text + first-2-pages DOI sniff), bibtex + ris (one doc per record), folder (recursive, skips `.git`/`.obsidian`/`__pycache__`/…). Stubbed with a clear `NotImplementedError`: url, doi, pmid, zotero, notebooklm. `registered_ingestors()` introspects the registry (so a help surface can list what's supported).
- `vaultlab.kb.start_here` — auto-maintains each project's `START_HERE.md` so a session never re-starts from zero: `init_start_here` (on onboarding), `update_start_here` (append an activity line + refresh the resume-files list + queue open questions; caps the recent-activity list, preserves manual edits), and `read_start_here` (structured read-back). Lives at `Wiki/Projects/<slug>/START_HERE.md`.
- `vaultlab.kb.feedback` — async-first feedback channels: `open_question` (numbered grill doc, auto-opened in Obsidian, returns a `GrillDoc` with the `bobby-kb open` command), `log_decision` (append a reasoned entry to `decisions-log.md`, returns the `Path` to that file — `DecisionEntry` is the internal render shape, not the return value), and `unread_docs_summary` (list grill / decisions-log / START_HERE files modified since a threshold, for end-of-turn surfacing).
- `vaultlab.kb.dossier` — the standing Layer-0 project mental model (`Wiki/Projects/<slug>/Project-Dossier.md`): `compile_dossier` synthesizes 9 canonical sections (origin, current state, methodology commitments, established findings, frontier, literature backdrop, cross-project connections, anticipated PI questions, recent rolling tail) from KB sources, with a freshness gate (skips recompile under 24h unless `force=True`) and auto-archival of the prior version; `load_dossier` reads it back; `dossier_age_hours` / `dossier_path` / `dossier_archive_dir` are the resolvers. `vaultlab.kb.dossier_html` renders a compiled `Dossier` as a single-file tabbed HTML report.
- `vaultlab.kb.snapshot` — `create_snapshot` / `list_snapshots` / `restore_snapshot`: point-in-time tar.gz backups under `_Snapshots/` before risky operations. Restore is destructive and guarded — it requires `confirm=True` and refuses path-traversal archive members.
- `vaultlab.kb.tools_index` — curated catalog of 12 analysis packages (`load_index`, `suggest_for_topic`, plus tiered `summary_for` / `deep_doc_for` so the LLM reads one-paragraph TL;DRs first and dives into the full doc only for the 1-3 packages it picks) the LLM consults before web-searching, so it cites real functions from real packages. `load_external_repos` reads the lab-collaborator-repo registry (`external_repos.toml`). The `discovery` submodule auto-grows the catalog: `detect_tool_signature` / `extract_tool_metadata` spot a tool-introducing paper and pull its name / language / install / repo / domains, `save_discovered_tool` writes it to `packages/discovered/`, `is_already_known` dedupes against curated + discovered + external, and `promote_to_curated` graduates a discovered entry.
- `vaultlab.kb.obsidian` — Obsidian vault setup (`init_vault`, `configure_plugins`, `write_templates`), install detection (`detect_install`), and the `bobby-kb open` / `vaultlab kb open` deep-link launcher (`open_in_obsidian`, which auto-detects the open vault and prefers the Advanced URI plugin for new-tab opens). See its own README.

## How it fits

`vaultlab.kb` sits at the centre of the pipeline as the persistence layer. It **reads from** the user's KB folder (whose root is resolved upstream by `vaultlab.context`) and from frontmatter the other subsystems write. It is **written to** by essentially every artifact-producing primitive: `vaultlab.research` files paper stubs, full text, and per-paper summaries via `paths`; `vaultlab.figures` and `vaultlab.slides` write deliverables under `Output/`; `vaultlab.analysis` and the multi-agent runner file run transcripts; orchestrators read `dossier`, `start_here`, and `retrieve_by_frontmatter` for context before they act and append to `feedback`'s decisions log afterward. In one line: other subsystems compute, `vaultlab.kb` remembers — and the only way a later step learns what an earlier step produced is by reading what the earlier step wrote here.

Several slash commands route directly into this package, so its primitives are user-facing even when the user never imports Python: `/init-kb` and `/start-project` / `/onboard-project` / `/onboard-me` call `scaffold_kb` + `init_start_here`; `/audit-kb` calls `lint_kb`; `/refresh-dossier` calls `compile_dossier`; `/find-tool-for` calls `tools_index`; and any command that writes a deliverable (e.g. `/build-deck`) routes its output paths through `paths`. The `vaultlab init` CLI command persists the KB root; the broader `vaultlab kb …` subcommand surface referenced elsewhere is not yet wired in this source tree (the `cli/` modules are placeholders).

## What it does NOT do

- It does not resolve *which* KB root or project is active — that's `vaultlab.context` / `vaultlab.config`'s job; the path helpers take an explicit `kb_root` so callers stay in control.
- It does not run the science. `ingest`, `search`, and the indexes store and retrieve; correctness of the content comes from the research, analysis, and citation steps that feed it.
- It does not auto-create directories from a path builder. `vaultlab.kb.paths` functions return a `Path` and leave the `mkdir` to the caller (typically via `ensure_parent`) — by design, so path computation stays side-effect-free.
- It does not version or roll back files for you beyond the append-only decisions log and the explicit `snapshot` archives; longer history relies on your own synced drive / git.
- It does not itself call an LLM to write content. `compile_dossier` and `start_here` assemble *skeletons* — they gather and excerpt the right source files into the canonical structure, and a downstream Claude Code pass (or a manual edit) refines the prose. Likewise `tools_index.discovery` uses regex heuristics, not a model, to spot tool-introducing papers — treat a discovered entry as a draft to verify, not a verified fact.

## Files

- `setup.py` — `scaffold_kb`, `lint_kb`, `LintReport`/`LintFinding`, `CANONICAL_FOLDERS`, `DOMAIN_EXTENSIONS` (opt-in folders for equities / tax / metabolism / spatial-omics project types).
- `indexes.py` — `build_indexes`: deterministic `_Index.md` (grouped by `type:`) / `_Catalog.md` (chronological by `created:`) / `_BackLinks.md` (wikilink referrers).
- `retrieve.py` — `retrieve_by_frontmatter`: structured frontmatter-filter lookup (cascade layer 2; AND across keys, OR within a `set`-valued key; tolerant of malformed YAML).
- `paths.py` — canonical path router + slug/label helpers; single source of truth for where files go. Builders are side-effect-free (no `mkdir`).
- `semantic_search.py` — TF-IDF (default, dependency-free) / optional embedding `search` over the KB, plus `index_kb` pre-caching and the `SearchHit` result type.
- `start_here.py` — per-project `START_HERE.md` auto-update (`init_start_here` / `update_start_here` / `read_start_here`).
- `feedback.py` — `open_question` / `log_decision` / `unread_docs_summary` async-first channels (+ `GrillDoc` / `DecisionEntry` result types).
- `dossier.py`, `dossier_html.py` — project-dossier compile/load (9 sections, freshness gate, auto-archive) + single-file tabbed HTML render.
- `snapshot.py` — tar.gz KB backups; `restore_snapshot` is guarded (`confirm=True`, path-traversal refused).
- `ingest/` — pluggable source ingestors (markdown, pdf, bibtex, ris, folder implemented; url / doi / pmid / zotero / notebooklm stubbed) → `KbDocument`, behind a self-registering dispatcher.
- `tools_index/` — curated analysis-package catalog (12 packages) + tiered summary/deep-doc access + external-repo registry (`external_repos.toml`) + `discovery.py` auto-detection of tool-introducing papers (`packages/discovered/`).
- `obsidian/` — Obsidian vault setup, plugins, and deep-link open (`init_vault`, `configure_plugins`, `write_templates`, `detect_install`, `open_in_obsidian`).
- `cli/` — placeholder for the `vaultlab kb …` subcommands (not yet wired; `vaultlab init` lives in `vaultlab.cli`).
- `retrieve.md` — the layered "researcher pathway" retrieval cascade (corpus → frontmatter → indexes → wikilink walk → cumulative recall).
- `obsidian/README.md`, `tools_index/README.md` — sub-package docs.

## See also

- [`vaultlab.kb.obsidian` README](obsidian/README.md) — vault setup + the `vaultlab kb open` deep-link mechanism.
- [`vaultlab.kb.tools_index` README](tools_index/README.md) — the analysis-package catalog the LLM reads before web-searching.
- [`retrieve.md`](retrieve.md) — the full layered-retrieval doc this package's retrieval/index primitives implement.
- [`docs/architecture.md`](../../../docs/architecture.md) — where `vaultlab.kb` sits in the whole system.
- `tools/knowledge-base-specification.md` (in the KB) — the human-readable schema canon `setup.py` enforces.
- `vaultlab.research` (the main writer into this KB) and `vaultlab.context` (the root-resolver upstream) — the two packages that bracket `vaultlab.kb` in the pipeline.
