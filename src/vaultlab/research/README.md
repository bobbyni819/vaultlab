# vaultlab.research

The literature engine: search many databases at once, build a citation graph from the hits, pull the PDFs it can legally get for free, read them into page-cited summary cards, and assemble the whole thing into a lineage arc or a deep-research review.

Plain-language companion: see the **Paper fetching / The influence map / Paper understanding / Paper indexing** sections of `vaultlab-subsystems.md` in the KB (`Wiki/Concepts/`). Architectural sketch: `docs/architecture.md` → "vaultlab.research".

## What it is

When a researcher asks Claude Code for a literature review, this is the package that does the actual work. It fans a topic out to PubMed, Semantic Scholar, CrossRef, bioRxiv, Springer, and the Elsevier/Scopus cluster, merges the duplicate hits by DOI, then expands outward into a who-cites-whom graph so a foundational paper can be told apart from one that is merely loud. It downloads the open-access PDFs along a most-permissive-license-first waterfall, hands each budgeted PDF to Claude to read into a one-page summary card where **every finding carries a `[pN]` page marker**, and writes all of it into the project's knowledge base as Obsidian markdown.

The `paperclip` 8M-paper full-text corpus is a **wired-but-dormant seventh source**: `unified_search` and the `acquire_pdf` waterfall both accept an optional `paperclip_client` (and `PaperclipClient` is a working CLI wrapper in `sources/paperclip.py`), but no orchestrator or `ResearchClient` currently constructs and injects that client — so on every default code path the paperclip branch stays off. Treat it as plumbing that exists but is not yet switched on, not as a live source.

It exists because literature search is the most-requested vaultlab capability and the easiest one to get quietly wrong — a hallucinated citation, a "foundational" ranking that just reflects citation-count noise, a summary finding floating free of any page. The package is built so that the orchestrators (`run_lit_arc`, `run_lit_report`) and the `/lit-arc`, `/lit-report`, `/full-reader`, `/lit-arc-next`, `/papers-index`, and `/dig-deeper` slash commands all share one disciplined, idempotent pipeline (`/lit-search` is a catalog entry over the same `unified_search` engine). A distinctive design point: most LLM steps expose a **no-SDK "Claude-Code-callable" path** (a `prepare_*` / `render_*_from_response` pair) so the active Claude Code session is the model — no Anthropic API key required.

## Public surface

Search + retrieval client:

- `ResearchClient` — unified client over all configured literature APIs. `.search()` / `.search_with_trace()` (the latter returns a per-source `SearchTrace`), `.get_paper()`, `.get_citations()` (depth-limited), `.get_references()`, `.get_recommendations()` (seed-paper "more like this"), `.verify_exists()` (existence + a confidence score), `.match_claim()` / `.fetch_evidence()` (LLM claim-matching against abstract or full text), `.save_to_kb()`, `.find_full_text_in_kb()`, `.download_pdf()`.
- `search_papers` — module-level convenience: spin up a client and search (optionally downloading PDFs) in one call.
- `get_paper` — fetch full metadata for one DOI or PMID.
- `download_pdf` — download a paper's PDF to a directory (returns path or empty string).
- `Paper` — the canonical paper-metadata record passed between every stage (title / authors / year / journal / DOI / PMID / abstract / URLs / citation count / source); merges duplicate records field-by-field.

Search ranking + query handling (under the client):

