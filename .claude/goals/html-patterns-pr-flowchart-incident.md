# /goal: 3 more HTML pattern consumers — PR writeup, flowchart, incident timeline

_Created: 2026-05-15_
_Working dir: `C:/Users/bobby/Downloads/vaultlab`_

## CONTEXT

- **Predecessors:** sub-goal 4.2 (commits `6bd6dc6`, `fbfbb8f`) shipped 4 of the top-5 HTML patterns: #1, #6, #15, #16, #19. Sub-goal 4.3 (commit `7ef2714`) shipped the SKILL.md catalog.
- **Audit state at start of this goal:** 12 implemented / 8 partial / 0 missing (per `docs/html-pattern-coverage.md`).
- **Remaining 🟡 patterns:** #2, #5, #7, #8, #9, #11, #12, #17. Audit out-of-scope: #7, #9. Less core: #2 (visual-design), #8 (component variants).
- **Target slice:** ship the three highest-fit remaining 🟡 patterns — #5 PR Writeup, #12 Annotated Flowchart, #17 Incident Timeline.

## SUCCESS CRITERIA

1. `src/vaultlab/report/pr_writeup_html.py` renders Pattern #5 — file-by-file navigation + before/after diffs + commit log. Uses `matrix_table` + `compare_panel` + `tldr_box`.
2. `src/vaultlab/report/flowchart_html.py` renders Pattern #12 — clickable steps + expandable timing/failure paths. Uses `svg_arg_graph` + `collapsible_step`.
3. `src/vaultlab/report/incident_timeline_html.py` renders Pattern #17 — minute-by-minute timeline + log excerpts + followup checklist. Uses `timeline` + `tabbed_block`.
4. Each `write_*` calls `vaultlab.provenance.write_receipts` per Red Line #2 (`kind="pr_writeup_html"` / `"flowchart_html"` / `"incident_timeline_html"`).
5. Tests cover minimal + full input, escaping, sidecar presence, and edge cases (empty lists, no breaking changes, no log excerpts).
6. `docs/html-pattern-coverage.md` updated — #5, #12, #17 flipped to ✅; summary count → 15 implemented / 5 partial.
7. Doc mirrored to `G:/My Drive/Knowledge/vaultlab/Sources/Notes/html-pattern-coverage-2026-05-15.md`.
8. No regressions: `tests/test_vaultlab_report/` + `tests/test_vaultlab_invariants/` stay green.

## DECISIONS

- Match `weekly_status_html.py` / `state_dashboard_html.py` shape exactly: dataclass + `build_*_html(...)` returning a self-contained HTML string + `write_*_html(...)` writing receipts via best-effort try/except.
- Import primitives via `from vaultlab.report import _components as c` and `from vaultlab.report.html import render_report` (avoids the partial-init footgun documented in the predecessor goal).
- No new primitives — every visual element comes from `_components`.
- PR Writeup uses `matrix_table` for the per-file change table and `compare_panel` for at-most-one "before/after" highlight pair (e.g. test counts). The full diff stays out of scope — the consumer surfaces summary lines, not patch contents.
- Flowchart lays out steps with a simple left-to-right rank layout (Sugiyama-lite). Successors that don't resolve are silently dropped (additive-state-aware feedback rule).
- Incident timeline maps severity → status chip colours (`info`=neutral, `warning`=warn, `error`=bad, `resolution`=good). The log-excerpt tab is only rendered when at least one entry has a non-empty `log_excerpt`.
