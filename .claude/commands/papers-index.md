---
name: papers-index
description: Build/update a project's persistent papers index — one entry per paper with title, DOI, PDF presence + readability, read depth, and verification status. Lets an agent understand the corpus from one file without re-reading every paper. Additive; never touches existing notes.
arguments: [build|status] [--kb <path>]
---

# /papers-index [build|status]

> Engine: `vaultlab.research.papers_index`. Index lives at `<kb>/Sources/Papers/_papers_index.{json,md}`.
> Read the `.md` first to understand the corpus; open a per-paper note only when you need its detail.

The index is the fast-access layer over the deep per-paper reads. The deep reading is done ONCE per
paper and captured in `Sources/Papers/<slug>.md`; the index aggregates identity + status + a digest so
a later agent (or a later fetch run) does not re-read or re-download what is already accounted for.

## Build / update the index

```python
import sys; sys.path.insert(0, "src")
from pathlib import Path
from vaultlab.research.papers_index import build_papers_index, save_index

papers_dir = Path(kb_root) / "Sources" / "Papers"
index = build_papers_index(papers_dir)
save_index(index, papers_dir)           # writes _papers_index.json + _papers_index.md
print(index.counts)
```

What each status means:
- `pdf_present` — a `<slug>.pdf` exists next to the note.
- `pdf_readable` — that PDF passes the `%PDF-` magic + min-size check; **False means a paywall stub /
  truncated download → re-fetch** (feed it to `/cite` HARVEST or `vaultlab fetch-list paywalled`).
- `read_depth` — `none` / `noted` / `deep` (deep = several sections + quoted evidence).
- `verification` — from the note's `status:` frontmatter (`VERIFIED` / `UNVERIFIED`).

## Per-paper read protocol (the "as much reading as possible" contract)

When a paper is fetched or first encountered, do a DEEP read and record it in `Sources/Papers/<slug>.md`
so the index can account for it. The note's frontmatter is the machine-readable status; the body is the
organization. Minimum contract (extend with Bobby's additions below):

1. **Frontmatter** (parsed into the index): `title`, `authors`, `year`, `journal`, `doi`,
   `ref_number` (if cited), `status` (`VERIFIED` once read from the PDF; else `UNVERIFIED`).
2. **Identity check first.** Confirm the PDF's title/authors/journal/DOI match the citation before
   recording anything (see `/cite`). On mismatch, quarantine and mark `UNVERIFIED`.
3. **Read the full PDF page images**, not text extraction. Account for the paper's organization with
   `## ` sections, e.g. `## What it does`, `## Key results (verified, with quotes)`, `## Methods`,
   `## Figures/Tables`, `## Verdict`.
4. **Quote high-stakes numbers verbatim** with their `[table/figure/pN]` location.
5. **First prose paragraph = the digest** the index surfaces, so lead with a clear 1-3 sentence summary.
6. Once verified, set `status: VERIFIED` in the frontmatter so `/papers-index` and the
   `VERIFICATION_LEDGER` agree.

<!-- BOBBY: add your per-paper / per-knowledge details here — what else every paper note must record
     (relevance-to-aim, tags, reading TODOs, organization fields). These flow into the note frontmatter
     and the index `extra` field. -->

## How an agent should USE the index

Before reading any paper folder, read `_papers_index.md`. It tells you which papers exist, which have
good PDFs, which are verified, and a digest of each — so you only open the full notes you actually need,
and you never re-fetch a paper already present and readable.
