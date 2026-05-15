# /goal: wire write_receipts into manuscript/* + report/dispatch (sub-goal 1.2b complete)

_Created: 2026-05-15_
_Working dir: `C:/Users/bobby/Downloads/vaultlab`_
_Parent: `.claude/goals/parallel-execute-north-star.md` (Agent A)_

## CONTEXT

- **Project:** vaultlab v0.0.4-dev
- **Sub-goal:** 1.2b — wire `write_receipts` into the remaining artifact-producing entrypoints
- **Strategic reference:** `.claude/goals/vaultlab-north-star.md`
- **Prior state:** invariant suite 7 passed / 1 xfailed; `citations/reporter.py` had already been wired (commit `272d2d4`).
- **Red line being enforced:** #2 (no silent failures — every artifact-producing entrypoint writes a `.provenance.json` + `.method.md` sidecar).

## SUCCESS CRITERIA

1. `write_receipts` calls present in `vaultlab/manuscript/polish.py`, `respond.py`, `data_availability.py`, `report/dispatch.py`. ✅
2. xfail marker removed from `tests/test_vaultlab_invariants/test_red_lines.py::test_every_artifact_entrypoint_writes_manifest`. ✅
3. Invariant suite: 8 passed / 0 xfailed. ✅
4. `tests/test_vaultlab_manuscript/` + `tests/test_vaultlab_report/` no regression. ✅ (122 passed)
5. Slides tests still green (added provenance to `slides/render.py` to close coverage). ✅ (223 passed)
6. Goal file committed.
7. Pushed to `origin/main`.

## PROGRESS

- [2026-05-15] Read `citations/reporter.py:73-90` as the reference pattern.
- [2026-05-15] Discovered the three manuscript modules (`polish.py`, `respond.py`, `data_availability.py`) had **no I/O** at all — they returned strings/dataclasses. The cleanest minimal-additive approach was to add a single `write_*` function per module that wraps the existing renderer and emits provenance sidecars (mirroring the `respond_html.write_response_letter_html` shape that already exists).
- [2026-05-15] Added tests first (TDD):
  - `test_write_polish_report_emits_provenance`
  - `test_write_response_letter_emits_provenance`
  - `test_write_data_availability_statement_emits_provenance`
- [2026-05-15] Implemented the three write functions + threaded `write_receipts` through `report/dispatch.write_artifact_html`.
- [2026-05-15] Ran invariant suite — got **1 fail**, not pass. The test exposed that `vaultlab/slides/render.py` ALSO lacked `write_receipts` (was in `ARTIFACT_ENTRYPOINTS` all along; xfail message had mentioned `slides/deck.py` was wired but not `slides/render.py`). See "Decisions made" below.
- [2026-05-15] Wired `slides/render.py::render_pptx` to emit `kind="slide_deck"` provenance after `pres.save()`.
- [2026-05-15] Invariant suite: 8 passed / 0 xfailed. Manuscript + report + slides tests all green.

## EVIDENCE

### Final test runs

```
pytest tests/test_vaultlab_invariants/ -v
  → 8 passed in 1.19s   (was: 7 passed, 1 xfailed)

pytest tests/test_vaultlab_manuscript/ tests/test_vaultlab_report/ -q
  → 122 passed in 0.50s  (no regression; 3 new tests added)

pytest tests/test_vaultlab_slides/ -q
  → 223 passed in 14.45s (no regression)
```

### Files modified

```
M  src/vaultlab/manuscript/polish.py          (+ write_polish_report)
M  src/vaultlab/manuscript/respond.py         (+ write_response_letter)
M  src/vaultlab/manuscript/data_availability.py (+ write_data_availability_statement)
M  src/vaultlab/report/dispatch.py            (provenance in write_artifact_html)
M  src/vaultlab/slides/render.py              (provenance in render_pptx)
M  tests/test_vaultlab_invariants/test_red_lines.py (removed xfail decorator)
M  tests/test_vaultlab_manuscript/test_polish.py (+ provenance test)
M  tests/test_vaultlab_manuscript/test_respond.py (+ provenance test)
M  tests/test_vaultlab_manuscript/test_data_availability.py (+ provenance test)
A  .claude/goals/wire-manuscript-report-provenance.md
```

## Decisions made

- **Added new `write_*` functions to manuscript modules instead of trying to graft provenance onto string-returning renderers.** The three manuscript modules (`polish.py`, `respond.py`, `data_availability.py`) only returned strings — they had no write site at all. The minimal-additive choice: add one `write_*(out_path, ...)` per module that wraps the renderer + writes the sidecars. This mirrors how `respond_html.py` ships both `build_*` (string) and `write_*` (file + provenance) in pairs, and how `citations/reporter.py::generate_report` accepts an optional `output_path` and conditionally writes the receipt.

- **Wired `vaultlab/slides/render.py::render_pptx` as well, even though the parent plan didn't list it.** Reason: when I removed the xfail decorator the test failed on `vaultlab/slides/render.py` (not on any of the four modules I was assigned). The parent goal file's success criterion #3 says "Last invariant xfail flips to pass" — that cannot happen without wiring `render.py`. Cross-checked: Agent B's parallel work is "4 new slide layouts" in `vaultlab/slides/layouts/`, which does not touch `render.py`, so there is no merge collision. The xfail's own reason string had listed `slides/deck.py` as already-wired, but the test scans `slides/render.py` (a specific file path in `ARTIFACT_ENTRYPOINTS`), so deck.py's provenance never satisfied the test.

- **Refactored `write_artifact_html` to call `_detect_kind` once and pass the resolved kind into both `render_artifact_html` and the provenance record.** Previously the dispatcher detected twice (once inside the writer for the render call, once inside `render_artifact_html` itself). The refactor is functionally equivalent — `render_artifact_html` is idempotent when given an explicit `kind=` — and lets the provenance record capture the resolved artifact kind without a second detection pass.

- **Used `ProvenanceRecord(kind=...)` values exactly as the parent task specified:** `manuscript_polish`, `manuscript_response`, `manuscript_data_availability`, `html_report`. For `slides/render.py` I picked `slide_deck` to match the pre-existing `slides/deck.py` convention.

## Files skipped

- **None of the listed targets were skipped.**
- Touched one file (`slides/render.py`) outside the listed targets — see "Decisions made" above for the rationale. The alternative (leave it unwired and document a BLOCKED) would have left success criterion #3 unmet despite all four listed targets being correctly wired.

## Known limitations / followups

- The new `write_*` functions in the manuscript modules are not yet wired into a slash command — they're available as a library API. A followup sub-goal could expose them via `/manuscript polish`, `/manuscript respond`, `/manuscript data-availability`.
- `write_polish_report` only checks long sentences + US spelling. The 12-step `WORKFLOW_STEPS` workflow is still LLM-driven at slash-command time. The provenance record captures the two mechanical checks so reviewers can tell what was audited.

## Commit

`feat(audit): wire provenance receipts into manuscript/* + report/dispatch (sub-goal 1.2b complete)`
