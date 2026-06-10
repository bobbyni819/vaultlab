# Papers spine — build plan & spec decisions (2026-06-10)

> Companion to `NEXT_STEPS.md`. This doc records the design decisions Bobby made on
> 2026-06-10 after a full-pipeline deep dive, and the build sequence that follows from them.
> It is the agreed spec for the **paper fetch → index → read → verify → cite** spine — the
> part of vaultlab Bobby wants to use for real research now.

## Why this exists

A nine-subsystem deep dive (2026-06-10) found the lower-level primitives mostly real and
well-tested, but the reading spine's **keystone missing**: the persistent "papers index"
Bobby believed was built lives only on `feat/writing-citation-practices` (commit `dd45b13`)
and, even there, scans `Sources/Papers/*.md` *notes* the fetch pipeline never writes — so on
a real corpus it indexes zero rows. Several adjacent links were also unreconciled (summary
re-reads on every run, a citation trust hole, a dead `/cite` front door, docs that call
shipped code "planned").

## The end-to-end pipeline, honestly (deep-dive map)

| Stage | State | Note |
|---|---|---|
| **Fetch** | solid | 7-source search + dedup; most-open-first PDF waterfall; `%PDF-` magic + min-byte validation; cached PDF short-circuits re-download (file-level idempotency already works). |
| **Index** | **missing on main** | the keystone — being built here. |
| **Read / track-depth** | partial | `summarize.py` works and enforces `[pN]` markers, but re-reads every PDF every run (not idempotent); read-depth is a coarse A/C tier in scattered frontmatter, not tracked state. |
| **Verify** | partial / trust hole | citation + claim verification are real, but an unread paper's claim was scored `API_CONFIRMED` instead of `UNVERIFIED`; grounding is text-only (no page images). |
| **Cite / dispatch** | dead front door | `audit_file` backend is real, but no `cite.md` command shipped. |
| **Analyze** | solid | refuses raw data; provenance receipts; verification-only Welch's t. |
| **Draft / figure / memory** | partial / aspirational | template-only methods; recipes don't honor the export contract; `update_start_here` wired into nothing; a `START_HERE` path mismatch. |

## The four decisions (2026-06-10)

1. **Index design → ledger is the source of truth.** One `papers_index.json` per KB, keyed by
   DOI-slug, built by enumerating **PDFs on disk JOINed to summaries** (never the note-glob that
   sinks the branch version). Fetch consults it for idempotency; summarization hash-gates against
   it; `papers.md` becomes a *view* rendered from it. The index is load-bearing state kept
   consistent with disk by always rebuilding from disk.

2. **Citation trust → mark `UNVERIFIED`.** When a cited paper exists in an API but its full text
   was never checked, the citation is flagged `UNVERIFIED` (insufficient evidence), not
   `API_CONFIRMED + low-risk`. Surfacing the reading backlog is a feature, not noise.

3. **Read depth → tiered + idempotent.** Track `none / abstract / full / grounded` per paper.
   Fetch + abstract-tier cheaply; full-read only papers marked relevant; **hash-gate so a paper
   is never re-read once summarized** (re-read only if its PDF changed). Re-runs are delta-only.

4. **`/full-reader` → wire it to the real extractor.** Connect the reader to the existing
   `read_paper_sections` / `pdf.extract_text` path so it works on real papers instead of raising
   `NotImplementedError`; stop advertising a flagship that crashes.

## Build sequence

**Phase 1 — keystone (this branch `feat/papers-index-spine`)**
- `research/papers_index.py` — rewritten, disk-enumerated (PDF ∪ summary), with
  `read_depth` tiers, PDF sha256 (for hash-gating), readability, verification, `last_verified`,
  acquisition outcome; `scan_corpus(kb_root)`, `save_index`, `load_index`, and the idempotency
  query helpers `needs_fetch` / `needs_summary`.
- `kb/paths.py` — `papers_index_path` / `papers_index_md_path` helpers.
- `INSPIRATIONS.md` — lineage entry (commitment #8).
- Tests.

**Phase 2 — idempotent reading**
- Persist `source_pdf_sha256` in `PaperSummary` + frontmatter.
- `summarize_corpus(..., idempotent=True)` skips the LLM read when a summary exists and the PDF
  hash is unchanged. Tiered read-depth recorded.

**Phase 3 — trust fix**
- `verify_citation` assigns `UNVERIFIED` on the unread-paper-with-claim path; `_assign_risk`
  never returns LOW for it.

**Phase 4 — front door & reader**
- Ship `cite.md`; wire `/full-reader` to the real extractor (or honestly mark unbuilt parts).

**Phase 5 — quick-win reconciliation**
- Re-sync `CLAUDE.md` / `docs/architecture.md` (shipped verifiers no longer "planned").
- `START_HERE` path fix + a "fetching into <KB> (project=<slug>)" guard.
- Figure-recipe doc fixes + a render test + the ≥3-anchor assertion.

Each phase ships with tests and an independent diff-scoped reviewer pass before the next.