- `unified_search` (in `search.py`) — fans the query across every configured source **concurrently** (one worker thread per source, with a global wall-clock backstop so one hung API can't stall the run), dedups by DOI (PubMed metadata preferred when records collide), and sorts by a **recency-blended score** rather than raw citation count. `SearchTrace` / `SourceTrace` capture per-source hit counts, errors, and wall-time for the audit sidecar.
- `blended_paper_score` / `DEFAULT_RECENCY_WEIGHT` (in `scoring.py`) — the ranking formula: a log-squashed blend of citations-per-year and absolute citations (default 60 % weight on velocity), so a fresh high-velocity paper isn't buried under an old, heavily-cited one. Pass `recency_weight=0.0` to recover the legacy citation-count order.
- `expand_query` (in `query_expansion.py`) — turn one topic into several framings (review / methods / applications / recent / benchmark) — LLM-driven when a callback is wired, deterministic-string-template otherwise — and run every variant against every source before the dedup. This is the "smart query expansion" the `/lit-search` catalog entry advertises.

PDF acquisition (the waterfall):

- `acquire_pdf` — try (optional paperclip Tier-0) → Unpaywall → PMC/EuropePMC → bioRxiv/medRxiv → Springer → Elsevier for one DOI, with `%PDF-` magic + Content-Type validation, polite-pool rate limiting, and a cached short-circuit. Captures a best-effort licence string per tier.
- `acquire_pdfs_for_corpus` — run the waterfall across a whole corpus in parallel, with an `aggressive_retry` pass for `depth="complete"` runs.
- `AcquisitionResult` — per-paper outcome: which tier succeeded (or why each failed, per-tier), a classified `outcome` taxonomy (`oa_pdf` / `gated_pdf_via_key` / `gated_metadata_only` / `failed_paywalled` / `failed_not_indexed` / `cache_hit` / `paperclip_full_text`), wall-time, and — on paywalled failure — a publisher URL + the cache path where a manually-fetched PDF should be dropped.
- `render_manual_fetch_instructions` — turn a corpus's failed acquisitions into a copy-paste markdown shopping list (publisher links + drop-paths) for papers behind an institutional proxy; the next run picks them up from cache automatically. Surfaced on the CLI as `vaultlab fetch-list paywalled <log.json>`.

Citation graph + metrics:

- `Corpus` — a topic-scoped collection of papers plus their backward (`references`) and forward (`cited_by`) citation edges; the unit of analysis.
- `build_corpus_from_seeds` — grow a corpus by walking CrossRef references one hop out from seed papers.
- `expand_corpus` — extend an existing corpus with more backward hops. A sibling `expand_corpus_forward` (**in `corpus.py`** — not re-exported from the barrel; import as `from vaultlab.research.corpus import expand_corpus_forward`) walks Semantic Scholar's *citing* papers so the corpus also catches work newer than the seeds (the SOTA blind spot a backward-only graph misses); `run_lit_arc` calls it by default (`forward_expansion=True`).
- `CitationGraph` — directed citation-network builder (depth-limited forward+backward traversal, seminal-paper detection, Mermaid export). Backs the `/dig-deeper <doi>` command.
- `compute_metrics` — produce `og_score` (Kessler-1963 bibliographic coupling), `forward_influence`, co-citation pairs (Small 1973), and year buckets over a corpus.
- `CorpusMetrics` — the computed-metrics record.
- `CandidatePaper`, `PickerTask`, `PickerCallback`, `pick_top_n_content_aware`, `prepare_picker_task`, `render_picks_from_response`, `picker_response_schema` — the **content-aware picker**: read abstracts to choose the deep-read set rather than trusting citation rank alone. With `picker_mode="adversarial"` the pick becomes a bounded multi-agent crosstalk meeting instead of a single call.
- `apply_recency_quotas` (in `recency_quota.py`) — a floor on how many recent-window papers must survive into the final picks, so fast-moving SOTA work isn't squeezed out by the citation-graph's structural bias toward older papers.
- `BinningTask`, `BinningCandidate`, `BinningCallback`, `BinningResult`, `assign_buckets_with_llm`, `prepare_binning_task`, `render_binning_from_response`, `binning_response_schema` — LLM-driven conceptual bucketing (read each abstract, decide where it belongs in the arc) that overrides the deterministic year quartiles — fixing the "empty HISTORY bucket on a recent corpus" failure.
- `arc_structure` (`SHORT` / `STANDARD` / `REVIEW_PAPER` templates, `make_custom_structure`, `resolve_structure`) — makes the arc shape a first-class object: 3 sections for a journal-club intro, up to ~10 for a full review-paper scope. The bucketer and narrator both read the chosen structure.

Citation lookups (low-level):

- `get_references_via_crossref`, `get_citations_via_s2`, `get_influential_count_via_s2` — backward refs / forward citations / influential-citation count.
- `Reference` — a single citation edge. `RateLimitError` — raised when an API throttles.

Summarization + reading:

- `PaperSummary`, `summarize_paper`, `summarize_corpus`, `prepare_summary_task`, `render_summary_from_response`, `summary_response_schema`, `SummarizationTask`, `SummaryReader`, `SummarizeAuthError`, `write_summary_to_kb` — turn a PDF into a page-cited `Wiki/Summaries/<doi>.md` card (Tier-A full read or Tier-C stub). Every key finding must carry a `[pN]` page marker; unground-able findings are dropped or `[unknown]`-flagged.
- `build_paper_reader` (in `full_reader.py`, also `/full-reader`) — instead of a short summary, produce a **complete bilingual `paper.md`**: full prose preserved, each paragraph paired with a same-language translation (default zh-CN), figures/tables inlined near the text that introduces them, and stable anchor IDs (`S###`/`C###`/`F###`/`T###`) on every block for source-grounded citation. Writes provenance receipts.
- `verify_paragraph_claims` (in `claim_verification.py`) — re-read each narrator-written arc paragraph against the cited papers' summaries and label every claim `supported` / `partial` / `unsupported` / `unverifiable`, catching overclaims the narrator propagated past the `[pN]` anchors. Wired into `run_lit_arc` as an opt-in Phase 7b.
- `is_policy_refusal_error`, `mark_skipped`, `list_skipped`, `fetch_list_paywalled` (in `policy_skip.py`) — when an LLM usage-policy filter false-positives on a legitimate biomedical batch, flag the paper `tier: skipped_policy` and keep going rather than sinking the run; the user reviews the list later (CLI: `vaultlab list-policy-skipped`).
- `extract_text`, `extract_and_save`, `batch_extract` — raw text extraction from PDFs. `read_paper_text` / `read_paper_sections` (`read_paper.py`) dispatch reading by acquisition source (paperclip sections when available, else PDF text).
- `extract_figures`, `write_figure_notes` — pull embedded figures + captions out of a PDF (extraction, not figure *generation*).
- `detect_data_format` — sniff what kind of data file an input is (CSV / Parquet / H5AD / XLSX / JSON / HDF5) for the analysis pipeline's load step.

Orchestrators (end-to-end):

- `run_lit_arc` — the full `/lit-arc` pipeline: query-expand → search (+ trace) → article stubs → corpus + metrics → (optional LLM bucketing) → PDF acquisition → (optional figure acquisition) → Tier-A pick → per-paper summaries → lineage arc → (optional claim verification) → provenance → project view. A `depth` knob (`fast` / `balanced` / `thorough` / `complete`) dials the Tier-A read budget against the count of PDFs actually acquired; `picker_mode` / `arc_mode` can swap the single-call picker/narrator for bounded adversarial crosstalk meetings. Same-day re-runs are collision-protected (`-rerun-N`) and idempotent re-runs leave files untouched.
- `ArcTask`, `ArcNarrator`, `DepthLevel`, `LineageRunResult`, `prepare_arc_task`, `render_arc_from_response`, `arc_response_schema` — the lit-arc task/result types and its Claude-Code-callable path. `LineageRunResult` also carries the live `Corpus` and any `figure_assignments` so a downstream deck builder reads them directly.
- `run_lit_report` — the `/lit-report` deep-research review (3000–5000 words). Reuses lit-arc's search→summaries front half, then drafts five sections (background / methods landscape / findings / contradictions / future directions), each via a section-specific **adversarial crosstalk** meeting (no opt-out — this is the deep-research differentiator), threading prior sections in for cohesion, then runs a rigor audit and inlines its fix-list.
- `ReportTask`, `ReportRunResult`, `Section`, `SECTION_ORDER`, `SECTION_ROLES`, `SECTION_WORD_TARGETS`, `build_section_prompt`, `prepare_report_task`, `render_section_from_response`, `section_response_schema` — the report's section schema and callable path.
- `propose_next_topics` (in `next_topic.py`, also `/lit-arc-next`) — read the project's decisions log + existing arcs + papers manifest and rank 3–5 candidate next topics with KB-grounded rationale, so the system can suggest what to research next instead of waiting for a topic.
- `aggregate_rubric_scores` / `RubricEnsembleScore` (in `rubric.py`) — when an ensemble of critics scores an artifact, aggregate as mean ± spread (not int-mean) so a lone dissenter's fatal-flaw signal isn't averaged away.

Corpus ledger + session state:

- `PapersIndex`, `PaperEntry`, `scan_corpus`, `build_and_save`, `load_index`, `save_index`, `needs_fetch`, `needs_summary`, `summary_is_current` — the **papers ledger**: one row per paper (PDF JOINed to summary on DOI-slug), rebuilt from disk so multi-run fetch/read stays idempotent.
- `ResearchSession`, `Finding`, `FindingStatus` — programmatic state for multi-round reasoning runs (rounds, findings, their status through review).

Verification types (`TYPE_CHECKING`-only re-exports, materialized lazily inside `ResearchClient`): `VerificationResult`, `ClaimMatch`, `EvidenceRecord`.

## How it fits

**Reads from:** the configured API-key file (`research_apis.json`), the live literature APIs, and the project KB — existing PDFs in `Sources/Papers/`, summary cards in `Wiki/Summaries/`, and per-paper stubs in `Sources/Articles/`. The ledger and the acquisition cache make re-runs delta-only, so a session never re-downloads or re-reads what is already on disk.

**Writes to:** the project KB. A `run_lit_arc` pass lands a search log in `Sources/Notes/`, article stubs in `Sources/Articles/`, PDFs in `Sources/Papers/`, summary cards in `Wiki/Summaries/`, the lineage arc in `Wiki/Concepts/`, and provenance receipts (`.provenance.json` + `.method.md`) next to each artifact.

**Consumed by:** `vaultlab.workflows` (crosstalk reads the corpus + summaries), `vaultlab.citations` (claim verification reads the fetched papers), `vaultlab.slides` and `vaultlab.figures` (decks/figures built from the arc), the slash commands `/lit-arc`, `/lit-report`, `/lit-search`, `/full-reader`, `/lit-arc-next`, `/papers-index`, and `/dig-deeper` (which drive the Claude-Code-callable paths directly), and the CLI subcommands `vaultlab fetch-list paywalled` and `vaultlab list-policy-skipped`. It sits at the front of the pipeline: nearly everything downstream depends on the corpus this package assembles.

## What it does NOT do

- It does **not** rank by topic/content match during search — ranking is citations-plus-recency; relevance is judged later, from abstracts, by the content-aware picker.
- It does **not** break paywalls or log into an institution — gated papers it can't get legally become a manual link list, and `verify_exists` confirms existence, not access.
- It does **not** build a searchable index of full PDF text — only the summary *cards* are searchable; a sentence buried in a PDF that never reached a card cannot be pinpointed later.
- It does **not** invent findings, page numbers, or references — an unpinnable finding is dropped or marked `[unknown]`, and an unchecked citation stays `UNVERIFIED` rather than being upgraded.
- It does **not** query the paperclip full-text corpus on any default path — `ResearchClient` (and therefore `search_papers` and `run_lit_arc`, which both route through it) never builds or injects a `paperclip_client`, so although `unified_search` / `acquire_pdf` accept one, paperclip stays dormant until a caller wires it explicitly.

## Files

- `__init__.py` — the barrel + `ResearchClient` (the search/retrieve/verify/claim-match facade) and the `search_papers` / `get_paper` / `download_pdf` convenience functions.
- `search.py` — `unified_search`: concurrent fan-out across sources, dedup by DOI, recency-blended sort, per-source `SearchTrace`.
- `query_expansion.py` — rephrase a topic into methods/review/applications/recency/benchmark variants. `scoring.py` — the recency-blended `blended_paper_score`. `recency_quota.py` — floor on recent papers in the picks.
- `sources/` — one client per API as a separate file (`ncbi`, `semantic`, `crossref`, `biorxiv`, `springer`, `elsevier` (the Elsevier/Scopus cluster), `openalex`, `paperclip`); `sources/__init__.py` itself is an empty placeholder, so clients are imported by path. `ResearchClient` wires the first five plus `elsevier`; `openalex` and `paperclip` are present as clients but not injected by the default client (paperclip is the dormant source noted above).
- `acquisition.py` — the most-open-first PDF download waterfall + manual-fetch instructions. `download.py` — single-PDF download + KB save. `_polite_pool.py` — polite-pool User-Agent / email resolution. `retry.py` — retry/backoff.
- `corpus.py` — `Corpus` assembly + backward/forward expansion. `citation_graph.py` — directed graph builder (Mermaid/seminal-paper). `graph_metrics.py` — `og_score` / forward-influence / co-citation / year buckets. `citation_lookup.py` — low-level refs/citations fetchers (CrossRef refs, S2 citations + influential-citation count).
- `picker.py` — content-aware deep-read selection. `binning.py` — LLM conceptual HISTORY/DEVELOPMENT/SOTA bucketing. `arc_structure.py` — variable-length arc templates (SHORT/STANDARD/REVIEW_PAPER + custom). `rubric.py` — ensemble-critic mean-±-spread scoring. `policy_skip.py` — usage-policy-refusal skip + paywalled fetch-list (backs two CLI subcommands). `next_topic.py` — propose-next-topic from KB state.
- `summarize.py` — per-paper summary cards. `pdf.py` — text extraction. `figures.py` — PyMuPDF figure/caption extraction. `read_paper.py` — source-dispatched section reader. `full_reader.py` (+ `full_reader.md`) — the bilingual, figure-aware `paper.md` reader. `data_utils.py` — data-format sniffing.
- `lineage.py` — `run_lit_arc`. `report.py` — `run_lit_report`. `litarc_html.py` — HTML render of an arc. `claim_verification.py` — per-claim verdict pass over arc paragraphs.
- `papers_index.py` — the corpus ledger (rebuilt from disk: PDF JOINed to summary on DOI-slug; `read_depth` + `verification` per row). `session.py` — multi-round research session state (`ResearchSession` / `Finding` / `FindingStatus` / chain-of-reasoning links). `verification.py` — paper-existence + claim-match types.
- `config.py` — API-key discovery.
- `full_reader.md` — the only sibling doc; spec for the bilingual full-paper reader.

## See also

- `../citations/` — NotebookLM-style citation verification that consumes the papers this package fetches.
- `../kb/` — the knowledge base layer (`kb.paths` provides every canonical write path used here).
- `../workflows/` — crosstalk / deep-think orchestrators that reason over the corpus.
- `../slides/`, `../figures/` — deck and figure builders downstream of the arc.
- `.claude/commands/lit-arc.md`, `lit-report.md`, `full-reader.md`, `lit-arc-next.md`, `papers-index.md`, `dig-deeper.md` — the slash-command bodies that drive the Claude-Code-callable paths. (`/lit-search` is a catalog/skill entry in `COMMANDS.md`, not a standalone command file — it maps onto `unified_search` + `expand_query`.)
- `vaultlab.cli` — the `vaultlab fetch-list paywalled` and `vaultlab list-policy-skipped` subcommands route into `policy_skip`.
- `docs/methodology.md` — canonical reference for `og_score`, co-citation, year-bucketing (Kessler 1963 / Small 1973).
