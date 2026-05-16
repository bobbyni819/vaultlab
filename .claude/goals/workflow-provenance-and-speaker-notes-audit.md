# /goal: workflow Provenance gets params dict + speaker-notes structure audit

_Created: 2026-05-15_
_Working dir: `C:/Users/bobby/Downloads/vaultlab`_

## CONTEXT

Two bundled followups from previously-shipped work:

- **Item 1 — Workflow Provenance gets a params dict.** The deep-think
  crosstalk wiring (commit `55c5379`) deferred unifying the workflow
  `Provenance` dataclass with the project-wide `ProvenanceRecord`. The
  workflow form has only `tags` + `notes`; the project-wide form has
  `params: dict[str, Any]`. Crosstalk decisions were encoded into tags
  and notes as a workaround. This goal promotes workflow `Provenance` to
  carry `params` too and migrates the deep-think wiring to use it.
- **Item 2 — Speaker-notes structure audit.** Sub-goal 5.4
  (commit `981e6d3`) deferred enforcing Bobby's
  `feedback_slide_hard_rules` two-tier speaker-notes rule (mental_map
  heading + 200-400 word script) in `vaultlab.slides.self_review`. This
  goal adds the audit.

## SUCCESS CRITERIA

### Item 1
1. ✅ `vaultlab.workflows._provenance.Provenance` gains `params: dict[str, Any]`.
2. ✅ `to_dict()`, `from_dict()`, frontmatter rendering, and the JSON
   sidecar bridge all preserve `params`.
3. ✅ `_record_crosstalk_decision` populates `prov.params["crosstalk_invoked"]`,
   `prov.params["crosstalk_task_kind"]`, and `prov.params["crosstalk_skip_reason"]`
   in addition to (not replacing) the existing `tags` + `notes` writes.
4. ✅ Existing tests in `test_deep_think_crosstalk_wiring.py` still pass.
5. ✅ New assertions on `prov.params` added to that file.

### Item 2
1. ✅ New `_check_speaker_notes` audit hooked into `_review_one_slide`.
2. ✅ Rules:
   - figure / data slide with EMPTY notes → critical
   - notes present but no mental_map heading → warning
   - script body < 100 words on body slide → warning
   - script body > 500 words → warning
   - title / divider slides exempt from body-word-count rule
3. ✅ 5 new tests in `test_self_review.py` cover each branch.
4. ✅ `pytest tests/test_vaultlab_invariants/ -q` still 8/0.

## NON-GOALS

- Don't change behavior of the sidecar `ProvenanceRecord` API.
- Don't refactor `parse_speaker_notes`; reuse it.
- Don't touch `tests/test_vaultlab_workflows/test_crosstalk_no_lit_search.py`
  (another agent is working there).

## FILES TO TOUCH

- `src/vaultlab/workflows/_provenance.py` — add `params` field + propagation
- `src/vaultlab/workflows/deep_think.py` — migrate `_record_crosstalk_decision`
- `tests/test_vaultlab_workflows/test_deep_think_crosstalk_wiring.py` — assertions
- `src/vaultlab/slides/self_review.py` — `_check_speaker_notes`
- `tests/test_vaultlab_slides/test_self_review.py` — 5 new tests

## COMMIT MESSAGE

```
feat: workflow Provenance gets params dict + speaker-notes structure audit
```
