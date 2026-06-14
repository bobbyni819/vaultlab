# vaultlab.research

The literature engine: search many databases at once, build a citation graph from the hits, pull the PDFs it can legally get for free, read them into page-cited summary cards, and assemble the whole thing into a lineage arc or a deep-research review.

Plain-language companion: see the **Paper fetching / The influence map / Paper understanding / Paper indexing** sections of `vaultlab-subsystems.md` in the KB (`Wiki/Concepts/`). Architectural sketch: `docs/architecture.md` → "vaultlab.research".

## What it is

When a researcher asks Claude Code for a literature review, this is the package that does the actual work. It fans a topic out to PubMed, Semantic Scholar, CrossRef, bioRxiv, Springer, and the Elsevier/Scopus cluster, merges the duplicate hits by DOI, then expands outward into a who-cites-whom graph so a foundational paper can be told apart from one that is merely loud. It downloads the open-access PDFs along a most-permissive-license-first waterfall, hands each budgeted PDF to Claude to read into a one-page summary card where **every finding carries a `[pN]` page marker**, and writes all of it into the project's knowledge base as Obsidian markdown.

The `paperclip` 8M-paper full-text corpus is a **wired-but-dormant seventh source**: `unified_search` and the `acquire_pdf` waterfall both accept an optional `paperclip_client` (and `PaperclipClient` is a working CLI wrapper in `sources/paperclip.py`), but no orchestrator or `ResearchClient` currently constructs and injects that client — so on every default code path the paperclip branch stays off. Treat it as plumbing that exists but is not yet switched on, not as a live source.

It exists because literature search is the most-requested vaultlab capability and the easiest one to get quietly wrong — a hallucinated citation, a "foundational" ranking that just reflects citation-count noise, a summary finding floating free of any page. The package is built so that the orchestrators (`run_lit_arc`, `run_lit_report`) and the `/lit-arc`, `/lit-report`, `/lit-search`, and `/full-reader` slash commands all share one disciplined, idempotent pipeline. A distinctive design point: most LLM steps expose a **no-SDK "Claude-Code-callable" path** (a `prepare_*` / `render_*_from_response` pair) so the active Claude Code session is the model — no Anthropic API key required.

## Public surface

Search + retrieval client:

- `ResearchClient` — unified client over all configured literature APIs; `.search()`, `.get_paper()`, `.get_citations()`, `.verify_exists()`, `.download_pdf()`, claim-matching.
- `search_papers` — module-level convenience: spin up a client and search in one call.
- `get_paper` — fetch full metadata for one DOI or PMID.
- `download_pdf` — download a paper's PDF to a directory (returns path or empty string).
- `Paper` — the canonical paper-metadata record passed between every stage.

PDF acquisition (the waterfall):

- `acquire_pdf` — try Unpaywall → PMC → bioRxiv → Springer → Elsevier for one DOI, with `%PDF-` validation and a cached short-circuit.
- `acquire_pdfs_for_corpus` — run the waterfall across a whole corpus.
- `AcquisitionResult` — per-paper outcome (which tier succeeded, or why it failed).

Citation graph + metrics:

- `Corpus` — a topic-scoped collection of papers plus their backward/forward citation edges; the unit of analysis.
- `build_corpus_from_seeds` — grow a corpus by walking CrossRef references one hop out from seed papers.
- `expand_corpus` — extend an existing corpus with more hops / forward citations.
- `CitationGraph` — directed citation-network builder (depth-limited traversal, seminal-paper detection, Mermaid export).
- `compute_metrics` — produce `og_score`, `forward_influence`, co-citation pairs, and year buckets over a corpus.
- `CorpusMetrics` — the computed-metrics record.
- `CandidatePaper`, `PickerTask`, `PickerCallback`, `pick_top_n_content_aware`, `prepare_picker_task`, `render_picks_from_response`, `picker_response_schema` — the **content-aware picker**: read abstracts to choose the deep-read set rather than trusting citation rank alone.
- `BinningTask`, `BinningCandidate`, `BinningCallback`, `BinningResult`, `assign_buckets_with_llm`, `prepare_binning_task`, `render_binning_from_response`, `binning_response_schema` — LLM-driven HISTORY / DEVELOPMENT / SOTA bucketing that overrides the deterministic year quartiles.

