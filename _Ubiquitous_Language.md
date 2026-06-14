# Ubiquitous Language — vaultlab

Shared, plain-English domain vocabulary for vaultlab. **Bobby and AI sessions use these exact terms with these exact meanings.** When you catch yourself or a thinking trace using a term differently — or inventing a synonym — that's drift: update this file so the term stays single-valued. Definitions are project-specific on purpose; the AI-generic reading of a word ("a cache is a store of recent data") is never what's meant here.

Scope: the whole `vaultlab` package + its slash commands + its KB. Companion to [`CLAUDE.md`](CLAUDE.md) (architecture philosophy) and [`READ_FIRST.md`](READ_FIRST.md) (dispatch cheat sheet); the plain-language tour is `Wiki/Concepts/vaultlab-subsystems.md` in the KB.

Tables are grouped by category: **Domain entities · Operations · Components / modules · States / statuses · Files / artifacts.** Each row: Term | Definition | Aliases | Used in.

---

## Domain entities

The nouns vaultlab reasons about — the papers, panels, contracts, and records that move through the pipeline.

| Term | Definition | Aliases | Used in |
|------|------------|---------|---------|
| Knowledge base (KB) | One plain folder of Obsidian-style markdown notes per research project — vaultlab's long-term memory and persistence layer; every task reads it before starting and writes back when done. | "the notebook", "the vault", "project memory" | everything; `kb/`, `context/` |
| Corpus | A topic-scoped collection of papers plus their backward/forward citation edges — the unit of literature analysis a lit-arc runs over. | "the collected set" | `research/`, `workflows/`, `figures/acquisition` |
| Paper | The canonical paper-metadata record (DOI/PMID, title, authors, year, journal, citation count) passed between every research stage. | — | `research/` |
| Summary card | A one-page, page-cited reading of one deep-read PDF (TL;DR, why-it-matters, methods, key findings), where **every finding carries a `[pN]` page marker** or is dropped. | "Tier-A card", "Tier-A summary", "reading card", `Wiki/Summaries/<doi>.md` | `research/summarize.py`, KB `Wiki/Summaries/` |
| Influence map | The who-cites-whom citation graph built outward from seed papers — distinguishes a *foundational* paper from one that is merely *loud*, and reaches forward to recent work the seeds are too old to know. | "citation graph", "lineage map" | `research/citation_graph.py`, `graph_metrics.py` |
| Recipe | One of eleven flat `<recipe>.py` + `<recipe>.md` figure-archetype modules; each exposes `render(...) -> Path`, a `RECIPE_VERSION`, and an `ANCHOR_PAPERS` tuple citing ≥3 published examples. | "chart layout", "figure recipe" | `figures/recipes/` |
| Anchor papers | The ≥3 published figures a recipe is copied from — the citation that makes "why this layout" answerable instead of "Claude guessed". | `ANCHOR_PAPERS`, "anchor set" | `figures/recipes/`, `figures/corpus/sources.json` |
| Figure contract | The pre-plotting commitment a figure must sign before any plotting code runs: (1) one-sentence conclusion, (2) per-panel evidence chain, (3) archetype, (4) Python-or-R backend, (5) export targets. A panel with no unique evidence is a *rigor* issue, not a style nit. | "the contract", `FigureContract` | `figures/contract.py` |
| Role | A named agent persona (analyst, critic, synthesizer, …) with a fixed posture, loaded from a `roles/<id>/prompt.md` + `metadata.yaml` pair and rendered into a per-task system prompt. | "persona", "agent role" | `roles/`, `runner/`, `workflows/` |
| Critic | The internal panel role that pressure-tests a finding and writes a markdown verdict — a rating plus priority-tagged next-round tests. A **methods critic** attacks statistical rigor; a **literature critic** weighs source quality/consensus. | "the reviewer" | `roles/`, `workflows/`, `parsers/` |
| Meeting | A multi-role internal session config — a topic, a list of roles, and a mode saying how those roles see each other's output. | "panel", "round-table" | `runner/meetings.py` |
| Agenda | The shared frame injected into every agent's prompt — a statement, the questions that must be answered, and the rules that must be obeyed — so all roles answer the same question under the same constraints. | — | `runner/`, `workflows/` |
| Linked repo | A separate code repository associated with a vaultlab project so crosstalk meetings can read its source files and recent git changes as context. | "code repo", `/link-repo` | `context/` |
| Project dossier | The standing, source-cited Layer-0 mental model of an entire project, compiled on a cadence and loaded before non-trivial primitives run. | "the dossier", "Layer 0" | `/refresh-dossier`, `context/` |
| Citation | One extracted citation under audit: raw text, authors, year, claim, source file+line, identifiers, plus the verification outcome (status, risk, evidence, hallucination flags). | — | `citations/` |
| Reviewer-response letter | A point-by-point editor-facing reply where each reviewer comment gets a stable ID, a classification, and a planned action. | "response letter" | `manuscript/`, `/respond` |

