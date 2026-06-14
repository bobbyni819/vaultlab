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

- `vaultlab.kb.paths` — the canonical path router. Every file-writing module routes through here (`pdf_path`, `summary_path`, `concept_path`, `deck_path`, `figure_path`, `run_dir`, …) plus the slug/label helpers (`slugify_topic`, `slugify_doi`, `author_year_label`, `format_author_lastname`, `ensure_parent`).
- `vaultlab.kb.semantic_search` — `search(...)` over the KB; TF-IDF baseline always available, optional `sentence-transformers` embedding backend.
- `vaultlab.kb.ingest` — `ingest(...)` dispatcher that turns a markdown/PDF/BibTeX/RIS file or a folder into a normalized `KbDocument` (url / doi / zotero / notebooklm are stubbed and raise with guidance).
- `vaultlab.kb.start_here` — auto-maintains each project's `START_HERE.md` (`update_start_here`, `init_start_here`) so a session never re-starts from zero.
- `vaultlab.kb.feedback` — async-first feedback channels: `open_question` (numbered grill doc), `log_decision` (append to `decisions-log.md`), `unread_docs_summary`.
- `vaultlab.kb.dossier` — `compile_dossier` / `load_dossier`: the standing Layer-0 project mental model, refreshed on a cadence.
- `vaultlab.kb.snapshot` — `create_snapshot` / `list_snapshots` / `restore_snapshot`: point-in-time tar.gz backups before risky operations.
- `vaultlab.kb.tools_index` — curated catalog of analysis packages (`load_index`, `suggest_for_topic`) the LLM consults before web-searching, so it picks real functions from real packages.
- `vaultlab.kb.obsidian` — Obsidian vault setup, plugin config, and `vaultlab kb open` deep links (see its own README).

## How it fits

`vaultlab.kb` sits at the centre of the pipeline as the persistence layer. It **reads from** the user's KB folder (whose root is resolved upstream by `vaultlab.context`) and from frontmatter the other subsystems write. It is **written to** by essentially every artifact-producing primitive: `vaultlab.research` files paper stubs, full text, and per-paper summaries via `paths`; `vaultlab.figures` and `vaultlab.slides` write deliverables under `Output/`; `vaultlab.analysis` and the multi-agent runner file run transcripts; orchestrators read `dossier`, `start_here`, and `retrieve_by_frontmatter` for context before they act and append to `feedback`'s decisions log afterward. In one line: other subsystems compute, `vaultlab.kb` remembers — and the only way a later step learns what an earlier step produced is by reading what the earlier step wrote here.

## What it does NOT do

- It does not resolve *which* KB root or project is active — that's `vaultlab.context` / `vaultlab.config`'s job; the path helpers take an explicit `kb_root` so callers stay in control.
- It does not run the science. `ingest`, `search`, and the indexes store and retrieve; correctness of the content comes from the research, analysis, and citation steps that feed it.
- It does not auto-create directories from a path builder. `vaultlab.kb.paths` functions return a `Path` and leave the `mkdir` to the caller (typically via `ensure_parent`) — by design, so path computation stays side-effect-free.
- It does not version or roll back files for you beyond the append-only decisions log and the explicit `snapshot` archives; longer history relies on your own synced drive / git.

## Files

- `setup.py` — `scaffold_kb`, `lint_kb`, `LintReport`/`LintFinding`, `CANONICAL_FOLDERS`, `DOMAIN_EXTENSIONS`.
- `indexes.py` — `build_indexes`: deterministic `_Index.md` / `_Catalog.md` / `_BackLinks.md`.
- `retrieve.py` — `retrieve_by_frontmatter`: structured frontmatter-filter lookup (cascade layer 2).
- `paths.py` — canonical path router + slug/label helpers; single source of truth for where files go.
- `semantic_search.py` — TF-IDF / embedding `search` over the KB.
- `start_here.py` — per-project `START_HERE.md` auto-update.
- `feedback.py` — `open_question` / `log_decision` / `unread_docs_summary` async-first channels.
- `dossier.py`, `dossier_html.py` — project-dossier compile/load + HTML render.
- `snapshot.py` — tar.gz KB backups.
- `ingest/` — pluggable source ingestors (markdown, pdf, bibtex, ris, folder) → `KbDocument`.
- `tools_index/` — curated analysis-package catalog (12 packages) + external-repo registry.
- `obsidian/` — Obsidian vault setup, plugins, and deep-link open (`init_vault`, `open_in_obsidian`, …).
- `cli/` — CLI wiring for the KB subcommands.
- `retrieve.md` — the layered "researcher pathway" retrieval cascade (corpus → frontmatter → indexes → wikilink walk → cumulative recall).
- `obsidian/README.md`, `tools_index/README.md` — sub-package docs.

## See also

- [`vaultlab.kb.obsidian` README](obsidian/README.md) — vault setup + the `vaultlab kb open` deep-link mechanism.
- [`vaultlab.kb.tools_index` README](tools_index/README.md) — the analysis-package catalog the LLM reads before web-searching.
- [`retrieve.md`](retrieve.md) — the full layered-retrieval doc this package's retrieval/index primitives implement.
- [`docs/architecture.md`](../../../docs/architecture.md) — where `vaultlab.kb` sits in the whole system.
- `tools/knowledge-base-specification.md` (in the KB) — the human-readable schema canon `setup.py` enforces.
- `vaultlab.research` (the main writer into this KB) and `vaultlab.context` (the root-resolver upstream) — the two packages that bracket `vaultlab.kb` in the pipeline.
