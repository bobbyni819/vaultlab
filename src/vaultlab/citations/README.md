# vaultlab.citations

Checks every cited claim in a markdown draft against the actual paper it points to, and refuses to bless any citation it cannot read for itself.

Plain-language subsystem write-up: the "Citation verification" entry in `G:/My Drive/Knowledge/vaultlab/Wiki/Concepts/vaultlab-subsystems.md`. Architectural placement: `docs/architecture.md` (the `vaultlab.citations` node, fed by `vaultlab.workflows`).

## What it is

When a scientist (or the LLM drafting on their behalf) writes "(Smith et al., 2021)" next to a claim, two things can be wrong: the paper might not exist, or it might exist but not actually say what the sentence claims. `vaultlab.citations` exists to catch both. It scans a markdown document for every citation it can recognize — author-year (parenthetical `(Smith et al., 2021)`, inline `Smith et al. (2021)`, no-comma `(Smith 2021)`, and grouped `(Smith 2020; Jones 2019)` forms, including lowercase-prefix surnames like `von Elm` / `de Jong`), DOIs (inline `DOI:` or `doi.org` URLs), and PMIDs — pulls the surrounding sentence as the *claim* being made, confirms the paper is real (via the research client's APIs), and where it can find text (an abstract, or full text already in the KB) it checks whether that text actually supports the claim. The result is an `AuditReport`: every citation tagged with a verification status, a risk level, hallucination flags, an evidence passage, and a list of recommended action items.

The discipline here is honest reporting. A paper that was found but whose claim was never checked against real text is marked `UNVERIFIED`, never optimistically "confirmed" — an unread-paper citation must not masquerade as verified in a manuscript, and such a citation is held at `MEDIUM` risk (never `LOW`) so the reading backlog stays visible. This package backs the `/cite` audit skill and the cite-watch citation watchdog, and is invoked by writing workflows before a draft ships.

## Public surface

- `audit_file` — audit one markdown file: extract its citations, verify each, return an `AuditReport`.
- `audit_directory` — audit every markdown file under a directory (glob-matched), deduplicating citations across files.
- `verify_citation` — verify a single `Citation`: check the evidence cache, locate the paper (by DOI/PMID, else by an author + year + claim-keyword search), match its claim against text, and set status / risk / flags. When only an author-year citation is given, the best search hit is chosen by keyword overlap between the claim and each candidate's title + abstract, with a strong bonus for matching the cited year.
- `extract_citations` — read a markdown file and return the `Citation` objects it contains, with correct line numbers (frontmatter offsets are accounted for).
- `extract_citations_from_text` — same extraction, but from an in-memory string (strips YAML frontmatter and fenced/inline code blocks so code samples don't produce false citations).
- `generate_report` — render an `AuditReport` to a markdown report (summary table, hallucination-flag list, per-citation evidence chunks with quoted passages and reasoning, and a checklist of action items), optionally writing it to disk with provenance receipts.
- `EvidenceIndex` — a JSON-backed cache mapping DOI/PMID → previously verified claims, so the same claim is never re-checked against the same paper twice. Also queryable: `list_all()` lists every cached paper with its claim count and latest-verified date, and `stats()` returns total-papers / total-claims counts.
- `Citation` — one extracted citation: raw text, authors, year, the claim, source file + line, identifiers (DOI/PMID/title/journal), status, risk, an `EvidenceRecord`, and hallucination flags; `to_dict()` serializes it.
- `AuditReport` — the audit summary: total count, status histogram (`by_status`), high-risk-unverified count, deduplicated hallucination flags, action items, source-file list, and the full citation list; `to_dict()` serializes the whole report.
- `VerificationStatus` — the status enum (`VERIFIED_FULLTEXT`, `VERIFIED_ABSTRACT`, `API_CONFIRMED`, `UNVERIFIED`, `SUSPECT`, `CONTRADICTED`).
- `RiskLevel` — the risk enum (`LOW`, `MEDIUM`, `HIGH`) derived from status + hallucination flags.

One more verifier helper is public but not re-exported from the package barrel:

- `verifier.check_hallucination_risks` — the heuristic flagger run on every citation. It raises `FUTURE_DATE` (year past the current year), `CURRENT_YEAR` (this-year paper, hard to verify), and `UNVERIFIED_QUANTITATIVE` (a numeric claim — `%`, `p<…`, `n=…`, a decimal — carrying no DOI/PMID). The verifier adds `PAPER_NOT_FOUND` when existence lookup fails. Any flag forces the citation to `HIGH` risk.

**Status / risk decision (how a citation lands where it does):** existence + claim-match together decide the status. Paper not found → `SUSPECT` (+ `PAPER_NOT_FOUND`, `HIGH` risk). Found, claim matched against KB full text and supported → `VERIFIED_FULLTEXT`; supported against abstract only → `VERIFIED_ABSTRACT`; a `partial` match → `VERIFIED_ABSTRACT`; `unsupported` → `CONTRADICTED` (`HIGH`); a match that runs but is `unrelated`/`unverifiable`, or a paper found with no text at all to check → `UNVERIFIED` (`MEDIUM` whenever a claim was attached). A paper confirmed to exist with *no* claim attached → `API_CONFIRMED` (`LOW`). The audit then emits an action item per `SUSPECT` ("Verify …") and per `CONTRADICTED` ("CHECK … claim may not be supported") citation.

Two more public helpers live in sibling modules but are not re-exported from the package barrel:

- `export.write_export` (plus `to_enw` / `to_ris` / `to_zotero_rdf`) — serialize citations to EndNote ENW, RIS, or Zotero RDF for import into a reference manager; the target format is inferred from the output extension (`.enw` / `.ris` / `.rdf` / `.xml`) unless passed explicitly. The author string is split into individual names, and missing fields are emitted blank, never fabricated.
- `report_html.build_citation_audit_html` — render an `AuditReport` (or its `to_dict` output) to a single-file, filterable HTML string (TL;DR box, status/risk chips, per-citation cards, copy-DOI / copy-citation buttons, status-and-risk filter bar, action-items table, and a hallucination-flag-pattern table); `report_html.write_citation_audit_html` writes that HTML to disk. This is the citation-audit consumer of `vaultlab.report`.

## How it fits

**Reads from:** the markdown documents you point it at (drafts, methods sections, lit notes); a `research_client` (a `bobby_research.ResearchClient`) for paper existence checks, search, abstract retrieval, and claim matching; and, when given a `kb_dir`, the project KB — both for full-text lookups (`Sources/Articles/`) and for the on-disk evidence cache (`Sources/.evidence_index.json`).

**Writes to:** an `AuditReport` returned in-process; a markdown report on disk when you call `generate_report` (with provenance receipts written alongside via `vaultlab.provenance.write_receipts`); a single-file HTML report when you call `report_html.write_citation_audit_html`; the `EvidenceIndex` JSON cache (atomic write to `Sources/.evidence_index.json`); and, when a `kb_dir` is supplied and claim-matching produced evidence, a "Verified Claims" section appended to the matching article note in `Sources/Articles/` (matched by DOI or title substring; silently skipped if no article note matches).

**Deduplicates as it goes:** within an `audit_file` / `audit_directory` run, a citation is keyed by DOI, else PMID, else `(authors, year)`. The first occurrence of a key is verified against the APIs; every later occurrence copies that status / risk / evidence / flags instead of re-hitting the network — so a paper cited twenty times is verified once.

**Where it sits:** late in the pipeline — after literature has been gathered and a draft written. `vaultlab.workflows` (notably the research-write phase and the cite-watch guard) calls in here before a manuscript or report is considered shippable. The status enum's honesty (`UNVERIFIED` over `API_CONFIRMED`) is the gate that keeps unread-paper citations from passing as checked.

## What it does NOT do

- It does not fetch or download papers, nor run the LLM claim-match itself — paper lookup, search, abstract/full-text retrieval, and the support/contradict judgement are all delegated to the `research_client` (a `bobby_research.ResearchClient`). Without a `research_client` passed in, `audit_file` only *extracts* citations; it cannot verify them.
- It does not invent metadata. A paper it cannot find is flagged `SUSPECT` with `PAPER_NOT_FOUND`; missing export fields are left blank rather than guessed.
- It does not page-image-ground citations to a specific PDF page — claim matching works from abstracts or KB full text, not rendered page images (that grounding is planned; see `NEXT_STEPS.md`).
- It does not edit your draft or auto-correct citations. It reports status, risk, and action items; deciding what to fix stays with the author.

## Files

- `__init__.py` — package barrel; the eleven re-exported public symbols (`audit_file`, `audit_directory`, `verify_citation`, `extract_citations`, `extract_citations_from_text`, `generate_report`, `EvidenceIndex`, `Citation`, `AuditReport`, `VerificationStatus`, `RiskLevel`).
- `models.py` — `Citation`, `AuditReport`, `VerificationStatus`, `RiskLevel` dataclasses/enums.
- `extractor.py` — recognizes author-year / DOI / PMID citations in markdown, strips frontmatter + code blocks, captures claim context.
- `verifier.py` — the per-citation orchestrator: cache check → find paper (DOI/PMID lookup, else keyword-scored search via `_best_match`) → hallucination flags → claim match → status + risk → optional KB write-back; also the public `check_hallucination_risks` (future-date, current-year, uncited quantitative claim).
- `auditor.py` — batch pipeline over a file or directory, with verify-once DOI/PMID/author-year deduplication and the `SUSPECT`/`CONTRADICTED` → action-item assembly in `_build_report`.
- `evidence.py` — `EvidenceIndex`, the atomic-write JSON cache of verified claims, with `lookup` / `store` / `list_all` / `stats`.
- `reporter.py` — markdown report rendering + provenance receipts.
- `report_html.py` — single-file filterable HTML report rendering.
- `export.py` — ENW / RIS / Zotero-RDF reference-manager exporters.

(No sibling `.md` docs in this package yet; this README is the package-level write-up.)

## See also

- `../research/verification.py` — defines the `EvidenceRecord` / `VerificationResult` / claim-match types this package consumes from the `ResearchClient`.
- `../provenance/` — `ProvenanceRecord` / `write_receipts`, the audit-manifest contract `generate_report` honors.
- `../report/` — the HTML report grammar (`vaultlab.report.render_report` + `components`) that `report_html.py`'s `build_citation_audit_html` builds on.
- `.claude/commands/cite-watch.md` — the inline citation watchdog for the research-write phase (the `/cite` audit skill drives this package end to end).
- `docs/architecture.md` — the `vaultlab.citations` node and its three-tier integrity sketch.
