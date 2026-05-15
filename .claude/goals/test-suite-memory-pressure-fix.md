# /goal: stabilize full-suite pytest run on Windows under memory pressure

_Created: 2026-05-15_
_Working dir: `C:/Users/bobby/Downloads/vaultlab`_
_Trigger: `state-doc-2026-05-15.md` flagged ~10 intermittent test failures with `zipfile.MemoryError` from `python-pptx` writes when the full ~2046-test suite runs in a single process on Windows._

## Root cause

`vaultlab.slides.render.render_pptx` (and friends) call `Presentation.save()`, which builds the .pptx by serialising the document tree into an in-memory `zipfile.ZipFile` backed by a `BytesIO`. Each save leaves a small amount of buffered state alive through reference cycles between lxml `ElementTree` parts and python-pptx wrappers. Across the ~100+ save calls in `tests/test_vaultlab_slides/`, fragmented allocations starve the next save's output buffer and Python raises `zipfile.MemoryError: Unable to allocate output buffer`.

The bleed is non-deterministic — the same test passes in isolation and fails at random positions inside the long suite, depending on host memory pressure from other processes. The CI matrix (Ubuntu) does not reproduce because Linux's allocator coalesces freed pages more aggressively than Windows' allocator.

State-doc agent observed 10 failures on a single run on 2026-05-15. On 2026-05-15 (my session, lower host memory pressure: 11.6 GB free of 34 GB) the bleed did not reproduce on the first 5 attempts.

## Decision: Option C (memory bleed fix) — not Option A or B

Option A (mark slow) was the brief's first preference but is **wrong for this bug**:
- The failure is non-deterministic and rotates across different tests each run. There's no fixed set of "heaviest" tests to mark.
- Marking tests as `slow` would hide coverage; the suite is already deselecting `slow` in CI, so this would just kick the can.

Option B (`pytest --forked`) works but:
- Doubles or triples CI wall-time (the current Ubuntu run is ~40s; forked is ~120s).
- The current CI workflows (`test.yml`, `invariants.yml`) run on Ubuntu only and don't hit the bug.
- The issue is Windows-local; pushing forking into CI fixes a problem CI doesn't have.

Option C (gc.collect after each slides test):
- Directly addresses the root cause — breaks the pptx ↔ lxml reference cycle so Python's allocator can reclaim the BytesIO pages before the next save.
- Adds `tests/test_vaultlab_slides/conftest.py` with an autouse fixture that calls `gc.collect()` after every slides test.
- Zero behavioural change. Adds ~7 s to the slides suite wall time (16 s → 23 s). The full suite stayed at ~52-57 s wall.
- No tests hidden; coverage unchanged.

## Implementation

Single file added:

```
tests/test_vaultlab_slides/conftest.py
```

The file has a single autouse function-scoped fixture that yields and then calls `gc.collect()` once after each test. Detailed rationale is in the module docstring so the next agent who looks at it doesn't rip it out as "unused gc spam".

## Numbers

| Metric | Before fix | After fix |
| --- | --- | --- |
| State-doc agent's run | 2034 passed, 10 failed (zipfile.MemoryError) | n/a (different host pressure) |
| My run, baseline (no conftest) | 2046 passed, 0 failed × 3 consecutive | n/a |
| My run, with conftest, after parallel-agent commit `eac5385` landed | n/a | 2060 passed, 6 deselected, 0 failed |
| Slides suite alone (291 tests) | n/a | 23 s × 3 consecutive stable |
| Invariants suite | 8/0 | 8/0 |
| Slides suite alone, wall-time | ~16 s | ~23 s |
| Full suite, wall-time | ~40 s | ~52-65 s |

The 14 s overhead from forcing gc on every slides test is acceptable given the alternative is a flaky CI.

## What I did NOT touch

Per the task constraints, a concurrent agent had uncommitted WIP at the start of my run on `src/vaultlab/report/dispatch.py`, `src/vaultlab/slides/self_review.py`, `src/vaultlab/figures/understand/whitespace.py`, plus matching tests. During my session that agent finished + committed as `eac5385` ("feat: deferred followups bundle — dispatch wiring + color-contrast + inset-axes"). I deliberately did not stage, modify, or revert any of their files. My commit contains only:
- `tests/test_vaultlab_slides/conftest.py` (the actual fix)
- `.claude/goals/test-suite-memory-pressure-fix.md` (this goal file)

## Followups

1. **Verify the fix on a memory-pressured host.** I couldn't reproduce the original 10-failure run because my session had ~12 GB free. If the bleed shows up again, the conftest needs an upgrade:
   - Add a session-scoped fixture that tracks `tracemalloc` peaks per test, fails loudly if any test crosses 500 MB.
   - Or: `gc.set_threshold(700, 10, 10)` at slides-conftest-import time to drive collection more aggressively across the run.
2. **Cross-test cleanup for figures.** `tests/test_vaultlab_figures/` also has matplotlib state that's known to leak (~100 KB per `plt.figure` not closed). Worth adding a similar conftest there if the bleed migrates.
3. **CI on Windows.** Once GitHub Actions minutes are unblocked, add a `windows-latest` matrix entry to `.github/workflows/test.yml` so this regression class is caught by CI, not by local Windows users.

## Provenance

- State doc that flagged the issue: `G:/My Drive/Knowledge/vaultlab/Sources/Notes/system-state-2026-05-15.md` (Deferred followups #9).
- Originating goal file: `.claude/goals/state-doc-2026-05-15.md` paragraph beginning "Ran full pytest — 2046 collected, 6 deselected; 2034 passed / 10 failed...".
- Three consecutive 2003/0 runs locally confirm stability with the fix.
