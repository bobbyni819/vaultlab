# Goal — Slash commands for v0.0.5 primitives

## Status: SHIPPED 2026-05-15

## What

Expose every primitive that landed in v0.0.5 as a Claude Code slash
command at `.claude/commands/<name>.md`. The Python is callable today;
this goal closes the gap by wiring each entrypoint to a one-shot
slash-command UX.

## Commands

| Slash command | Primitive | New / audited |
|---|---|---|
| `/full-reader <paper-source>` | `vaultlab.research.full_reader.build_paper_reader` | **NEW** |
| `/run-analysis <project-dir>` | `vaultlab.analysis.run_pipeline` | **NEW** |
| `/polish <manuscript-path>` | `vaultlab.manuscript.polish.write_polish_report` | audited (already exists, added v0.0.5 writer call) |
| `/respond <reviewer-block>` | `vaultlab.manuscript.respond.write_response_letter` | audited (already exists, added v0.0.5 writer call) |
| `/das-audit <das-text>` | `vaultlab.manuscript.data_availability.write_data_availability_statement` | audited (already exists, added v0.0.5 writer call) |
| `/state-dashboard <state-md>` | `vaultlab.report.state_dashboard_html.write_state_dashboard_html` | **NEW** |
| `/review-deck <pptx-path>` | `vaultlab.slides.self_review.review_deck` + `write_review_report` | **NEW** |
| `/reorder-slides <plan>` | `vaultlab.report.editors.write_slide_reorder_editor` | already existed — no change needed |
| `/triage-citations <citations-json>` | `vaultlab.report.editors.write_citation_triage_editor` | **NEW** |

## Files

- `.claude/commands/full-reader.md` — new
- `.claude/commands/run-analysis.md` — new
- `.claude/commands/state-dashboard.md` — new
- `.claude/commands/review-deck.md` — new
- `.claude/commands/triage-citations.md` — new
- `.claude/commands/polish.md` — audited (added `write_polish_report`
  call alongside the existing per-rule pass)
- `.claude/commands/respond.md` — audited (added `write_response_letter`
  call so the .md write goes through the provenance-receipt path)
- `.claude/commands/das-audit.md` — audited (added
  `write_data_availability_statement` call alongside `audit_statement`)
- `.claude/commands/COMMANDS.md` — appended a "v0.0.5 primitives" section
  to the inventory

## Audit decisions

- **`/reorder-slides` was already complete** — it already calls
  `write_slide_reorder_editor`. Left untouched.
- **`/polish`, `/respond`, `/das-audit` already existed** — they used
  the underlying primitives (`audit_statement`, `render_response_letter`,
  `check_sentence_length`) but bypassed the v0.0.5 top-level
  `write_*` writers. Added the writer calls so every artifact gets
  Red Line #2 provenance sidecars by default.
- **No new commands were duplicated.** Each new file's name is unique
  among existing `.claude/commands/*.md`.

## Auto-doc mirror (per Bobby's CLAUDE.md rule)

Each new / updated command file is mirrored to
`G:/My Drive/Knowledge/claude-config/Sources/Commands/vaultlab/`. Index
refreshed via `bobby-kb index --kb claude-config` (best-effort).

## Test plan

- Each new command file is valid markdown with the canonical YAML
  frontmatter and matches the `.claude/commands/lit-arc.md` shape.
- Each command's Python implementation block imports a real primitive
  (verified by `grep`).
- `pytest tests/test_vaultlab_invariants/ -q` still passes 8/0
  (slash-command markdown isn't touched by the invariants suite, but
  this is the canonical green-light).
