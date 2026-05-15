# /goal: implement top-5 unimplemented HTML patterns (sub-goal 4.2)

_Created: 2026-05-15_
_Completed: 2026-05-15_
_Working dir: `C:/Users/bobby/Downloads/vaultlab`_

## CONTEXT

- **Sub-goal:** 4.2 of the north-star plan
- **Predecessor:** sub-goal 4.1 (`html-pattern-coverage-audit.md`, commit `b4b3ca4`) flagged the top-5 highest-fit unimplemented patterns: #16 Weekly Status, #15 Concept Explainer, #6 Module Map, #19 Feature Flag Editor, #1 Three Code Approaches.
- **Already shipped slice:** pattern #16 (`weekly_status_html.py`, commit `6bd6dc6`).
- **Audit recommendation:** ship #16 + #6 + #15 as ONE composite "state-dashboard" consumer; ship #19 and #1 as standalone consumers.

## SUCCESS CRITERIA

1. `src/vaultlab/report/state_dashboard_html.py` composite consumer renders patterns #16 + #6 + #15. ✅
2. `src/vaultlab/report/feature_flag_editor.py` renders pattern #19 with two-way toggle UI + Copy diff. ✅
3. `src/vaultlab/report/approaches_compare_html.py` renders pattern #1 with 2-up `compare_panel` and N-up `card_grid` paths. ✅
4. Each consumer writes provenance sidecars per AGENTS.md Red Line #2. ✅
5. Tests cover minimal + full state, escaping, sidecar presence (5-7 per consumer). ✅
6. `docs/html-pattern-coverage.md` updated: patterns #1, #6, #15, #19 flipped to ✅; summary count bumped. ✅
7. Doc mirrored to `G:/My Drive/Knowledge/vaultlab/Sources/Notes/html-pattern-coverage-2026-05-15.md`. ✅
8. No regressions: `tests/test_vaultlab_report/` + `tests/test_vaultlab_invariants/` stay green. ✅

## PROGRESS

- Read 3 existing consumers for convention reference: `slides/audit_html.py`, `report/weekly_status_html.py`, `report/editors.py`. ✅
- Authored `state_dashboard_html.py` — composes `tldr_box` + `status_chip` band + metric `card_grid` + shipped/in-flight/blockers `card_grid` of `severity_card` + `svg_arg_graph` module map (ring layout) + module legend `card_grid` + optional concept explainer panel (Pattern #15). ✅
- Authored `feature_flag_editor.py` — grouped toggle cards (`severity_card` neutral + `<input type="checkbox">` rows) with `data-group` / `data-flag` attributes; Copy defaults / Copy current / Copy diff buttons; inline JS walks `.vl-flag` checkboxes to build the diff payload. ✅
- Authored `approaches_compare_html.py` — branches at N: 2 approaches → `compare_panel`, 3+ → `card_grid` of `severity_card`s with RECOMMENDED chip; pros/cons rendered as labeled bullet blocks with `good`/`bad` accents. ✅
- Updated `src/vaultlab/report/__init__.py` to export 9 new symbols (3 dataclasses + 3 builders + 3 writers). ✅
- Wrote 12 tests in `test_state_dashboard_html.py` (minimal, full, module-map SVG, concept explainer present/absent, escaping, write+sidecar, string path, parent dirs). ✅
- Wrote 7 tests in `test_feature_flag_editor.py` (minimal, toggle count, copy buttons, defaults embedded, escaping, write+sidecar). ✅
- Wrote 7 tests in `test_approaches_compare_html.py` (2-up compare panel, 3-up card grid + RECOMMENDED, context+rationale, zero handled, escaping, write+sidecar). ✅
- Updated `docs/html-pattern-coverage.md`: #1, #6, #15, #16, #19 → ✅; summary bumped to **12 implemented / 8 partial / 0 missing**. ✅
- Mirrored doc to KB. ✅

## EVIDENCE

- ✅ Criterion #1: `src/vaultlab/report/state_dashboard_html.py` ~330 LOC; composes 3 patterns into one consumer per audit's recommendation.
- ✅ Criterion #2: `src/vaultlab/report/feature_flag_editor.py` ~230 LOC; grouped toggles, three copy buttons, embedded JS for diff computation.
- ✅ Criterion #3: `src/vaultlab/report/approaches_compare_html.py` ~260 LOC; both rendering paths covered by tests.
- ✅ Criterion #4: each consumer's `write_*` function calls `vaultlab.provenance.write_receipts` with `kind="state_dashboard_html" / "feature_flag_editor" / "approaches_compare"`. Best-effort: HTML write never blocks on sidecar failure (mirrors `weekly_status_html` pattern).
- ✅ Criterion #5: 12 + 7 + 7 = 26 new tests; all pass.
- ✅ Criterion #6+7: doc edits land in both `docs/` and KB mirror.
- ✅ Criterion #8: `pytest tests/test_vaultlab_report/ tests/test_vaultlab_invariants/` → 104 passed (was 79 baseline; +25 new tests, +1 from elsewhere).

### Decisions made

- **Imported `_components` and `vaultlab.report.html.render_report` directly** instead of `from vaultlab.report import ...`. Reason: importing from the package while the package's `__init__.py` is still loading causes `ImportError` (partial init). The existing `weekly_status_html.py` works because `render_report` happens to be re-exported *before* it in the import order — but that's fragile. Going directly through the submodule is the robust pattern.
- **Composite consumer chose ring layout for `svg_arg_graph` module map.** Two reasons: (a) no module-relationship metadata to drive a force-directed layout; (b) ring layout gives readable spacing for the typical 5-20 module count. Edges are pruned to declared modules so an unknown downstream silently drops out (additive-state-aware feedback rule).
- **`feature_flag_editor` Copy-current and Copy-diff buttons use inline `<script>`** instead of leaning on the global `JS` bundle. The toggle-walking + diff-vs-defaults logic is specific to this consumer and only fires on user click, so inlining it keeps the wiring local to the file that needs it.
- **`approaches_compare_html` branches on N rather than always using `card_grid`.** With N=2, `compare_panel` is visually punchier (true side-by-side rather than a 2-column grid that wraps below ~600px). Three or more always uses `card_grid` because `compare_panel` is hard-wired to 2 panes.
- **Did NOT modify existing consumers (`weekly_status_html.py`, `editors.py`, `audit_html.py`)** even though pattern #16's row got updated in the coverage doc. The change is documentation only — the implementation was untouched from commit `6bd6dc6`.
- **Did NOT add new primitives to `_components.py`** — per the task constraint and the audit's "we have the LEGO bricks" finding.

### Known limitations / followups

- The `state_dashboard_html` consumer takes a `StateDashboard` dataclass directly — it does NOT yet parse `system-state-<date>.md` markdown. That parser belongs to a follow-up sub-goal that adds a `/state-html` slash command (estimated: one short session). The dataclass API is the stable contract; the parser is a transformation layer.
- `feature_flag_editor` only handles boolean flags. Pattern #19 in Thariq's gallery includes numeric sliders + dropdowns; those can layer on later via the same dataclass extension pattern (e.g. `FlagGroup.numerics: list[...]`).
- `approaches_compare_html` does not yet have a "trade-off matrix" mode (cross-tabulating approaches against 5 criteria). That's a natural extension once we have a SPEC doc using this output in anger.

### Tests after

- `tests/test_vaultlab_report/` — 96 passed (was 71 before this slice; +25 new).
- `tests/test_vaultlab_invariants/` — 8 passed (no regressions).
- Combined: 104 / 104.