Citation lookups (low-level):

- `get_references_via_crossref`, `get_citations_via_s2`, `get_influential_count_via_s2` — backward refs / forward citations / influential-citation count.
- `Reference` — a single citation edge. `RateLimitError` — raised when an API throttles.

Summarization + reading:

- `PaperSummary`, `summarize_paper`, `summarize_corpus`, `prepare_summary_task`, `render_summary_from_response`, `summary_response_schema`, `SummarizationTask`, `SummaryReader`, `SummarizeAuthError`, `write_summary_to_kb` — turn a PDF into a page-cited `Wiki/Summaries/<doi>.md` card (Tier-A full read or Tier-C stub).
- `extract_text`, `extract_and_save`, `batch_extract` — raw text extraction from PDFs.
- `extract_figures`, `write_figure_notes` — pull embedded figures + captions out of a PDF (extraction, not figure *generation*).
- `detect_data_format` — sniff what kind of data file an input is.

Orchestrators (end-to-end):

- `run_lit_arc` — the full `/lit-arc` pipeline: search → corpus → PDFs → summaries → lineage arc.
- `ArcTask`, `ArcNarrator`, `DepthLevel`, `LineageRunResult`, `prepare_arc_task`, `render_arc_from_response`, `arc_response_schema` — the lit-arc task/result types and its Claude-Code-callable path.
- `run_lit_report` — the `/lit-report` deep-research review (3000–5000 words, adversarial crosstalk per section).
- `ReportTask`, `ReportRunResult`, `Section`, `SECTION_ORDER`, `SECTION_ROLES`, `SECTION_WORD_TARGETS`, `build_section_prompt`, `prepare_report_task`, `render_section_from_response`, `section_response_schema` — the report's section schema and callable path.

Corpus ledger + session state:

- `PapersIndex`, `PaperEntry`, `scan_corpus`, `build_and_save`, `load_index`, `save_index`, `needs_fetch`, `needs_summary`, `summary_is_current` — the **papers ledger**: one row per paper (PDF JOINed to summary on DOI-slug), rebuilt from disk so multi-run fetch/read stays idempotent.
- `ResearchSession`, `Finding`, `FindingStatus` — programmatic state for multi-round reasoning runs (rounds, findings, their status through review).

Verification types (`TYPE_CHECKING`-only re-exports, materialized lazily inside `ResearchClient`): `VerificationResult`, `ClaimMatch`, `EvidenceRecord`.

## How it fits

**Reads from:** the configured API-key file (`research_apis.json`), the live literature APIs, and the project KB — existing PDFs in `Sources/Papers/`, summary cards in `Wiki/Summaries/`, and per-paper stubs in `Sources/Articles/`. The ledger and the acquisition cache make re-runs delta-only, so a session never re-downloads or re-reads what is already on disk.

**Writes to:** the project KB. A `run_lit_arc` pass lands a search log in `Sources/Notes/`, article stubs in `Sources/Articles/`, PDFs in `Sources/Papers/`, summary cards in `Wiki/Summaries/`, the lineage arc in `Wiki/Concepts/`, and provenance receipts (`.provenance.json` + `.method.md`) next to each artifact.

**Consumed by:** `vaultlab.workflows` (crosstalk reads the corpus + summaries), `vaultlab.citations` (claim verification reads the fetched papers), `vaultlab.slides` and `vaultlab.figures` (decks/figures built from the arc), and the `/lit-*` and `/full-reader` slash commands, which drive the Claude-Code-callable paths directly. It sits at the front of the pipeline: nearly everything downstream depends on the corpus this package assembles.

