---
name: audit-kb
description: Lint a KB project folder against the canonical schema. Surfaces missing folders, orphan files, stale indexes, naming-convention violations, missing top-level files. Severity-ranked report (fail / warn / info) with concrete fixes.
arguments: <project-slug>
---

# /audit-kb <project-slug>

> *"Check whether the metabolism KB is still healthy."*

Invokes `vaultlab.kb.setup.lint_kb` to audit a project folder against the canonical schema (`tools/knowledge-base-specification.md`). Returns a structured report saved to the project's `Output/Reports/` directory.

## Lineage

Lifts:
- `vaultlab.kb.setup.lint_kb` (SPEC-D, shipped 2026-05-08)
- Severity rubric — scientific peer-review convention (fail / warn / info)
- Schema enforcement pattern — k8s admission controllers (validating webhook style)

## What gets checked

### Severity: fail (blocks ship)
- Project folder missing
- `START_HERE.md` missing (this is the daily-brief landing page; required)

### Severity: warn (degraded but usable)
- Required canonical folders missing (Sources/Articles, Wiki/Concepts, etc.)
- `_Index.md`, `_Catalog.md`, `_Log.md` missing
- `_Index.md` more than 7 days older than the latest source-folder mtime (stale)

### Severity: info (cosmetic)
- Article filenames not matching `AuthorYear_short-title.md` convention
- Orphan files outside canonical folders

## Pre-flight checklist

1. Resolve KB root + project slug
2. Verify project folder exists (otherwise audit will return a `fail` finding immediately)

## Execution

### Step 1 — Run lint

```python
from vaultlab.kb.setup import lint_kb
report = lint_kb(kb_root, project_slug)
```

### Step 2 — Save the report

Write `report.render_markdown()` to:

```
<kb_root>/<project-slug>/Output/Reports/kb-lint-<date>.md
```

Per the audit-trail-by-default convention.

### Step 3 — Surface verdict inline

Surface to user:
- Verdict: **shippable** (no fails) / **BLOCKED** (has fails)
- Summary counts (X fail / Y warn / Z info)
- Top 3 findings by severity
- Path to the full report

### Step 4 — Suggested fixes

For each fail/warn finding, the report includes a concrete fix instruction. Surface the top 3 inline:
- *"Top fix 1: re-scaffold via `vaultlab.kb.setup.scaffold_kb('<slug>', force=True)` to fill in missing folders"*
- *"Top fix 2: run a /lit-arc to refresh stale index"*

## Batch mode

To audit all KBs in the root, loop:

```python
for project_dir in (kb_root).iterdir():
    if project_dir.is_dir() and not project_dir.name.startswith("_"):
        report = lint_kb(kb_root, project_dir.name)
        # Aggregate
```

## What this is NOT

- Not a content audit. Checks structure, not whether the docs are good.
- Not a frontmatter audit (that's SPEC-C — frontmatter discipline + indexes). When SPEC-C ships, this command will gain a frontmatter check.
- Not destructive. Read-only; never modifies files.

## See also

- `vaultlab/src/vaultlab/kb/setup.py` — implementation
- `tools/knowledge-base-specification.md` — the schema being enforced
- `vaultlab/Sources/Notes/SPEC-kb-setup-as-primitive-2026-05-07.md` — full SPEC
- `/init-kb` — scaffold a fresh KB