## Operations

The verbs — what a session *does* to entities. vaultlab's stance is dispatch-first: reach for the primitive before free-form markdown.

| Term | Definition | Aliases | Used in |
|------|------------|---------|---------|
| lit-arc | The flagship literature pipeline: search → influence map → most-open-first PDF acquisition → page-cited summary cards → a 3-paragraph lineage arc, all written into the KB. | "lineage arc", "run_lit_arc", `/lit-arc` | `research/lineage.py` |
| crosstalk | vaultlab's multi-agent internal meeting where role-playing analyst/critic/synthesizer agents draft, challenge, and reconcile a finding over bounded rounds (hard cap 5). | "the panel", "multi-agent meeting", "round-table" | `workflows/crosstalk.py`, `runner/meetings.py` |
| deep-think round | One bounded iteration of the multi-agent reasoning loop; round N's agenda is built from round N-1's parsed Critic tests. | — | `workflows/deep_think.py` |
| state-aware preflight | The pre-run glob of prior outputs (KB `Output/` + target out-dir) so an artifact-producing primitive **extends** existing work instead of starting from zero (CLAUDE.md commitment #6). | "preflight", `state_aware_preflight()` | target across primitives |
| compose-preamble | Assemble a project's known KB state (START_HERE, recent decisions, top summaries, recent outputs) into a token-budgeted preamble prepended to a spawned sub-agent's prompt, so sessions never zero-shoot. | "KB-context preamble", "context preamble" | `runner/`, `workflows/` |
| scope discipline | The runtime rule that the analysis pipeline consumes *post-analysis tidy tables* and **rejects** raw-data formats (FASTQ/BAM/HDF5/microscopy/mass-spec), raising a `ValueError` that points back at the user's analysis code. | "consumes-not-computes" | `analysis/`, `/run-analysis` |
| verification-only recompute | The sanctioned carve-out from scope discipline: recomputing a Welch's t-test on already-tidy two-group values as a faithfulness check, surfaced as a hedged line — never a substitute for upstream inference. | — | `analysis/stats.py` |
| verify-citation | The per-citation audit: find the paper → check hallucination risks → match the claim against the real pages → set status + risk → cache + write back. Refuses to bless any citation it cannot read for itself. | "citation audit", `/cite verify` | `citations/verifier.py` |
| enforce-hedge | A deterministic guardrail that flags a narrow set of overclaiming phrases so generated scientific text stays in hedged voice. | "hedge check" | `roles/_guardrails.py` |
| verify-numeric | A deterministic (non-LLM) check scanning generated text for reported statistics and flagging inconsistent/implausible values (p outside [0,1], non-positive n, mean outside its stated range). | "numeric check" | `runner/verifiers.py` |
| ingest | Normalize an external source (paper, meeting transcript, note) into a frontmatter+body `KbDocument` filed in the KB. | — | `kb/` |
| scaffold / lint / index a KB | Three KB-maintenance verbs: create the canonical folder skeleton (`scaffold_kb`); health-check it against the schema (`lint_kb`); (re)generate `_Index`/`_Catalog`/`_BackLinks` (`build_indexes`). | "init-kb", "audit-kb" | `kb/`, `/init-kb`, `/audit-kb` |
| onboard a project | Run the intake-form + folder-scan flow that writes START_HERE, decisions-log, saved intake, and `.vaultlab-project.json` so later commands resume without re-interviewing. | "onboarding", `/onboard-project` | `onboarding/` |
| review-deck (self-review) | The composite quality pass over a rendered `.pptx` — layout hard rules, descriptive titles, bullet density, figure presence, story arc; core checks are deterministic and LLM-free, and it exits non-zero on any critical issue. | "slides self-review", "deck audit" | `slides/`, `/review-deck` |
| triple-export | Contract-grade save of a matplotlib figure to SVG + PDF + 600 DPI TIFF (editable-text vector + raster) for camera-ready output. | — | `figures/contract.py` |
| compare-to-actual | Diff a pre-registered plan against what an analysis run actually did, surfacing deviations as warnings. | "deviation check" | `plan/` (planned) |

## Components / modules

The code structures and standing facilities — facades, runners, registries, and cross-cutting plumbing.

| Term | Definition | Aliases | Used in |
|------|------------|---------|---------|
| Companion mode | vaultlab's defining stance: it *accompanies* the user's actual work with full life-context (KB + Google + Outlook + meetings) rather than autonomously generating research questions or running studies. | "companion, not autonomous" | whole system; `context/` |
| Research-companion context pipes | The optional Google / Outlook / meetings / linked-repo integrations that pull a researcher's life-context into the LLM prompt. | "context pipes", "life-context" | `context/google/`, `context/outlook/` |
| ResearchClient | The search/retrieve/verify facade: on construction it auto-discovers API keys and wires NCBI/PubMed, Springer, Semantic Scholar, CrossRef, bioRxiv, and the Elsevier/Scopus cluster, then delegates to `unified_search`. | "the research client" | `research/__init__.py` |
| unified_search | The fan-out search entry point: queries each source concurrently under one wall-clock deadline, dedups by DOI (PubMed-preferred merge), and re-ranks by a recency-blended citation score. | "federated search" | `research/search.py` |
| Elsevier/Scopus cluster | vaultlab's Elsevier-backed source — search runs against the Scopus API (ScienceDirect search is unsupported); the same Elsevier key also feeds the Elsevier tier of the PDF waterfall. | "elsevier", "sciencedirect" (aliases) | `research/sources/elsevier.py` |
| Content-aware picker | The step that reads abstracts to choose the deep-read set rather than trusting citation rank alone — overrides `og_score` when the citation signal disagrees with the content. | "the picker" | `research/picker.py` |
| Papers ledger | The corpus ledger: one row per paper (PDF JOINed to summary on DOI-slug), rebuilt from disk so multi-run fetch/read stays idempotent. | "papers catalog", "papers index", "corpus ledger", `PapersIndex` | `research/papers_index.py`, `/papers-index` |
| Claude-Code-callable path | The no-SDK execution mode: each LLM step exposes a `prepare_*(task)` / `render_*_from_response(text)` pair plus a `*_response_schema`, so the active Claude Code session **is** the model — no Anthropic API key needed. | "no-SDK path", "callable path" | `research/`, `slides/`, runner |
| ClaudeCodeRunner | The in-session planner: turns a Meeting into a `RunPlan` that a slash command executes by spawning the Agent tool once per step. | "the runner" | `runner/` |
| LocalRunner | The secondary executor: same planner, but runs each step against the Anthropic API directly (or fills no-cost dry-run stubs when given no client). | — | `runner/` |
| Researcher-pathway retrieval cascade | The layered way context is pulled — corpus → frontmatter filter → indexes → wikilink walk → cumulative/semantic recall — mirroring how a researcher who knows a project finds things. | "the retrieval cascade" | `kb/` |
| Canonical path router | `vaultlab.kb.paths` — the single source of truth for where each kind of file is written in a KB; every file-producing module routes through it instead of hand-building paths. | "kb.paths" | `kb/paths.py` |
| Locations registry | Per-user `~/.config/vaultlab/locations.toml` mapping dotted slugs (e.g. `work_log.google_doc_id`) to standard paths so vaultlab doesn't re-ask each session. | "locations.toml" | `context/`, `cli/` |
| User memory | Per-user auto-memory under `~/.config/vaultlab/user_memory/` that persists calibration (feedback/preference/pattern/project) across sessions. | "auto-memory" | `context/user_memory.py` |
| Single-file HTML report | vaultlab's standard report artifact: one offline-readable `.html` with inline CSS + vanilla JS, no CDN or web fonts — emailable and phone-readable. | "the HTML report" | `report/` |
| Placeholder package | A reserved namespace whose `__init__.py` is a docstring-only stub exporting nothing — awaiting migration commits, **not safe to depend on**. | "reserved namespace", "package slot", "stub package" | `cache/`, `errors/`, `evaluate/`, `observability/`, `plan/`, `prompts/`, `status/`, `stats/`, `data/<modality>/` |
| Cross-cutting concern | Plumbing (error handling, observability) shared across many packages rather than owned by one feature. | — | `errors/`, `observability/` |
| Content-addressable cache | A store keyed by a hash of its inputs, so an identical later request returns the cached result instead of recomputing. | "the cache" | `cache/` (reserved), `research/` |

## States / statuses

The lifecycle words — the literal enum/flag values to branch on. Match the **full** string, never a truncated form.

| Term | Definition | Aliases | Used in |
|------|------------|---------|---------|
| VerificationStatus | The six citation outcomes: `VERIFIED_FULLTEXT`, `VERIFIED_ABSTRACT`, `API_CONFIRMED`, `UNVERIFIED`, `SUSPECT`, `CONTRADICTED`. A located paper whose claim was never checked against text is `UNVERIFIED`, **never** `API_CONFIRMED`. | "citation status" | `citations/` |
| RiskLevel | `LOW` / `MEDIUM` / `HIGH` derived from status + hallucination flags. Any flag, or SUSPECT/CONTRADICTED, is HIGH; an UNVERIFIED citation *with a claim* is MEDIUM (never LOW). | — | `citations/` |
| Hedged voice | vaultlab's mandatory output register: claims read as "consistent with X" / "appears to X", never "proves X" or "X is Y". | "hedged", "the hedge rule" | `roles/`, all LLM output |
| crosstalk_status | How an adversarial meeting ended — exactly one of `"complete"`, `"converged"`, `"incomplete (timeout)"`, `"fallback (callback failed)"`. Branch on the full string. | — | `workflows/crosstalk.py` |
| rating | A Critic verdict keyword on a finding — `ROBUST`/`NEEDS_VALIDATION`/`WEAK`/`UNSUPPORTED` for data, or `STRONG_CONSENSUS`/`EMERGING_EVIDENCE`/`SINGLE_STUDY`/`CONTESTED` for literature. | "verdict" | `parsers/`, `workflows/` |
| InvestigationMode | Whether a task is `EXPLORATORY` (no committed direction; survey broadly) or `DIRECTED` (a direction exists; harden and defend it). | — | `runner/`, `workflows/` |
| MeetingMode | How roles see each other's work: `round_table` (parallel/blind), `adversarial` (sees prior outputs), `synthesis` (one integrator), `individual`, `team`, or `critiqued`. | "meeting mode" | `runner/meetings.py` |
| Mode (data vs lit) | The axis deciding whether a meeting's analyst/critic slots are filled by data-analysis roles or literature-review roles (`data_analysis` vs `literature_review`). | — | `runner/`, `roles/` |
| extend mode | A run mode that reads prior runs via the preflight and does not overwrite identically-named outputs already present — keeping operations additive (vs `--fresh` / `--branch` / `--variant`). | "additive mode", "--extend" | across primitives |
| degraded fallback | A flagged, lower-fidelity result returned when an LLM/API call fails, instead of crashing or pretending success. | "degraded result" | `errors/` (reserved), `workflows/` |
| FigureAcquisitionResult.source | Which tier produced an acquired figure: `"pmc-tar"`, `"elsevier-api"`, `"springer-api"`, `"cache"`, or `"unavailable"`. No tier ever mines images from a PDF. | "acquisition source" | `figures/acquisition.py` |
| policy-skipped paper | A paper the LLM refused to summarize, recorded in a project's `policy_skipped.json` for human triage. | — | `research/policy_skip.py`, `/list-policy-skipped` |
| wired-but-dormant source | A literature source whose plumbing exists (`unified_search`/`acquire_pdf` accept it) but which no default code path constructs/injects — the paperclip 8M-paper corpus is the canonical example. | "dormant source" | `research/sources/paperclip.py` |
| AUTHOR_INPUT_NEEDED | The response-action flag marking a reviewer comment that can't be drafted until the author makes a judgement call. | — | `manuscript/`, `/respond` |

## Files / artifacts

The on-disk things a run reads or drops — the persistence + audit-trail layer.

| Term | Definition | Aliases | Used in |
|------|------------|---------|---------|
| Tidy result table | A post-analysis CSV/Parquet/TSV with one header row and one observation per row — the **only** input format the analysis pipeline accepts. | "results table", "tidy table" | `analysis/`, `figures/recipes/` |
| Provenance receipt | The `.provenance.json` (machine-readable) + `.method.md` (human-readable methods narrative) sidecar pair written next to **every** vaultlab output, recording inputs, hashes, params, seed, model, and how it was made (AGENTS.md Red Line #2). | "provenance sidecar", "receipt", "method.md sidecar" | `provenance/`; written by nearly every package |
| Sources / Wiki / Output (three-shelf layout) | The canonical KB structure — `Sources/` holds immutable inputs, `Wiki/` holds LLM-written summaries/concepts/state, `Output/` holds finished deliverables. | "the three shelves" | `kb/` |
| START_HERE.md | Per-project daily brief (newest day on top), auto-maintained after meaningful work, so a fresh session never re-starts from zero. | "the brief", "resume page" | `kb/start_here.py` |
| decisions-log.md | Append-only per-project record of design/scope decisions, so later work doesn't relitigate settled questions (e.g. "we use spearman after Round 8"). | "decisions log" | `kb/`, `onboarding/` |
| grill doc | A markdown open-question document written to the KB (instead of blocking the chat) when vaultlab needs decisions or missing config — `grill-<topic>-<date>.md`. | "open-question doc" | `kb/feedback.py` |
| .vaultlab-project.json | The per-project machine-readable config (schema `vaultlab-project/v1`) written at onboarding so future commands recover slug/topic/KB root without re-asking. | "project config" | `onboarding/` |
| .bobby-project.json | The **legacy** per-project settings file (name, kb_path, domain, target journal, dirs, hypotheses, significance thresholds) read by `vaultlab.config`. Distinct from the newer companion-mode `.vaultlab-project.json`. | "legacy project config" | `config/` |
| KB root | The user-chosen top-level directory of a knowledge base, set once by `vaultlab init`, persisted to `locations.toml`, and resolved by `resolve_kb_root` before any read/write. | "the vault root" | `context/`, `cli/` |
| Draft Methods paragraph | A template-composed (no-LLM) markdown methods blurb the analysis pipeline emits, citing each input file, column, and figure with column-level sample sizes, closing in hedged voice. | "methods.md" | `analysis/` |
| Intake form | A structured markdown file (`project_intake.md`) the user fills in once so onboarding can ask 3-5 follow-ups instead of 30. | "the intake" | `onboarding/` |
| Manual-fetch shopping list | The publisher-clustered list of paywalled DOIs `vaultlab fetch-list paywalled` emits, with URL hints and a drop-the-PDF-here path for papers the free waterfall couldn't get. | "manual link list", "fetch list" | `research/`, `/fetch-list` |
| Journal guideline (yaml) | Per-target-journal enforceable figure/font/color/stats-reporting rules (`nature`/`cell`/`elife`/`biorxiv` + a cross-journal `_common.yaml`), point-in-time snapshots refreshed by editing, not by network call. | "journal_guidelines/*.yaml", "house-style rules" | `data/journal_guidelines/`, `roles/_invoke` |
| Demo seed | `demo/paper.json` (Bhate et al., *Cell Systems* 2022 metadata) + `demo/figures/*.png` — the deterministic, no-LLM/no-network seed behind `vaultlab demo`. | "the demo data" | `data/demo/`, `cli/demo` |
| figure-index.json | A per-project cross-figure pairing index answering "this figure pairs with…" via a dominant-color pixel signature plus a same-recipe bonus. | "figure index" | `figures/index.py` |
| Meeting transcript | A recorded-meeting transcript ingested into `<kb>/Sources/Meetings/<date>-<slug>.md` with vaultlab frontmatter, searchable via the KB index. | — | `context/`, `kb/` |
| Data Availability Statement (DAS) | The journal-required statement saying where each result-supporting dataset lives, what identifier resolves to it, and what access restrictions apply — audited against the 14-item FAIR checklist. | "DAS" | `manuscript/`, `/das-audit` |
| Polish report | A markdown audit of a manuscript draft flagging over-length sentences and US spellings (the 25 frozen `PolishRule`s), written with provenance sidecars. | — | `manuscript/`, `/polish` |
| JSONL trace | A line-per-step machine-readable record of a primitive's execution, written for after-the-fact inspection; diagnostic, not load-bearing. | "execution trace", "search/acquisition trace" | `observability/` (reserved), `research/` |
| Slim barrel | vaultlab's top-level `__init__.py`, which deliberately re-exports only `__version__`; `config` and other symbols must be imported from their submodule directly. | — | `__init__.py` |

---

*Anti-claim to remember: the `journal_guidelines/*.yaml` rules are wired into the **audit roles**, not into the figure recipes — several `recipes/*.md` cite `cell.yaml`/`_common.yaml` as an authoring convention, but the recipe `.py` files hardcode their own colorblind-safe palettes and never load the YAML. There is no executable link from `journal_guidelines` to `vaultlab.figures`.*
