# Sub-goal 5.2 — Four new slide-deck templates

## Status: SHIPPED

## What

Adds 4 new deck-composition recipes to `vaultlab.slides.templates`. Each
module exposes a single `build_*` function that returns a deck-plan dict
ready for `vaultlab.slides.build_from_plan`. Templates encode the section
order + layout choices for a specific use case so callers only have to
supply *content*, not slide-structure decisions.

| Template | Use case | Slide count | Time budget | Builder |
| --- | --- | --- | --- | --- |
| `investor_pitch` | VC / seed pitch for a research-tool startup | 10-12 | 10 min | `build_investor_pitch` |
| `lab_meeting` | Weekly lab-meeting progress update | 7-10 | 20-30 min incl. discussion | `build_lab_meeting` |
| `conference_talk` | Conference talk (motivation -> 4-6 results -> conclusions) | 12-15 | 12 min talk + 3 min Q&A | `build_conference_talk` |
| `journal_club` | Paper-discussion deck with strengths/limits per figure | 10-12 | 30 min incl. discussion | `build_journal_club` |

## Files

- `src/vaultlab/slides/templates/__init__.py` (new, package surface)
- `src/vaultlab/slides/templates/investor_pitch.py` (new)
- `src/vaultlab/slides/templates/lab_meeting.py` (new)
- `src/vaultlab/slides/templates/conference_talk.py` (new)
- `src/vaultlab/slides/templates/journal_club.py` (new)
- `tests/test_vaultlab_slides/templates/__init__.py` (new)
- `tests/test_vaultlab_slides/templates/test_investor_pitch.py` (new, 12 tests)
- `tests/test_vaultlab_slides/templates/test_lab_meeting.py` (new, 12 tests)
- `tests/test_vaultlab_slides/templates/test_conference_talk.py` (new, 11 tests)
- `tests/test_vaultlab_slides/templates/test_journal_club.py` (new, 16 tests)
- `src/vaultlab/slides/deck.py` (wired 4 new slide types into `build_from_plan`)

## Plumbing into `build_from_plan`

Sub-goal 5.3 added the layout primitives (`add_equation_slide`,
`add_table_slide`, `add_comparison_table_slide`,
`add_acknowledgments_grid_slide`) but did not wire them into the dict-plan
dispatcher in `vaultlab.slides.deck.build_from_plan`. This sub-goal
finishes that wiring by:

- Adding `"equation"`, `"table"`, `"comparison_table"`,
  `"acknowledgments_grid"` to `SUPPORTED_PLAN_SLIDE_TYPES`.
- Adding the matching `elif stype == "..."` branches to the dispatcher.
- Importing the four new primitives in the lazy-import block.

This means the new templates can emit those slide types directly without
the caller having to hand-render them. It is the minimum addition needed
to make the templates work end-to-end.

## Hard-rule conformance

Each template delegates layout to the existing imperative primitives in
`vaultlab.slides.layouts`, so the hard rules from
`feedback_slide_hard_rules.md` are honored by construction:

- **Roboto everywhere** — set by `template.load_template` + layouts.
- **Min sizes** — 28 pt (heading) / 24 pt (body) / 18 pt (caption), via
  `template.min_sizes()`.
- **Descriptive sentence titles** — each builder takes "headline" args
  rather than single-word labels, encouraging Bobby-style sentence titles
  ("Authors show that X reduces Y under Z").
- **No shape overlap** — inherited from the primitives, which already
  enforce it.

## Journal-club specifics

The `journal_club` builder follows
`feedback_journal_club_deck_practices.md`:

- Section order: title → why → lab → field → divider → figures (each with
  Strengths/Limits) → take-home quote → discussion prompts → references.
- `format_label_bullet(label, detail)` helper exposed for callers to keep
  bullets in parallel "LABEL — detail" style.
- `READ_FIRST_PATH = "READ_FIRST_journal_club.md"` constant documents the
  canonical companion-briefing filename so the convention survives a
  fresh session.

Distinct from `vaultlab.slides.journal_club_arcs` — that module is an
*arc-registry* (paper-type → slide-skeleton); this is a full deck
*builder* with Bobby's structured JC inputs.

## Investor-pitch specifics

- Optional sections (comparison, market, business model, team, roadmap)
  can be omitted by passing empty / default args — the deck still
  produces a valid plan.
- The ask slide is mandatory; the builder always emits it as the final
  slide.
- Team slide uses `acknowledgments_grid` for the auto-sized photo-grid
  feel that VC decks expect.

## Lab-meeting specifics

- Progress entries can be figure slides (with `image_path` + `caption` +
  `bullets`) OR text slides (when no figure yet).
- Raises `ValueError` if zero progress entries — a lab meeting with no
  progress is a meeting that should have been a Slack message.
- "Open questions for discussion" slide is the meeting's value driver and
  is always emitted.

## Conference-talk specifics

- Approach slide (methods at a glance) is mandatory and rendered as the
  first figure slide.
- Results entries (4-6 typically) are each one figure slide.
- Optional synthesis-figure slide for the take-home schematic.
- Acknowledgments + references slides are emitted only when their content
  is non-empty.

## Tests

- 51 new tests in `tests/test_vaultlab_slides/templates/` (all passing).
- Each test file covers: plan shape, slide-count band (± 2 of target),
  type validity (all types in `SUPPORTED_PLAN_SLIDE_TYPES`), critical
  section presence, end-to-end render via `build_from_plan`.
- Full slides suite: 275 passed (224 pre-existing + 51 new).
- Invariants suite: still 8/0.

## Sample inputs

Test fixtures use real research-tool conventions:

- **investor_pitch:** Multiplexed-imaging analysis platform (Manifold) —
  CODEX/IMC/MIBI pipelines, design partners at Hickey/Greenbaum/Pearce
  labs, $2.5M seed at $12M post.
- **lab_meeting:** Phospholipid programs in IBD — B12 donor CODEX QC,
  Schurch 2020 macrophage motif recapitulation, RUVg normalization.
- **conference_talk:** Panel-agnostic cell typing for ISMB — trained on
  4.2M cells from 17 atlases, zero-shot F1 = 0.88 to IMC.
- **journal_club:** Goltsev 2018 Cell paper (CODEX foundational paper) —
  panel breadth, neighborhood definitions, lupus tonsils.

## Verify

```bash
pytest tests/test_vaultlab_slides/ -q  # 275 passed
pytest tests/test_vaultlab_invariants/ -q  # 8 passed
```
