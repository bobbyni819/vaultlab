---
name: cite
description: PDF-grounded citation audit — inventory have-PDF vs no-PDF, ground claims against actual PDF page images with an identity check, harvest a clickable link list for missing PDFs, mark no-PDF citations UNVERIFIED. Zero hallucination.
arguments: [audit|verify|status] <draft.md>
---

# /cite [audit|verify|status] <draft.md>

> Runs Bobby's PDF-grounded, zero-hallucination citation workflow. Canonical rules:
> [`docs/writing-and-citation-practices.md`](../../docs/writing-and-citation-practices.md) sections C and D.

This command dispatches to the existing `verify-citations` skill engine for the per-claim matching loop.
It does NOT fork a parallel verifier. The related `/cite-show` and `/cite-find` views are referenced, not
absorbed here.

Subcommands:
- **`audit`** (default) — run the full three-step loop over every citation in the draft.
- **`verify`** — re-run only the citations currently marked UNVERIFIED or NEEDS_REVIEW.
- **`status`** — print the ledger summary (counts by verification status) without re-reading PDFs.

## The hard rule

Never verify a claim from memory, from an abstract alone, or from a search snippet. If there is no local
PDF, the citation is UNVERIFIED. A citation is "verified" only after its PDF page images have been read in
STEP 2.

## STEP 1 — INVENTORY

For every reference in the draft, check whether a local PDF exists (in `Sources/Papers/` or the papers
database). Split the reference list into have-PDF and no-PDF.

```python
from vaultlab.citations.grounding import inventory_pdfs   # Tier-2; until it lands, glob manually
# Tier-1 today: glob Sources/Papers/*.pdf and match against the draft's reference list.
```

## STEP 2 — GROUND (have-PDF citations)

For each have-PDF citation:

1. **Identity check (HARD, non-skippable, runs FIRST).** Open the PDF page images and confirm the title,
   authors, journal, and DOI match the cited paper. On a mismatch, move the file to
   `Sources/Papers/_wrong_pdfs/`, mark the citation UNVERIFIED, and do not verify any claim from it. This
   catches a wrong PDF filed under the right name.
2. **Read page images, not text extraction.** Use the multimodal `Read` tool on the PDF path
   (`Read(file_path=<pdf_path>)`), the same path `/lit-arc` Step 3 uses. Text extraction drops figures,
   tables, and superscripts.
3. **Verify every claim, number, and attribution** that cites this paper against the real text. Quote
   high-stakes numbers verbatim with their location (table, figure, or page).
4. **Record** one line per citation in `Output/<project>/VERIFICATION_LEDGER.md` plus, for high-stakes
   papers, a per-paper note in `Sources/Papers/<Author><Year>.md`.

## STEP 3 — HARVEST (no-PDF citations)

1. Mark every no-PDF citation UNVERIFIED in the ledger.
2. Emit a flat, clickable link list directly in the chat: one DOI / publisher / PubMed URL per line,
   grouped by publisher so they are easy to scan. The `vaultlab fetch-list paywalled <acquisition-log.json>`
   CLI subcommand produces this clustered list.
3. Bobby left-clicks each link to open browser tabs, bulk-downloads in one pass, files the PDFs into
   `Sources/Papers/`, and re-runs STEP 2 on them. The acquisition cache short-circuits already-present PDFs.

## Preflight (process discipline, section F)

- Confirm the canonical draft version before editing (check `START_HERE.md` and the latest draft on disk).
- Do not clobber a figure-bearing `.docx`.

## Pre-ship gate (section G)

Before declaring the draft's citations final, every citation must be either VERIFIED (PDF read in STEP 2,
identity confirmed) or explicitly UNVERIFIED in the ledger. No citation may be asserted correct without a
read PDF. Echo the section-G checklist items that touch citations.
