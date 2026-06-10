---
name: papers-index
description: Build/refresh the KB's papers ledger — the one file an agent reads to understand the whole paper corpus without re-reading it. Scans Sources/Papers/*.pdf JOINed to Wiki/Summaries/*.md and records, per paper, PDF present/readable + content hash, read-depth (none/abstract/full/grounded), and verification status. Surfaces the reading backlog (readable PDFs not yet read) and the re-fetch queue (missing/unreadable PDFs). The ledger is the idempotency authority: fetch skips papers already present+readable, summarization skips papers whose PDF is unchanged.
arguments: "[--no-hash] [--backlog]"
---

# /papers-index

> *"Tell me, in one file, what this KB has fetched, what's readable, what I've
> actually read, and what's left to read — so I never re-download or re-read
> work that's already done."*

Drives `vaultlab.research.papers_index.build_and_save`. Produces two co-located
artifacts in `Wiki/Summaries/`:

- `_papers_index.json` — machine source of truth (one row per DOI-slug).
- `_papers_index.md` — the agent/human-readable status table + reading backlog
  + per-paper digests. **Read this file to understand the corpus**; open a
  per-paper summary only when you need its detail.

The ledger is **enumerated from disk** (PDFs JOINed to summaries on DOI-slug), so
it never drifts — every run reflects exactly what is on disk. It is the
idempotency authority for the whole spine:

- a paper that is `pdf_present && pdf_readable` is **not re-downloaded**;
- a paper whose summary's recorded PDF hash matches the on-disk PDF is **not re-read**;
- a paper that is `pdf_present && !pdf_readable` (a paywall stub / truncated file)
  surfaces in the **re-fetch queue**;
- a readable PDF with no full-text summary surfaces in the **reading backlog**.

## When to use this

- **At session start** — to load the corpus state before deciding what to do
  (Context-preservation Invariant: never zero-shoot).
- **After a fetch / `/lit-arc` run** — `/lit-arc` refreshes the ledger automatically,
  but run this to refresh after a manual drop of PDFs into `Sources/Papers/`.
- **Before reading** — `--backlog` lists the readable-but-unread papers, your work queue.

## Execution

```python
import shlex
from vaultlab.context import resolve_kb_root, KbRootNotConfigured
from vaultlab.research import papers_index as pidx

args = shlex.split("$ARGUMENTS") if "$ARGUMENTS" else []
no_hash = "--no-hash" in args
backlog_only = "--backlog" in args

try:
    kb_root = resolve_kb_root()
except KbRootNotConfigured as exc:
    print(f"No KB configured. Run `vaultlab init` (default: {exc.suggested_default}).")
    raise SystemExit(1)

print(f"Scanning corpus in {kb_root} ...")
index, json_path, md_path = pidx.build_and_save(kb_root, hash_pdfs=not no_hash)
c = index.counts
print(
    f"{c['total']} papers — {c['pdf_present']} with PDF "
    f"({c['pdf_unreadable']} unreadable → re-fetch), {c['no_pdf']} without PDF. "
    f"Read: {c['read_full'] + c['read_grounded']} full ({c['read_grounded']} grounded), "
    f"{c['read_abstract']} abstract-only, {c['read_none']} unread; {c['verified']} verified."
)

backlog = index.reading_backlog()
if backlog:
    print(f"\nReading backlog ({len(backlog)} readable PDFs not yet read full-text):")
    for e in backlog[:25]:
        print(f"  - {e.title or e.slug}  [{e.read_depth}]  {e.pdf_path}")

refetch = index.needs_refetch()
if refetch and not backlog_only:
    print(f"\nRe-fetch queue ({len(refetch)} missing/unreadable PDFs):")
    for e in refetch[:25]:
        state = "unreadable stub" if e.pdf_present else "missing"
        print(f"  - {e.title or e.slug}  ({state})  {e.doi}")

print(f"\nLedger: {md_path}")
print(f"to open: bobby-kb open {md_path.relative_to(kb_root)}")
```

## Per-paper reading protocol (how to use the ledger)

The point of the ledger is that **reading is done once, up front, and never
repeated**. To work a corpus down:

1. Run `/papers-index` (or read the existing `_papers_index.md`).
2. Take the **reading backlog** — readable PDFs at `read_depth` `none`/`abstract`.
3. Deep-read each with `/full-reader <Sources/Papers/<slug>.pdf>` (full bilingual
   read) or via the lit-arc summarizer (Tier-A structured summary). Either writes a
   summary whose frontmatter records the PDF's `source_pdf_sha256`.
4. Re-run `/papers-index` — those papers now show `read_depth: full`, drop out of the
   backlog, and will be **skipped on the next fetch+summarize run** (hash-gated) unless
   their PDF changes.
5. For the **re-fetch queue**, re-acquire the PDF (`/lit-arc --extend` or drop the file
   into `Sources/Papers/`) and re-run.

A later agent should ALWAYS read `_papers_index.md` before re-reading any paper —
it is the corpus map.

## Output

- `Wiki/Summaries/_papers_index.json` — machine ledger (counts + per-paper rows).
- `Wiki/Summaries/_papers_index.md` — status table, reading backlog, per-paper digests.

## Test plan

- Empty KB → ledger writes with `total: 0`, no crash.
- A KB with one bare PDF (no summary) → that paper appears in the reading backlog at
  `read_depth: none`.
- A KB with a Tier-A summary whose `source_pdf_sha256` matches its PDF → `read_depth: full`,
  not in the backlog.
- An unreadable `.pdf` stub (no `%PDF-` magic / < 1000 bytes) → re-fetch queue.
- Re-running is a no-op on content (the `_papers_index.md` is not itself re-scanned as a paper).

## Related

- `vaultlab.research.papers_index` — the underlying ledger module.
- `/lit-arc` — fetches + summarizes a corpus and refreshes this ledger automatically.
- `/full-reader` — deep-read one paper (moves it from backlog to `read_depth: full`).
- `/cite` — citation verification; an unread paper's claim is scored `UNVERIFIED`
  until it is actually read (the backlog made visible at the claim level).
