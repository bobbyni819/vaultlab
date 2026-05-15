# Sub-goal 5.3 — Four new slide layouts

## Status: SHIPPED

## What

Adds 4 new imperative slide-layout primitives to `vaultlab.slides.layouts`,
following the lifted-primitive convention established in 2026-04 (the
`add_*_slide(pres, ...)` family in `figure.py`, `text.py`, `title.py`,
`multi_figure.py`, `references.py`, `section_divider.py`).

| Layout | Purpose | Module |
| --- | --- | --- |
| `add_equation_slide` | Centered equation, descriptive title, optional caption — math-heavy lab meetings | `equation.py` |
| `add_table_slide` | Styled rows-and-columns (list-of-rows or DataFrame) with header fill, alternating shading, >10-row "see appendix" fallback — experimental conditions / comparison data | `table.py` |
| `add_comparison_table_slide` | Two-column bullets with bold headers and optional "key insight" callout — journal-club A/B trade-off discussions | `comparison_table.py` |
| `add_acknowledgments_grid_slide` | Auto-sized contributor grid `(name, role, affiliation)` — closing slide of any deck | `acknowledgments_grid.py` |

## Files

- `src/vaultlab/slides/layouts/equation.py` (new, 107 LOC)
- `src/vaultlab/slides/layouts/table.py` (new, 168 LOC)
- `src/vaultlab/slides/layouts/comparison_table.py` (new, 178 LOC)
- `src/vaultlab/slides/layouts/acknowledgments_grid.py` (new, 160 LOC)
- `src/vaultlab/slides/layouts/__init__.py` (added 4 imports + 4 exports)
- `tests/test_vaultlab_slides/test_layouts_new.py` (new, 21 tests)

## Hard-rule conformance

All four layouts honor the vaultlab non-negotiable slide rules:

- **Font:** Roboto everywhere (via `_helpers.apply_font`)
- **Min sizes:** heading 28pt, body 24pt, caption 18pt — sourced from
  `template.min_sizes()` so any future tweak propagates
- **Equation slide** uses 44pt for the equation block (well above min)
- **Table body cells** use the caption-min 18pt; **headers** use body 24pt bold
- **Comparison bullets** use 18pt; **column headers** use 24pt bold;
  **key insight callout** uses 24pt bold
- **Acknowledgments grid** auto-shrinks name/role sizes only down to the 18pt
  caption floor (never below), with adaptive density:
  - ≤4 people: 24pt name / 18pt sub
  - 5-9 people: 20pt name / 18pt sub
  - ≥10 people: 18pt / 18pt
- **No shape overlap** — verified by `_no_significant_overlap` test helper
  using EMU bounding-box intersection (tolerance 9144 EMU ≈ 0.01")

## Tests (21 new)

1. `TestAddEquationSlide` × 5: returns slide, renders title+equation+caption,
   uses Roboto, no overlap, optional caption.
2. `TestAddTableSlide` × 5: basic rows, header bold styling, >10-row appendix
   fallback, Roboto + min sizes, empty rows.
3. `TestAddComparisonTableSlide` × 4: basic two columns, key insight callout,
   Roboto + min sizes, no overlap.
4. `TestAddAcknowledgmentsGridSlide` × 6: basic, optional role/affiliation,
   Roboto + min sizes, empty, large 12-person grid, no overlap.
5. `TestFullDeck.test_compose_all_four`: builds one deck using all four
   layouts and round-trips through `.pptx`.

Each test renders to a tmp_path .pptx, reloads via `python-pptx`, and asserts
on the reloaded artifact (not just the in-memory `Presentation`).

## Decisions

- **No audit module changes.** The task description mentioned
  `src/vaultlab/slides/audit.py` and `verify_slide_layouts`; neither
  exists. The closest gate is `slides/deck.py::SUPPORTED_LAYOUTS`, which
  guards the *declarative* `Slide` dataclass (title /
  `content_with_bullets` / `figure_with_caption`). The lifted-primitive
  family deliberately bypasses that gate (see the module docstring of
  `layouts/__init__.py`: "Both layers coexist"). New imperative
  primitives are simply re-exported from `__init__.py`, matching the
  pattern used for `add_text_slide`, `add_figure_slide`, etc.
- **Tables use python-pptx native tables.** Not a textbox-grid: that
  loses sortability and accessibility when the .pptx is reopened. The
  table API supports per-cell fills, so alternating shading + teal
  header fill come for free.
- **Equation rendering = plain text at 44pt.** No LaTeX-to-image pipeline.
  Callers who need pixel-perfect TeX should render their own image
  (matplotlib or external) and pass to `add_figure_only_slide`. Documented
  in the equation-slide docstring.
- **Acknowledgments grid uses a 4-column-max ceiling.** For >12 people the
  grid spills to multiple rows of 4 — keeps each cell wide enough for an
  18pt name + role + affiliation without truncation.

## Verify

```bash
cd C:/Users/bobby/Downloads/vaultlab
python -m pytest tests/test_vaultlab_slides/ -q
# 223 passed (was 202; +21 new)

python -m pytest tests/ -q
# 1811 passed (full suite green)
```
