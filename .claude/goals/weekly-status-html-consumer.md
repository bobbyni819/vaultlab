# Sub-goal 4.2 slice — Weekly Status HTML consumer (pattern #16)

## Status: SHIPPED

## What

Adds `vaultlab.report.weekly_status_html` as the 7th consumer of the
`vaultlab.report` primitive library. Implements Thariq Shihipar's HTML
pattern #16 ("Weekly Status"), identified in
`docs/html-pattern-coverage.md` as the top-fit pattern for biology
research workflows (Bobby writes a state doc every few days).

## Public API

- `WeeklyStatusReport` — dataclass (week_label, project, tldr, shipped,
  in_flight, blockers, carryover_next_week, metrics)
- `build_weekly_status_html(report) -> str` — composes existing
  primitives (`tldr_box`, `status_chip`, `severity_card`, `card_grid`,
  `section`) and wraps via `render_report`
- `write_weekly_status_html(report, output_path) -> Path` — writes the
  HTML and emits Red Line #2 provenance sidecars

## Files

- `src/vaultlab/report/weekly_status_html.py` (new, 234 LOC)
- `src/vaultlab/report/__init__.py` (added 3 exports)
- `tests/test_vaultlab_report/test_weekly_status_html.py` (new, 11 tests)

## Composition (matches existing consumers)

- Header band: `status_chip` row with project, week label, and
  shipped / in-flight / blocker counts (each chip colored by severity)
- TL;DR: `tldr_box(report.tldr)` — paragraph form, single string input
  branch of the primitive
- Metrics row: `card_grid` of `severity_card`s with the value in a
  large-font div as the body
- Shipped / In flight / Blockers: each is a `card_grid` of severity
  cards at the appropriate level (good / warn / bad). Sections omit
  themselves when empty.
- Carryover: simple `<ul>` styled with `--ink-soft`
- Wrap: `render_report` with eyebrow
  `"vaultlab · weekly status · <project>"`

## Provenance contract

Per AGENTS.md Red Line #2, `write_weekly_status_html` calls
`vaultlab.provenance.write_receipts` after writing the HTML. The record
is `kind="weekly_status_html"`, `generated_by="vaultlab.report.weekly_status_html"`,
and params capture project, week_label, and count of every list /
dict on the input. Provenance failure is logged but does not gate the
HTML write (mirrors `vaultlab.slides.deck` pattern).

## Tests (11/11 passing, all 70 report tests passing)

- minimal report returns non-empty HTML with project + week label
- minimal report contains TL;DR section
- full report contains shipped + in-flight + blocker text
- full report renders metrics (label + value)
- empty shipped list does not crash
- no metrics + no blockers still renders
- user text is HTML-escaped (XSS guard)
- write creates the output file
- write creates `.provenance.json` + `.method.md` sidecars with
  expected fields (generated_by, kind, params.project, params.week_label,
  params.shipped_count)
- write accepts a string path
- write creates parent directories

## Decisions

- **Did not add a dispatch.py kind** — instructions limit me to `report/`
  but adding a `weekly-status` `ArtifactKind` and detection rule would
  conflict with the parallel agent working on `report/dispatch`. Left
  as a follow-up; dispatch consumers detect on dict shape so the
  follow-up is mechanical.
- **TL;DR rendered as paragraph, not list** — `tldr_box` supports both
  via type-dispatch on the items arg; paragraph form is more natural
  for a one-paragraph weekly summary.
- **Metric cards reuse `severity_card`** rather than introducing a new
  "stat tile" primitive (per the "don't invent new primitives"
  constraint). The card title carries the metric name, body carries
  the value in a large-font div.
- **Empty sections omit themselves** — quiet weeks shouldn't render a
  page full of "(empty)" placeholders.

## Skipped

Nothing skipped — full scope delivered.

## Commit

To be added after `git commit`.
