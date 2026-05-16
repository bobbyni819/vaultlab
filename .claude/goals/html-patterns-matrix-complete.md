# /goal: close the HTML pattern matrix — last 3 in-scope consumers (#2, #8, #11)

_Created: 2026-05-15_
_Working dir: `C:/Users/bobby/Downloads/vaultlab`_

## CONTEXT

- **Predecessors:**
  - sub-goal 4.1 — audit (`html-patterns-coverage-audit.md`)
  - sub-goal 4.2 — top-4 batch (commits `6bd6dc6`, `fbfbb8f`): patterns #1, #6, #15, #16, #19.
  - sub-goal 4.3 — SKILL.md catalog (commit `7ef2714`).
  - sub-goal 4.4 — second batch (`html-patterns-pr-flowchart-incident.md`): patterns #5, #12, #17.
- **Audit state at start of this goal:** 15 implemented / 5 partial / 0 missing.
- **Remaining 🟡 patterns:** #2, #7, #8, #9, #11. Audit out-of-scope: #7, #9.
- **Target slice:** ship the three in-scope remaining 🟡 patterns — #2 Visual Design Directions, #8 Component Variants, #11 SVG Figure Sheet.

## SUCCESS CRITERIA

1. `src/vaultlab/report/visual_designs_html.py` renders Pattern #2 — palette + layout swatches rendered side-by-side via `card_grid` + inline SVG.
2. `src/vaultlab/report/component_variants_html.py` renders Pattern #8 — contact-sheet of slide layouts / report primitives via `card_grid` (dense mode), grouped by first tag.
3. `src/vaultlab/report/svg_figure_sheet_html.py` renders Pattern #11 — standalone schematic library, each block with copy-SVG button + related-concepts chips.
4. Each `write_*` calls `vaultlab.provenance.write_receipts` per Red Line #2 (`kind="visual_designs_html"` / `"component_variants_html"` / `"svg_figure_sheet_html"`).
5. `vaultlab.report.dispatch._detect_kind` routes the three new dataclasses + dict shapes; `render_artifact_html` has render branches for all three.
6. `vaultlab.report.__init__` exports the 3 dataclass families + 6 builder/writer functions and adds them to `__all__`.
7. Tests cover minimal + full input, escaping, sidecar presence, and dispatch routing per consumer. Test files:
   - `tests/test_vaultlab_report/test_visual_designs_html.py`
   - `tests/test_vaultlab_report/test_component_variants_html.py`
   - `tests/test_vaultlab_report/test_svg_figure_sheet_html.py`
8. `docs/html-pattern-coverage.md` updated — #2, #8, #11 flipped to ✅; #7, #9 marked ⛔ (out-of-scope); summary count → 18 implemented / 0 partial / 2 out-of-scope.
9. Coverage doc mirrored to `G:/My Drive/Knowledge/vaultlab/Sources/Notes/html-pattern-coverage-2026-05-15.md`.
10. No regressions: `tests/test_vaultlab_report/` and `tests/test_vaultlab_invariants/` stay green.

## DECISIONS

- Match `weekly_status_html.py` / `flowchart_html.py` / `incident_timeline_html.py` shape exactly: dataclass + `build_*_html(...)` returning a self-contained HTML string + `write_*_html(...)` writing receipts via best-effort `try/except`.
- Import primitives via `from vaultlab.report import _components as c` and `from vaultlab.report.html import render_report` (avoids the partial-init footgun documented in predecessor goals).
- **No new primitives.** Every visual element comes from `_components` (`severity_card`, `card_grid`, `tldr_box`, `status_chip`, `section`) plus the trusted-HTML escape hatch for inline SVG.
- **Visual designs (#2):**
  - Each `DesignOption.swatch_colors` auto-renders as an inline SVG strip; we don't ask callers to hand-roll SVG when they just want a palette.
  - `inline_svg_preview` is treated as trusted HTML (it's a tiny SVG the caller built; escaping it would defeat the point of the preview).
  - Colour values are run through a conservative regex to keep them out of attribute-injection paths; invalid values fall back to `#cccccc`.
- **Component variants (#8):**
  - `group_by_tag=True` by default — multi-axis inventories (theme × layout × state) only stay scannable when grouped. The first tag drives the bucket; variants with no tag bucket under `"untagged"`.
  - `preview_html` is trusted HTML (same rationale as the design preview).
- **SVG figure sheet (#11):**
  - Reuses `severity_card`'s built-in `data-copy` click handler for the copy-SVG button — no new JS.
  - Each schematic block is rendered as a framed `<article>`, not as a card, because the SVG is the headline content and cards add too much chrome.
- **Dispatch detection:**
  - Dataclass-instance routes by `isinstance`. Dict-shape routes by `(title + options + no slides)`, `(title + variants)`, `(title + schematics)`.
  - The `not has("slides")` guard on visual-designs is intentional symmetry with the existing `feature-flag-editor` guard — keeps deck plans from accidentally matching.

## VERIFICATION RESULTS

Tests: 178 passed in 2.41s (137 baseline + 33 new + 8 invariants).

- `test_visual_designs_html.py` — 11 tests
- `test_component_variants_html.py` — 11 tests
- `test_svg_figure_sheet_html.py` — 11 tests
- All other `tests/test_vaultlab_report/` tests still pass.
- `tests/test_vaultlab_invariants/` — 8/0 (no regression).

## OUT OF SCOPE FOR THIS GOAL

- **#7 Living Design System** — vaultlab has 2 palettes total. Building a token-swatch HTML for that handful of tokens would not earn its keep. Documented as ⛔ in the coverage table.
- **#9 Animation Sandbox** — annotation timing is not a user-tunable parameter per Bobby's slide hard rules ("default annotation timing should just work"). Documented as ⛔ in the coverage table.
- **Wiring a real consumer to `vaultlab.figures.contract_html`** — the figure-contract draft mode hasn't been built yet; this goal ships only the renderer, leaving the integration to a future sub-goal.
- **SKILL.md catalog refresh** — the pattern catalog already references these as candidate consumers. A future light-touch pass can move them from "candidate" to "shipping" in the catalog narrative.
