# Goal: README refresh for v0.0.5 release

**Date:** 2026-05-15
**Status:** complete
**Driver:** Bobby (autonomous task to Claude)

## Why

v0.0.5 shipped on 2026-05-15 (commit `246635d`, tag `v0.0.5`) bundling
19 of 20 north-star plan sub-goals and the previously-in-flight v0.0.4
HTML/manuscript/nature-skills work. The README needed a current-state
sweep so first-time visitors land on v0.0.5 framing, not stale
"v0.0.4 in flight" language.

## What changed

1. **Added a "What's new in v0.0.5 (2026-05-15)" block** between the
   "First run" section (sub-goal 1.4, preserved) and the "About" prose.
   Seven highlight bullets covering:
   - 4 red lines mechanically enforced (CI invariant suite)
   - `vaultlab demo` single-command artifact
   - All 7 nature-skills absorbed (`full_reader` final piece)
   - 6 new SPEC executions
   - HTML coverage 12/20 patterns now consumed
   - 4 deck templates + 4 new layouts
   - GitHub Discussions live
   Footer link to `CHANGELOG.md`.
2. **Updated the Claude-Code bootstrap Quickstart** (step 1) to prefer
   `pip install vaultlab` from PyPI, with clone+editable as the fallback
   dev install path.
3. **Added a "Simpler install (recommended as of v0.0.5)"** subsection
   in the "Get started — inside Claude Code" block. Three-line install
   path: `pip install vaultlab` → `vaultlab demo` → `vaultlab init` →
   `claude`. Retained the editable-install block for contributors.

## What did NOT change

- The "First run — produce a real artifact in under 5 minutes" block
  written by another agent (sub-goal 1.4) — preserved as-is.
- No stale `v0.0.4` / `v0.0.3` text was found in README.md to delete;
  only `## Specialty module (in progress)` which is a status note not
  a version reference.
- No links were broken or rerouted — every GitHub link still resolves
  to `bobbyni819/vaultlab` and every PyPI link to `vaultlab`.

## Constraints honored

- Only README.md + this goal doc touched.
- No emojis added (matched existing README style).
- Did not touch `.github/workflows/test.yml` or `vaultlab.report.dispatch`
  (other agents own those).
- Did not modify CHANGELOG.md — `[Unreleased]` heading is correct per
  Keep-A-Changelog convention; the v0.0.5 section below it is the
  published release notes.

## Commit

`docs(readme): refresh for v0.0.5 release` on `main`, pushed to
`origin/main`. Hook output verified clean.
