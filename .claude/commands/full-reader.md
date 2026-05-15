---
name: full-reader
description: Turn a paper (DOI / paperclip-ID / PDF / arXiv ID / URL) into a complete bilingual figure-aware paper.md reading file. Preserves full prose, pairs each paragraph with a same-language translation (default zh-CN), inlines figures + tables near their referencing text, and stamps stable anchor IDs (S001/C001/F001/T001) for source-grounded citation.
arguments: <paper-source> [--out <out-dir>] [--lang <iso-code>] [--paperclip-id <id>] [--weight light|medium|heavy]
---

# /full-reader <paper-source>

> *"Read the whole paper in two languages, with the figures in the right
> place and every paragraph carrying a citable anchor — drop the result
> into Wiki/Summaries for any downstream consumer."*

Drives `vaultlab.research.full_reader.build_paper_reader`. Absorbed
from the nature-reader skill (Sub-goal 2.1, 2026-05-15). Produces a
single `paper.md` artifact with:

- **Full prose** with section structure intact (not a summary).
- **Bilingual** — original text paired with a same-language translation
  paragraph-by-paragraph. Default target is `zh-CN`; any ISO code works
  (`ja`, `es`, `fr`, ...).
- **Figures + tables inline** — placed immediately after the body
  paragraph that mentions their label (case-insensitive substring match).
  Anything unmatched goes at the end so nothing is silently dropped.
- **Stable anchor IDs** on every substantive block:
  `S001/S002/...` (body), `C001` (abstract / caption),
  `F001/F002/...` (figures), `T001/T002/...` (tables).
- **Provenance receipts** — `paper.md.provenance.json` +
  `paper.md.method.md` sidecars + JSONL index entry (Red Line #2).

## When to use this (vs. neighbours)

| Module | When |
|---|---|
| `vaultlab.research.abstract_recall` | When you only need the abstract |
| `vaultlab.research.summarize` / batched reader | Short structured summary (TL;DR + findings list) |
| `vaultlab.research.full_reader` (**this command**) | Complete bilingual reading file with section-grounded anchors and inline figures |

## Pre-flight

1. Resolve `<paper-source>` — accepts a PDF path, DOI, arXiv ID, URL,
   or paperclip ID
2. Resolve `--out` (default: `Sources/Notes/<doi-or-id-slug>/`)
3. Resolve `--lang` (default: `zh-CN`)
4. Resolve `--paperclip-id` — bypasses re-parsing when the paper is
   already in the paperclip filesystem

## Execution

```python
import shlex
from pathlib import Path
from vaultlab.research.full_reader import build_paper_reader
from vaultlab.context import resolve_kb_root, KbRootNotConfigured

# Parse $ARGUMENTS
raw_args = shlex.split("$ARGUMENTS") if "$ARGUMENTS" else []
positional: list[str] = []
out_dir_arg: str = ""
lang_arg: str = "zh-CN"
paperclip_id_arg: str | None = None
weight_arg: str | None = None
i = 0
while i < len(raw_args):
    tok = raw_args[i]
    if tok == "--out" and i + 1 < len(raw_args):
        out_dir_arg = raw_args[i + 1]
        i += 2
    elif tok == "--lang" and i + 1 < len(raw_args):
        lang_arg = raw_args[i + 1]
        i += 2
    elif tok == "--paperclip-id" and i + 1 < len(raw_args):
        paperclip_id_arg = raw_args[i + 1]
        i += 2
    elif tok == "--weight" and i + 1 < len(raw_args):
        weight_arg = raw_args[i + 1]
        i += 2
    else:
        positional.append(tok)
        i += 1
source = " ".join(positional).strip()
if not source:
    raise SystemExit("usage: /full-reader <paper-source> [--out ...] [--lang ...]")

try:
    kb_root = resolve_kb_root()
except KbRootNotConfigured as exc:
    print(f"No KB configured. Run `vaultlab init` (default: {exc.suggested_default}).")
    raise SystemExit(1)

# Default out_dir lands the artifact under Sources/Notes so it joins the
# rest of the bilingual reading files alongside lit-search outputs.
if not out_dir_arg:
    from vaultlab.research.acquisition import doi_slug
    slug = doi_slug(source) or "paper"
    out_dir_arg = str(kb_root / "Sources" / "Notes" / slug)

paper_md = build_paper_reader(
    source,
    out_dir=out_dir_arg,
    target_lang=lang_arg,
    paperclip_id=paperclip_id_arg,
    weight=weight_arg,  # None → auto-classified as "medium"
)

print(f"Wrote {paper_md}")
print(f"to open: bobby-kb open {paper_md.relative_to(kb_root)}")
```

## Output

- `<out_dir>/paper.md` — bilingual reading file with inline figures + tables
- `<out_dir>/paper.md.provenance.json` — Red Line #2 manifest (inputs,
  model id, params: target_lang, n_body_blocks, n_figures, n_tables)
- `<out_dir>/paper.md.method.md` — short prose method record
- `<out_dir>/.vaultlab-provenance.jsonl` — appended index entry

## Test plan

- Sanity input: `/full-reader 10.1038/s41586-023-05915-x` →
  `Sources/Notes/10-1038-s41586-023-05915-x/paper.md` with at least an
  abstract block (C001) and one body block (S001).
- Multi-figure paper: every `Figure 1` mention in the body should be
  followed by an inline figure block; orphan figures land at the end of
  the document.
- Translation seam: when no LLM is wired up, the translation channel
  passes through identity — the file still renders without crashing.
- Provenance: both sidecars must exist next to `paper.md`.

## Rules of engagement

- **Don't summarise.** This command preserves the paper's full prose;
  pair with `/lit-arc` if you want a multi-paper narrative.
- **Anchors are stable.** Once `S007` is assigned to a paragraph,
  downstream commands (cite-watch, narrate-finding, journal-club) will
  cite back to it. Re-running on the same DOI re-emits the same IDs in
  the same order.
- **Figures match by label substring.** If the paper writes
  `Fig 1A, B and C` and the figure is captioned `Figure 1A-C`, the
  matcher pairs them. Edge-case captions that never appear in the body
  land at the document tail in label order.

## Related

- `vaultlab.research.full_reader` — underlying renderer
- `vaultlab.research.full_reader.md` — companion SKILL.md ("when to use")
- `/lit-arc` — multi-paper lineage narrative (uses `paper.md` files via
  `Wiki/Summaries`)
- `/narrate-finding` — KB concept page about a single finding (can cite
  full-reader anchors directly)
- nature-reader skill at `nature-skills/skills/nature-reader/SKILL.md` —
  upstream contract
