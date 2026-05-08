---
name: publication-guideline-audit
description: Audit a rendered figure (PNG, PDF, EPS) deterministically against the project's target journal publication guidelines — DPI, font sizes, color count, palette accessibility, panel labeling, axis treatments, RGB color space. Outputs structured per-check pass/warn/fail report with concrete fixes.
arguments: <figure-path>
---

# /publication-guideline-audit <figure-path>

> *"Will this figure pass Cell Systems' figure submission guidelines?"*

Invokes the `publication_guideline_compliance` role on a single rendered figure. Runs deterministic checks against the journal's enforceable publication rules from `vaultlab/data/journal_guidelines/<journal>.yaml`. Mechanical, not aesthetic.

## Lineage

Lifts:
- **publication_guideline_compliance role** from `vaultlab.roles.publication_guideline_compliance` (own work)
- **Cell Press figure guidelines** (DPI 300/500/1000; font 6-8pt; Avenir/Arial; uppercase A/B panel labels)
- **Nature figure preparation guide** (DPI 300+; font 5-7pt; Helvetica/Arial; lowercase a/b panel labels)
- **Wong 2011 Nat Methods** (color blindness — Okabe-Ito categorical palette)
- **Crameri 2024 Curr Protocols** (palette accessibility — viridis sequential)
- **Nine-check layout audit** from `vaultlab.figures.understand.layout_checks` (own work, runs before this role)

## Pre-flight checklist

1. Resolve KB root + project config; verify `target_journal` is set
2. Verify the figure file exists + is readable
3. Load `vaultlab/data/journal_guidelines/<target-journal>.yaml` (or `cell.yaml` for any cell-family target) + `_common.yaml`
4. Optionally load the figure's `.provenance.json` sidecar if it exists (recipe metadata, palette, etc.)

## Execution

### Step 1 — Run pixel-level layout audit first

Before invoking the role, run `vaultlab.figures.understand.layout_checks.run_layout_audit(figure_path)` for the deterministic 9-check pass (title cutoff, axis label cutoff, legend overlap, etc.). This is the existing layout audit pipeline; no LLM needed.

### Step 2 — Invoke the role for guideline-specific compliance

Invoke `publication_guideline_compliance` role with:
- The figure file
- The journal yaml content
- The provenance receipt (if available)
- The layout audit results from Step 1

The role applies 9 deterministic checks (fig_dpi, fig_font_min, fig_color_blind_safe, fig_color_count, fig_panel_label_convention, fig_axis_treatment, fig_color_space, fig_text_on_background, fig_palette_avoidance) and outputs per-check JSON.

### Step 3 — Save + surface

Write to `Output/Reports/publication-guideline-audit-<figure-slug>-<date>.md` (JSON + markdown rendering).

Surface to the user:
- The verdict (ship / ship_with_revisions / needs_minor_revision / fail)
- Per-check pass/warn/fail summary table
- The journal yaml the audit was anchored against
- Path to full audit doc

### Step 4 — Re-render hint when fails

For each `fail` check, surface a concrete re-render parameter to fix it: *"DPI under threshold (240 < 300 minimum). Re-render with `dpi=300` in matplotlib's `savefig`."* The figure renderer (or user) applies the fix.

## Batch mode

If multiple figures need audit (e.g., all 6 figures in a deck), invoke per-figure and aggregate. Each gets its own audit doc; the aggregate verdict is the worst per-figure verdict.

## What this is NOT

- Not aesthetic judgment. Mechanical rules only.
- Not a content-level figure read (use `figure_reader` role for "what does this figure actually show?").
- Not a layout audit (that's Step 1, runs first; deterministic, not LLM).

## See also

- `vaultlab/src/vaultlab/roles/publication_guideline_compliance/{prompt.md,metadata.yaml}`
- `vaultlab/data/journal_guidelines/{cell,nature,elife,biorxiv,_common}.yaml`
- `External/journal-guidelines/{cell-press,nature,elife,accessibility-and-color}.md`
- `vaultlab/src/vaultlab/figures/understand/layout_checks.py`
- `vaultlab/Sources/Notes/SPEC-meta-agent-roles-2026-05-07.md`
