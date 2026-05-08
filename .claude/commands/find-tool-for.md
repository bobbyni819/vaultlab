---
name: find-tool-for
description: Find a computational tool / Python or R package for a specific analysis task. Searches the curated 12-package registry + auto-discovered tools + external lab-collaborator repos. Returns ranked suggestions with install commands and use-case context.
arguments: <task-description>
---

# /find-tool-for <task-description>

> *"What's a good package for batch correction across patients?"*

Searches `vaultlab.kb.tools_index` (12 curated packages: scanpy, squidpy, anndata, scvi-tools, harmony, cellpose, scikit-image, scipy-stats, statsmodels, pingouin, pyimzml, palantir) plus any auto-discovered tools in `packages/discovered/` plus external lab-collaborator repos. Returns ranked suggestions with rationale.

## Lineage

Lifts:
- `vaultlab.kb.tools_index` curated registry (already shipped 2026-04-29)
- `vaultlab.kb.tools_index.discovery` auto-discovery (SPEC-O extension, shipped 2026-05-08)
- Tiered summary/deep-doc loading (per Bobby 2026-04-29 grill)
- OpenClaw "knowledge in instructions" — Claude reads tool docs at runtime; vaultlab provides the registry + retrieval

## Pre-flight checklist

1. Resolve KB root + project config (for project-specific data-format hints)
2. Load curated tools index via `load_index()`
3. Load discovered tools via `load_index()` (subdir `packages/discovered/`)
4. Load external repos via `load_external_repos()`

## Execution

### Step 1 — Topic match

```python
from vaultlab.kb.tools_index import suggest_for_topic
hits = suggest_for_topic(task_description)
```

This does keyword-overlap matching against each entry's `domains` + description. Returns ranked list of `ToolEntry`.

### Step 2 — Rank + filter

For each hit:
- Show one-paragraph summary (`summary_for(name)`)
- Show install command (`pip install ...` or `conda ...` or `BiocManager::install(...)`)
- Surface `domains` overlap with the task description
- Note status: `curated` / `discovered` / `external`

Top 3 hits surface inline; full list goes to a temporary scratch doc.

### Step 3 — Suggest install + adapter

If the user picks a tool, suggest:
- `/install-tool <name>` to verify install + pin version (if SPEC-O install primitive shipped)
- The relevant `vaultlab.tools.<name>` adapter if available
- Otherwise: read `deep_doc_for(name)` and let Claude figure out the call (OpenClaw fallback)

### Step 4 — When nothing matches

If `suggest_for_topic` returns empty:
- Suggest running a `/lit-arc <task-description>` to surface tool-introducing papers in the literature; auto-discovery via `vaultlab.kb.tools_index.discovery.extract_tool_metadata` will populate `packages/discovered/` for next time
- Surface external repos that match (lab collaborator hooks)

## What this is NOT

- Not a web search. Stays inside the registry; for new tools, suggest /lit-arc.
- Not an installer (yet). Returns the install command; user (or future SPEC-O install primitive) executes.
- Not a code-runner. Returns suggestions + docs; Claude assembles the actual call.

## See also

- `vaultlab/src/vaultlab/kb/tools_index/loader.py` — registry + tiered-search API
- `vaultlab/src/vaultlab/kb/tools_index/discovery.py` — auto-discovery from lit-arc (SPEC-O extension)
- `vaultlab/src/vaultlab/kb/tools_index/packages/` — 12 curated entries
- `vaultlab/src/vaultlab/kb/tools_index/external_repos.toml` — lab-collaborator hooks
- `vaultlab/Sources/Notes/spec-roadmap-2026-05-07.md` SPEC-O — full design
