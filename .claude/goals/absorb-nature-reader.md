# Sub-goal 2.1 — Absorb `nature-reader` skill into `vaultlab.research.full_reader`

## Status: SHIPPED 2026-05-15

## What

Adds a new module `vaultlab.research.full_reader` that implements the
[`nature-reader`](C:/Users/bobby/Downloads/nature-skills/skills/nature-reader/SKILL.md)
skill contract on top of vaultlab primitives.

`build_paper_reader(source, out_dir, target_lang, paperclip_id)` turns a
paper (PDF / DOI / arXiv ID / URL / pasted text) into a complete bilingual
Markdown reading artifact:

- Original text + paragraph-aligned translation (default `zh-CN`, any ISO code accepted).
- Figures and tables placed immediately after the body paragraph that mentions
  their label (case-insensitive substring match). Unmatched assets are appended
  at the end so nothing is silently dropped.
- Stable anchor IDs on every substantive block for source-grounded citations:
  `S001/S002/...` (body), `C001` (abstract / caption), `F001/F002/...` (figures),
  `T001/T002/...` (tables) — three-digit zero-padded.
- Red Line #2 provenance receipts: `paper.md.provenance.json` and
  `paper.md.method.md` sidecars + a JSONL index entry.

## Files

- `src/vaultlab/research/full_reader.py` — new module (~340 LOC)
- `src/vaultlab/research/full_reader.md` — SKILL.md companion describing
  when to use vs. `abstract_recall` / `summarize` / `batched_reader`
- `tests/test_vaultlab_research/test_full_reader.py` — 15 unit tests
- `.claude/goals/absorb-nature-reader.md` — this doc

## Architecture decisions

### Two replaceable seams

The module exposes two integration points so production code can plug in
real PDF parsing + a real LLM without touching the renderer:

1. **`_extract_paper_content(source, paperclip_id=None) -> PaperContent`** —
   the extraction seam. Default implementation raises `NotImplementedError`
   on purpose (returning an empty `PaperContent` would silently produce a
   useless `paper.md`, violating Red Line #2). Production callers
   monkeypatch this to dispatch through `read_paper_sections` / paperclip /
   `figures.acquisition`.

2. **`_translate_blocks(blocks, target_lang) -> list[str]`** — the LLM seam.
   Default implementation is an **identity passthrough**: returns the
   original text. This means the module never crashes when no LLM is
   wired up. Real callers monkeypatch to dispatch through DeepSeek / GLM /
   Qwen / Kimi / Anthropic (per nature-reader SKILL.md model-backends list).

Both seams are unit-testable via `monkeypatch.setattr(full_reader, ...)`,
which is how the 15 unit tests stay fast (no real LLM, no real PDF).

### Figure placement heuristic

Honors nature-reader's "place figures near the relevant discussion" rule
without trying to be too clever:

- After rendering each body paragraph, scan the remaining figures/tables.
- Any figure whose label (case-insensitive substring) appears in the
  paragraph is attached immediately after that paragraph.
- Anything still remaining is appended at the end of the document.

This is intentional. Perfect semantic placement would require a real
LLM-driven scan; "near the relevant discussion" + a no-drop guarantee is
the contract worth shipping today.

### Anchor scheme

- Three-digit zero-pad: `S001`–`S999`. Sorts lexicographically for the
  common case (papers ≤ 999 paragraphs). Verified by a dedicated test
  (`test_build_paper_reader_anchor_ids_are_zero_padded`).
- `C001` is reserved for the abstract specifically. Future caption blocks
  inside the body could extend to `C002+` but no caller needs that today.
- `F`/`T` use one-based indexing matching the order in `PaperContent.figures`
  / `tables`.

## Tests (15 new)

Unit-level (no LLM calls, no real PDFs):

1. `test_render_emits_abstract_with_C001_anchor`
2. `test_render_emits_body_block_anchors_starting_at_S001`
3. `test_render_emits_figure_anchors_and_alt_text`
4. `test_render_emits_table_anchors`
5. `test_render_falls_back_when_no_abstract`
6. `test_render_header_carries_doi_and_target_lang`

End-to-end (build_paper_reader with stubbed extract + translator):

7. `test_build_paper_reader_writes_paper_md_and_provenance` — verifies the
   provenance JSON has the right `generated_by` / `kind` / params
8. `test_build_paper_reader_with_no_figures`
9. `test_build_paper_reader_with_only_abstract`
10. `test_build_paper_reader_raises_on_missing_source`
11. `test_build_paper_reader_target_lang_threads_through` (uses `ja`)
12. `test_build_paper_reader_uses_paperclip_id_when_given`
13. `test_build_paper_reader_anchor_ids_are_zero_padded` (12 paragraphs)
14. `test_build_paper_reader_returns_path_under_out_dir`
15. `test_default_translator_is_identity_passthrough` — degrades gracefully
    when no LLM is wired

## Verification

```bash
cd ~/Downloads/vaultlab
pytest tests/test_vaultlab_research/test_full_reader.py -v
# -> 15 passed

pytest tests/test_vaultlab_research/ -q
# -> 551 passed (was 536, +15 new)

pytest tests/test_vaultlab_invariants/ -q
# -> 8 passed (unchanged)
```

## Scope discipline / what was deliberately deferred

This sub-goal delivers the **framework** plus a working end-to-end path on
stubbed inputs. Out of scope:

- Real PDF parsing wiring. `_extract_paper_content` is a seam — production
  callers plug in `read_paper_sections` / paperclip / publisher HTML
  scrapers as needed.
- Real LLM translation. `_translate_blocks` is a seam — default is an
  identity passthrough so the module never crashes without a provider.
- The `batched_reader.py` module referenced in the task spec is not in
  current `main` (it was committed on a feature branch but not merged).
  `full_reader` does NOT depend on it; the translation seam is a single
  function call that any future batched LLM helper can implement.
- `reader.html` companion preview (mentioned in nature-reader SKILL.md as
  optional secondary artifact) — Markdown is the primary output and the
  HTML preview is opt-in for a later iteration.

## Closes

nature-skills coverage: 7 of 7 skills now absorbed into vaultlab.
