---
name: vaultlab.research.full_reader
description: Bilingual, figure-aware, source-grounded full-paper Markdown reader. Turn a paper (PDF / DOI / arXiv / URL / pasted text) into a complete `paper.md` with original text, paragraph-aligned translation, inline figures/tables, and stable anchor IDs (S/C/F/T) for source grounding. Writes provenance receipts (Red Line #2). Absorbed from the `nature-reader` skill in sub-goal 2.1.
---

# vaultlab.research.full_reader

Use this module to turn a research paper into a **complete bilingual Markdown
reading artifact** — not a summary, not a slide deck, not a citation list.

It absorbs the [`nature-reader`](https://github.com/.../nature-skills) skill
into vaultlab so the contract survives across LLM providers and integrates
with vaultlab's provenance / figure-acquisition / paperclip primitives.

## When to use this skill

Use `vaultlab.research.full_reader.build_paper_reader` when the user wants any
of the following:

- Translate an entire paper into a complete Markdown document.
- Read a paper in two languages side-by-side, paragraph-aligned.
- Generate a reading file with figures and tables placed near the prose that
  introduces them.
- Preserve exact source locations (S001 / C001 / F001 / T001 anchors) on every
  substantive block so downstream answers can cite by ID.
- Produce a source-grounded Markdown artifact with provenance receipts.

## When NOT to use this skill

| Need | Use this instead |
| --- | --- |
| Only the abstract | `vaultlab.research.abstract_recall.get_abstract_for_doi` |
| A short TL;DR / structured summary | `vaultlab.research.summarize.summarize_paper` |
| Batched cross-paper synthesis (5-15 PDFs in one LLM call) | `vaultlab.research.batched_reader` — **planned / not yet implemented (not on disk)** |
| Citation / DOI verification | `vaultlab.citations` |
| Slide deck output | `vaultlab.slides` |

## Public API

```python
from vaultlab.research.full_reader import build_paper_reader

paper_md = build_paper_reader(
    "10.1038/s41586-023-05915-x",  # PDF path / DOI / arXiv / URL all accepted
    out_dir="reading/2026-paper",
    target_lang="zh-CN",  # ISO code; default zh-CN matches nature-reader
    paperclip_id="arx_2107.07953",  # optional bypass for the paperclip corpus
)
# -> Path("reading/2026-paper/paper.md")
#    plus paper.md.provenance.json and paper.md.method.md sidecars
```

## Output structure

```markdown
# Paper Title

**DOI:** 10.1038/...
**Source:** /path/or/url
**Target language:** zh-CN
**Generated:** 2026-05-15T...

## Abstract <a id="C001"></a>

> Original English abstract...
>
> **Translation (zh-CN):** 翻译后的中文文本...

## Introduction <a id="S001"></a>

> Original English paragraph...
>
> **Translation (zh-CN):** 翻译...

### Figure 1 <a id="F001"></a>

![Figure 1](figures/fig_1.png)

**Caption (original):** ...
**Caption (translated, zh-CN):** ...

## Methods <a id="S002"></a>
...
```

### Anchor scheme

- `S001`, `S002`, ... — body paragraphs in document order
- `C001` — abstract (caption-style block)
- `F001`, `F002`, ... — figures
- `T001`, `T002`, ... — tables

Anchors are three-digit zero-padded so they sort lexicographically for the
common case (< 1000 blocks per paper).

### Figure placement

Figures and tables are placed **immediately after the body paragraph whose
text mentions their label** (case-insensitive substring match on the label,
e.g. "Figure 1"). Anything not matched is appended at the end so nothing is
silently dropped. This is intentionally simple — semantic placement perfect
to the pixel is out of scope; the contract is "near the relevant discussion."

## Architecture

Two replaceable seams keep the module deterministic in tests and pluggable in
production:

1. `_extract_paper_content(source, paperclip_id=None) -> PaperContent`
   pulls structured blocks (abstract / body paragraphs / figures / tables).
   The default raises `NotImplementedError` because returning an empty
   `PaperContent` would silently produce a useless `paper.md` (Red Line #2).
   Production callers monkeypatch this to dispatch through:
   - `vaultlab.research.read_paper.read_paper_sections` for PDFs
   - paperclip MCP for the 8M-paper corpus
   - `vaultlab.figures.acquisition.acquire_figures` for figures

2. `_translate_blocks(blocks, target_lang) -> list[str]` is the LLM seam.
   The default implementation is an **identity passthrough** so the module
   degrades gracefully without an LLM. Production callers monkeypatch this
   to call DeepSeek / GLM / Qwen / Kimi / Anthropic / etc. (the
   nature-reader SKILL.md lists OpenAI-compatible endpoints).

## Provenance contract (Red Line #2)

Every call writes three artifacts:

- `paper.md` — the reading file.
- `paper.md.provenance.json` — machine-readable receipt with input hashes,
  generation params (target_lang, n_body_blocks, n_figures, n_tables, doi).
- `paper.md.method.md` — human-readable narrative for the methods section
  of a downstream manuscript.

Also appends a JSONL line to `.vaultlab-provenance.jsonl` in `out_dir` for
cheap "find every paper.md generated for project X" queries.

## Translation quality bar

Per the nature-reader SKILL.md:

- Translate for **meaning**, not style.
- Preserve gene names, protein names, formulas, model names, symbols.
- Keep citations, superscripts, subscripts, and numeric values unchanged.
- Do not collapse method details into vague prose.
- Mark uncertain text instead of guessing.
- Keep the source's paragraph form — do not convert prose into keyword bullets.

The default identity-passthrough translator satisfies these trivially (it
returns the original). Real LLM-backed implementations must self-enforce.

## Status

Sub-goal 2.1 of `.claude/goals/vaultlab-north-star-plan.md`: **shipped 2026-05-15**.

This is the framework + end-to-end path on stubbed inputs. Wiring real PDF
parsing and a real LLM provider into the two seams is a downstream concern
(not blocking on this sub-goal).