## What it does NOT do

- It does **not** rank by topic/content match during search — ranking is citations-plus-recency; relevance is judged later, from abstracts, by the content-aware picker.
- It does **not** break paywalls or log into an institution — gated papers it can't get legally become a manual link list, and `verify_exists` confirms existence, not access.
- It does **not** build a searchable index of full PDF text — only the summary *cards* are searchable; a sentence buried in a PDF that never reached a card cannot be pinpointed later.
- It does **not** invent findings, page numbers, or references — an unpinnable finding is dropped or marked `[unknown]`, and an unchecked citation stays `UNVERIFIED` rather than being upgraded.
- It does **not** query the paperclip full-text corpus on any default path — `ResearchClient` (and therefore `search_papers` and `run_lit_arc`, which both route through it) never builds or injects a `paperclip_client`, so although `unified_search` / `acquire_pdf` accept one, paperclip stays dormant until a caller wires it explicitly.

## Files

- `__init__.py` — the barrel + `ResearchClient` (the search/retrieve/verify facade) and the `search_papers` / `get_paper` / `download_pdf` convenience functions.
- `search.py` — `unified_search`: fan out across sources, dedup by DOI, with a per-source `SearchTrace`.
- `query_expansion.py` — rephrase a topic into methods/review/applications/recency variants.
- `sources/` — one client per API (`ncbi`, `semantic`, `crossref`, `biorxiv`, `springer`, `elsevier` (the Elsevier/Scopus cluster), `openalex`, `paperclip`). `ResearchClient` wires the first five plus `elsevier`; `openalex` and `paperclip` are present as clients but not injected by the default client (paperclip is the dormant source noted above).
- `acquisition.py` — the most-open-first PDF download waterfall. `download.py` — single-PDF download + KB save. `_polite_pool.py` — polite-pool User-Agent / email resolution.
- `corpus.py` — `Corpus` assembly. `citation_graph.py` — graph builder. `graph_metrics.py` — `og_score` / forward-influence / co-citation / year buckets. `citation_lookup.py` — low-level refs/citations fetchers.
- `picker.py` — content-aware deep-read selection. `binning.py` — LLM HISTORY/DEVELOPMENT/SOTA bucketing. `scoring.py`, `rubric.py`, `recency_quota.py`, `policy_skip.py`, `next_topic.py` — ranking/quota/skip helpers.
- `summarize.py` — per-paper summary cards. `pdf.py` — text extraction. `figures.py` — figure/caption extraction. `read_paper.py`, `full_reader.py` (+ `full_reader.md`) — the bilingual, figure-aware `paper.md` reader.
- `lineage.py` — `run_lit_arc`. `report.py` — `run_lit_report`. `litarc_html.py` — HTML render of an arc. `arc_structure.py` — arc section scaffolding.
- `papers_index.py` — the corpus ledger. `session.py` — multi-round research session state. `verification.py` / `claim_verification.py` — paper-existence + claim-match types.
- `config.py` — API-key discovery. `retry.py` — retry/backoff. `data_utils.py` — data-format sniffing.
- `full_reader.md` — the only sibling doc; spec for the bilingual full-paper reader.

## See also

- `../citations/` — NotebookLM-style citation verification that consumes the papers this package fetches.
- `../kb/` — the knowledge base layer (`kb.paths` provides every canonical write path used here).
- `../workflows/` — crosstalk / deep-think orchestrators that reason over the corpus.
- `../slides/`, `../figures/` — deck and figure builders downstream of the arc.
- `.claude/commands/lit-arc.md`, `lit-report.md`, `lit-search.md`, `full-reader.md` — the slash-command bodies that drive the Claude-Code-callable paths.
- `docs/methodology.md` — canonical reference for `og_score`, co-citation, year-bucketing (Kessler 1963 / Small 1973).
