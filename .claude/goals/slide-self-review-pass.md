# /goal: slide self-review pass — sub-goal 5.4 of north-star

_Created: 2026-05-15_
_Working dir: `C:/Users/bobby/Downloads/vaultlab`_

## CONTEXT

- **Sub-goal:** 5.4 of the north-star plan
- **Advances:** the slide pipeline's "ship-ready" gate — every rendered deck now has a single composite audit pass that catches layout regressions, missing titles, shape overlap, and structural arc errors without needing an LLM round-trip.
- **Starting state:**
  - `vaultlab.workflows.crosstalk.rigor_audit` exists for LLM-driven content audit but needs a runner_callback; nothing checks the RENDERED .pptx.
  - `vaultlab.slides.audit_html.build_audit_report_html` renders a rigor-audit result as an HTML report but had no producer that walked a real .pptx.
  - Lab template + layouts enforce hard rules at write time but a deck assembled outside `build_from_plan` (or post-edited) had no after-the-fact verifier.
- **Pre-existing audits reused:**
  - `vaultlab.slides.template.default_font()` → Roboto floor
  - `vaultlab.slides.template.min_sizes()` → 28 / 24 / 18 pt thresholds
  - `vaultlab.slides.audit_html.build_audit_report_html` → HTML rendering via a thin adapter

## SUCCESS CRITERIA

1. `vaultlab.slides.self_review.review_deck(pptx_path)` reads a rendered .pptx and returns a `ReviewReport`. ✅
2. The report aggregates `n_critical / n_warning / n_info`; `report.ok()` is true iff `n_critical == 0`. ✅
3. HTML rendering reuses `build_audit_report_html` via the `_to_audit_html_inputs` adapter. ✅
4. CLI: `vaultlab slides review <pptx> [--html <out>]` is wired through the root dispatcher. ✅
5. `write_review_report` emits `.provenance.json` + `.method.md` sidecars per the AGENTS.md Red Line #2 contract. ✅
6. Unit tests cover: known-good deck has zero criticals, an intentionally-tiny title triggers `min-title-font` critical, shape overlap triggers `no-shape-overlap` critical, a one-word title fires `descriptive-title` warning, HTML rendering produces non-empty output with sidecars. ✅
7. Existing slides test suite + invariants stay green. ✅

## PROGRESS

- `src/vaultlab/slides/self_review.py` (new, ~600 lines)
  - `SlideReview` + `ReviewReport` dataclasses with `n_critical / n_warning / n_info / ok()` aggregates
  - `review_deck(pptx_path)` — opens the .pptx via python-pptx, loops slides, runs every audit
  - Per-slide audits:
    - `_check_fonts_and_sizes` — Roboto floor + 28/24/18pt thresholds; ignores citation-source footnotes anchored in the bottom 12% of the slide
    - `_check_overlap` — pairwise EMU bbox overlap > 5M EMU² triggers `no-shape-overlap` critical
    - `_check_descriptive_title` — non-divider/non-reference slides with <3-word titles warn
    - `_check_bullet_density` — >7 body lines on text/figure/reference slides warn
    - `_check_figure_presence` — caption mentions figure but no picture shape → info
  - Story-arc structural audit (no LLM): empty deck (critical), title slide not at position 0 (critical), >5 section dividers (warning), references trailing slide (warning).
  - `_to_audit_html_inputs` — maps `ReviewReport` → `(plan, audit)` shape with severity mapping (`critical→blocker`, `warning→major`, `info→minor`).
  - `render_review_html` / `write_review_report` — HTML rendering + provenance sidecars.
- `src/vaultlab/slides/__init__.py` — re-exports the new public names (`ReviewReport`, `SlideReview`, `review_deck`, `write_review_report`).
- `src/vaultlab/cli/__init__.py` — added `_cmd_slides` + `_cmd_slides_review` dispatcher; updated usage banner. Exit code 2 when criticals are present.
- `tests/test_vaultlab_slides/test_self_review.py` (new, 11 tests)
  - Good-deck path: zero criticals, dataclass shape, summary lines
  - Critical path: tiny-title font, shape overlap
  - Warning path: one-word title
  - Story-arc path: empty deck
  - HTML: non-empty, contains issue name (uppercased per audit_html builder), sidecars written
  - Error path: missing pptx raises FileNotFoundError

## EVIDENCE

```
$ python -m pytest tests/test_vaultlab_slides/test_self_review.py -q
...........                                                              [100%]
11 passed in 1.08s

$ python -m pytest tests/test_vaultlab_slides/ tests/test_vaultlab_invariants/ -q
......                                                                   [100%]
294 passed in 18.57s   # 275 baseline + 8 invariants + 11 new = 294

$ python -m pytest tests/test_vaultlab_cli/ -q
............................                                             [100%]
28 passed in 1.59s
```

CLI smoke:

```
$ vaultlab slides review good.pptx --html review.html
vaultlab slides review — good.pptx
  Reviewed 4 slides from good.pptx.
  Findings: 0 critical, 1 warning, 0 info.
  Deck passed critical checks — see warnings for polish opportunities.
Issues:
  [WARNING] Slide 4 min-body-font: Body text is 18pt …
HTML report: review.html
(exit 0)
```

## DECISIONS / NOTES

- **Why deterministic checks, not `rigor_audit`?** Sub-goal 5.4 calls for a pass that runs on every render. `rigor_audit` requires a runner_callback (LLM invocation) so it can't ship as a default CI gate. The deterministic structural checks cover the load-bearing items from `feedback_slide_hard_rules.md` without needing network/keys. `rigor_audit` remains the LLM-tier content audit for `/build-deck`; self-review is the layout-tier gate that fires unconditionally.
- **Stable shape identity.** python-pptx wraps the underlying XML element in a fresh Python object on every `slide.shapes` access, so `id(shape)` is not stable across iterations. The code keys shapes by `id(shape._element)` via `_shape_key`. Multiple audits had to be refactored to share this resolver — see `_resolve_title_shape_key`.
- **Citation-source footnote allowance.** The lab template renders citation sources at 9pt anchored to the bottom 0.5in of the slide (`vaultlab.slides.layouts.figure.add_figure_slide`). Without an explicit allowance every figure slide would trip the `min-body-font` critical. `_is_footnote_shape` whitelists short single-line text in the bottom 12% of the canvas.
- **Title-slide classification.** Only the deck's FIRST slide can be classified as `"title"`; later slides with short titles stay tagged `"text"` so the descriptive-title audit fires on them.
- **Audit-html shape match.** Existing `build_audit_report_html` was kept as-is; the adapter materializes a thin deck plan from the rendered slides + a rigor-audit-shaped issue list so the renderer needed no changes.

## OPEN / DEFERRED

- Color-contrast audit: not wired (would need to read theme colors out of the master + measure WCAG ratios; out of scope for 5.4).
- Speaker-notes audit: not wired (deferred — `vaultlab.slides.notes.parse_speaker_notes` would give us the hook, but the rules around mental_map + 200-400 word script are still hand-checked).
- Animation audit: not wired (animations are XML-level; defensible to skip in v0.0.x).
