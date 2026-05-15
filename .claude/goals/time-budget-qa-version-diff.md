# /goal: time-budget audit + Q&A anticipator + slide-version diff (Phase 7.3 finish)

_Created: 2026-05-15_
_Working dir: `C:/Users/bobby/Downloads/vaultlab`_

## CONTEXT

- **Phase:** 7.3 close-out.
- **Prior state:** sub-goal 5.4 (`vaultlab.slides.self_review.review_deck`, commit `981e6d3`) shipped a unified self-review pass covering layout hard rules + story-arc continuity + WCAG color contrast. Three pieces of the original Phase 7.3 vision were still outstanding:
  1. Time-budget audit
  2. Q&A anticipator
  3. Slide-version diff (two-pptx)
- **Advances:** the deck pipeline now has a self-contained "ship-readiness" pass that also estimates speak-time vs a target slot, surfaces likely audience questions, and can diff two versions of a deck — all reusable from `vaultlab.slides.review_deck` (additive kwargs) or as standalone primitives.

## SUCCESS CRITERIA

1. `vaultlab.slides.time_budget.audit_time_budget(pptx, budget_minutes=..., qa_reserve_minutes=...)` returns a `TimeBudgetReport` with per-slide kind + estimate and an aggregate `over_budget()` verdict. ✅
2. `vaultlab.slides.qa_anticipator.anticipate_qa(pptx, runner_callback=None, n_questions=...)` returns a ranked `list[AnticipatedQuestion]`. LLM mode (callback present) AND heuristic fallback both work. ✅
3. `vaultlab.slides.version_diff.diff_decks(a, b)` returns a `DeckDiff` with per-slide `added` / `removed` / `modified` / `unchanged` records and field-level change tuples. ✅
4. `vaultlab.slides.self_review.review_deck` accepts optional `budget_minutes` + `anticipate_questions` kwargs and stores their outputs on the report; no behavior change when the kwargs are omitted. ✅
5. Unit tests cover: time-budget under/over verdicts + per-slide kind classification; Q&A heuristic + LLM mode + LLM-failure fallback; version diff add / remove / modify / unchanged. ✅
6. Full slides suite + invariants stay green. ✅

## PROGRESS

- `src/vaultlab/slides/time_budget.py` (new, ~280 lines)
  - `SlideTimeEstimate` + `TimeBudgetReport` dataclasses.
  - Per-slide kind classifier (`title` / `section_divider` / `bullets` / `figure` / `methods` / `references` / `acknowledgments` / `discussion` / `other`) with internal sub-kinds (`bullets_heavy`, `figure_heavy`) for finer-grained timing.
  - Heuristic base seconds tuned against 10-min Hickey-lab journal-club rhythm; bullets get a +5s/bullet density adjustment capped at +30s.
- `src/vaultlab/slides/qa_anticipator.py` (new, ~290 lines)
  - `AnticipatedQuestion` dataclass.
  - Heuristic templates for four trigger families: statistics (`p<...`, `n=...`, `%`, SE/SD/CI), comparisons (`vs` / `compared to`), future work (`future`, `next steps`, `plan to`, `in N months`), limitations (`limitations`, `caveats`, `sample size`, `small n`).
  - LLM mode: serializes the deck into a compact JSON-prompt; tolerates code fences + prose wrapping when parsing the response; gracefully falls back to heuristics if the callback raises or the response is unparseable.
- `src/vaultlab/slides/version_diff.py` (new, ~290 lines)
  - `SlideDiff` + `DeckDiff` dataclasses.
  - Three-pass matching: title-key (1:1 only — duplicates fall through), body-fingerprint (normalized whitespace + MD5), positional fallback.
  - Field-level diffs by shape kind: text-shape text comparison, picture-shape MD5 comparison, kind-mismatch as a coarse change.
- `src/vaultlab/slides/self_review.py` — `review_deck` extended with `budget_minutes` / `qa_reserve_minutes` / `anticipate_questions` / `qa_runner_callback` / `qa_n_questions` kwargs. Defaults to no-op; over-budget decks pick up a story-arc warning (`rule="time-budget-over"`). Added `time_budget` + `anticipated_questions` fields to `ReviewReport`.
- `src/vaultlab/slides/__init__.py` — re-exports the new public names.
- `tests/test_vaultlab_slides/test_time_budget.py` (new, 14 tests)
- `tests/test_vaultlab_slides/test_qa_anticipator.py` (new, 9 tests)
- `tests/test_vaultlab_slides/test_version_diff.py` (new, 9 tests)
- `tests/test_vaultlab_slides/test_self_review.py` — 4 new tests for the add-on wiring.

## EVIDENCE

```
$ python -m pytest tests/test_vaultlab_slides/test_time_budget.py \
    tests/test_vaultlab_slides/test_qa_anticipator.py \
    tests/test_vaultlab_slides/test_version_diff.py \
    tests/test_vaultlab_slides/test_self_review.py -q
....................................................                     [100%]
52 passed in 3.97s

$ python -m pytest tests/test_vaultlab_slides/ -q
327 passed in 27.03s

$ python -m pytest tests/test_vaultlab_invariants/ -q
8 passed in 1.21s
```

## DECISIONS / NOTES

- **Heuristic ceiling, LLM floor — not the other way around.** The Q&A anticipator works without any LLM so it can ship in CI and unit tests. The runner_callback path is a pure upgrade, not a requirement.
- **Time-budget heuristics intentionally conservative.** Estimates are slightly LONGER than practiced run-time. Bobby would rather over-budget on paper and have 30s of slack in the room than the inverse.
- **Internal sub-kinds (`bullets_heavy` / `figure_heavy`) collapse to public kinds** before being stored on `SlideTimeEstimate.kind`. Public surface stays small (8 kinds) while the estimator can still discriminate inside.
- **Three-pass matching in `diff_decks`** prefers title-stable matching for reordered decks. Body-fingerprint catches retitled-but-otherwise-identical slides. Positional fallback covers the no-stable-id worst case.
- **Title-key matching is 1:1 only.** When the same title appears more than once on either side, those slides fall through to body-fingerprint / positional matching to avoid arbitrary picks.
- **`review_deck` add-ons are pure additions.** Defaults make the new kwargs no-ops, so the existing CLI gate and previous tests stay byte-identical.
- **No CLI wiring this round.** Phase 7.3 close-out is library-tier. CLI surface for the three new primitives can land in a follow-up if needed; the slash-command catalog already exposes `slides review` and isn't strictly tied to these.

## OPEN / DEFERRED

- LLM-mode prompt is a single-shot JSON-list ask. A future iteration could chain "summarize each slide" → "ask N questions across the deck" for higher-quality questions on long decks.
- Version diff doesn't yet detect position shifts (a slide moved from index 3 → 5 with no content changes will currently match by title and report as `unchanged` — which is arguably correct, but a downstream reader might want to know it moved).
- Time-budget estimates ignore speaker-notes density. The notes carry the script — a denser notes block usually means the slide takes longer to talk through. Hook is `vaultlab.slides.notes.parse_speaker_notes` if we want to weight by it later.
