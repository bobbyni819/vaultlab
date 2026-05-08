---
name: init-kb
description: Scaffold a new project KB folder per the canonical schema. Creates Sources/Wiki/Output structure with START_HERE.md (with embedded LLM maintenance rules), _Index.md, _Catalog.md, _Log.md.
arguments: <project-slug-or-empty> [--domain=<extension-key>]
---

# /init-kb <project-slug>

> *"Set up a fresh KB folder for me — equities, metabolism, whatever."*

Invokes `vaultlab.kb.setup.scaffold_kb` to create the canonical 11-folder + 4-file structure (per `tools/knowledge-base-specification.md`). Drops the user into a working KB without having to remember where things go.

## Lineage

Lifts:
- `tools/knowledge-base-specification.md` schema (own work, 2026-04-10) — operationalized as code
- Karpathy LLM Wiki — wiki-grows-with-work + canonical-structure pattern
- Obsidian vault convention — folder structure
- conceptual-deep-dive-spec-roadmap-2026-05-08.md SPEC-D — design source

## What gets created

```
<kb-root>/<project-slug>/
    START_HERE.md       # daily brief w/ today's date + 7 maintenance rules embedded
    _Index.md           # master index (auto-regen stub)
    _Catalog.md         # source inventory (auto-regen stub)
    _Log.md             # chronological activity log + 1 setup entry
    Sources/
        Articles/       # paper summaries
        Papers/         # full-text PDFs
        Notes/          # analysis notes
        Assets/         # figures, images
    Wiki/
        Concepts/       # concept articles
        Methodology/    # pipeline docs
        Summaries/      # Tier-A paper summaries
    Output/
        Plans/          # action plans
        Drafts/         # PI messages, manuscript drafts
        Reports/        # audit + status reports
        Explorations/   # filed-back query results
```

Plus optional domain extensions (pass `--domain=equities`, `--domain=metabolism`, `--domain=spatial-omics`, etc.).

## Pre-flight checklist

1. Resolve KB root from config (or env var `VAULTLAB_KB_ROOT`)
2. Slugify the project name to kebab-case
3. Verify the target folder doesn't already exist (or use `--force`)

## Execution

### Step 1 — Confirm scaffold parameters

```python
from vaultlab.kb.setup import scaffold_kb
proj_dir = scaffold_kb(
    kb_root,
    project_slug,
    domain_extensions=["equities"],  # optional
    force=False,
)
```

### Step 2 — Surface what was created

Surface to user:
- Path to new project folder
- Path to START_HERE.md (open in Obsidian via pinned-vault URL)
- One-line summary of folders created
- Suggested next move: `/onboard-project` to capture origin/goals, or `/lit-arc <topic>` to populate Sources/

### Step 3 — Optional: seed with intake form

If user provides topic + goal as args, also run `/onboard-project` to populate `intake.md` automatically.

## What this is NOT

- Not a project-content scaffolder. Creates the structure, not the content.
- Not idempotent in destructive sense — refuses to overwrite existing folders by default. Pass `force=True` to fill in missing pieces.
- Not the same as `bobby-kb init` (which is the cross-machine config sync). Both can be run.

## See also

- `vaultlab/src/vaultlab/kb/setup.py` — implementation
- `tools/knowledge-base-specification.md` — the canonical schema this enforces
- `vaultlab/Sources/Notes/SPEC-kb-setup-as-primitive-2026-05-07.md` — full design SPEC
- `/audit-kb` — lint an existing KB against the schema
