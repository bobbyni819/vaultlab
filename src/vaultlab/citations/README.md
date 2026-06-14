# vaultlab.citations

Checks every cited claim in a markdown draft against the actual paper it points to, and refuses to bless any citation it cannot read for itself.

Plain-language subsystem write-up: the "Citation verification" entry in `G:/My Drive/Knowledge/vaultlab/Wiki/Concepts/vaultlab-subsystems.md`. Architectural placement: `docs/architecture.md` (the `vaultlab.citations` node, fed by `vaultlab.workflows`).

## What it is

When a scientist (or the LLM drafting on their behalf) writes "(Smith et al., 2021)" next to a claim, two things can be wrong: the paper might not exist, or it might exist but not actually say what the sentence claims. `vaultlab.citations` exists to catch both. It scans a markdown document for every citation it can recognize — author-year, DOI, PMID — pulls the surrounding sentence as the *claim* being made, confirms the paper is real (via the research client's APIs), and where it can find text (an abstract, or full text already in the KB) it checks whether that text actually supports the claim. The result is an `AuditReport`: every citation tagged with a verification status, a risk level, hallucination flags, and an evidence passage.

The discipline here is honest reporting. A paper that was found but whose claim was never checked against real text is marked `UNVERIFIED`, never optimistically "confirmed" — an unread-paper citation must not masquerade as verified in a manuscript. This package backs the `/cite` slash command and the citation watchdog, and is invoked by writing workflows before a draft ships.

## Public surface

- `audit_file` — audit one markdown file: extract its citations, verify each, return an `AuditReport`.
- `audit_directory` — audit every markdown file under a directory (glob-matched), deduplicating citations across files.
- `verify_citation` — verify a single `Citation`: locate the paper, match its claim against text, set status / risk / flags.
- `extract_citations` — read a markdown file and return the `Citation` objects it contains.
- `extract_citations_from_text` — same extraction, but from an in-memory string (handles frontmatter and code-block stripping).
- `generate_report` — render an `AuditReport` to a markdown report (with per-citation evidence chunks), optionally writing it to disk with provenance receipts.
- `EvidenceIndex` — a JSON-backed cache mapping DOI/PMID → previously verified claims, so the same claim is never re-checked against the same paper twice.
- `Citation` — one extracted citation: raw text, authors, year, the claim, source file + line, identifiers, status, risk, evidence, and flags.
- `AuditReport` — the audit summary: total count, status histogram, high-risk-unverified count, action items, and the full citation list.
- `VerificationStatus` — the status enum (`VERIFIED_FULLTEXT`, `VERIFIED_ABSTRACT`, `API_CONFIRMED`, `UNVERIFIED`, `SUSPECT`, `CONTRADICTED`).
- `RiskLevel` — the risk enum (`LOW`, `MEDIUM`, `HIGH`) derived from status + hallucination flags.

Two more public helpers live in sibling modules but are not re-exported from the package barrel:

- `export.write_export` (plus `to_enw` / `to_ris` / `to_zotero_rdf`) — serialize citations to EndNote ENW, RIS, or Zotero RDF for import into a reference manager; missing fields are emitted blank, never fabricated.
- `report_html.build_citation_audit_html` — render an `AuditReport` (or its `to_dict` output) to a single-file, filterable HTML string (status/risk chips, per-citation cards, action items); `report_html.write_citation_audit_html` writes that HTML to disk. This is the citation-audit consumer of `vaultlab.report`.

## How it fits

**Reads from:** the markdown documents you point it at (drafts, methods sections, lit notes); a `research_client` (a `bobby_research.ResearchClient`) for paper existence checks, search, abstract retrieval, and claim matching; and, when given a `kb_dir`, the project KB — both for full-text lookups (`Sources/Articles/`) and for the on-disk evidence cache (`Sources/.evidence_index.json`).

**Writes to:** an `AuditReport` returned in-process; a markdown report on disk when you call `generate_report` (with provenance receipts written alongside via `vaultlab.provenance.write_receipts`); a single-file HTML report when you call `report_html.write_citation_audit_html`; the `EvidenceIndex` JSON cache; and, when claim-matching succeeds against KB full text, a "Verified Claims" section appended to the matching article note in `Sources/Articles/`.

**Where it sits:** late in the pipeline — after literature has been gathered and a draft written. `vaultlab.workflows` (notably the research-write phase and the cite-watch guard) calls in here before a manuscript or report is considered shippable. The status enum's honesty (`UNVERIFIED` over `API_CONFIRMED`) is the gate that keeps unread-paper citations from passing as checked.

## What it does NOT do

- It does not fetch or download papers — that is `vaultlab.research`'s job. Without a `research_client` passed in, `audit_file` only *extracts* citations; it cannot verify them.
- It does not invent metadata. A paper it cannot find is flagged `SUSPECT` with `PAPER_NOT_FOUND`; missing export fields are left blank rather than guessed.
- It does not page-image-ground citations to a specific PDF page — claim matching works from abstracts or KB full text, not rendered page images (that grounding is planned; see `NEXT_STEPS.md`).
- It does not edit your draft or auto-correct citations. It reports status, risk, and action items; deciding what to fix stays with the author.

## Files

- `__init__.py` — package barrel; the eleven re-exported public symbols (`audit_file`, `audit_directory`, `verify_citation`, `extract_citations`, `extract_citations_from_text`, `generate_report`, `EvidenceIndex`, `Citation`, `AuditReport`, `VerificationStatus`, `RiskLevel`).
- `models.py` — `Citation`, `AuditReport`, `VerificationStatus`, `RiskLevel` dataclasses/enums.
- `extractor.py` — recognizes author-year / DOI / PMID citations in markdown, strips frontmatter + code blocks, captures claim context.
- `verifier.py` — the per-citation orchestrator: cache check → find paper → hallucination flags → claim match → status + risk; also `check_hallucination_risks` (future-date, current-year, uncited quantitative claim).
- `auditor.py` — batch pipeline over a file or directory, with DOI/PMID/author-year deduplication.
- `evidence.py` — `EvidenceIndex`, the atomic-write JSON cache of verified claims.
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
