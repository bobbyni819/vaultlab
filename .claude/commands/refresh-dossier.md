---
name: refresh-dossier
description: Compile a fresh Project Dossier — the standing mental model of an entire project (origin, current state, methodology commitments, established findings, frontier questions, literature backdrop, cross-project connections, anticipated PI/advisor questions, recent rolling tail). Auto-loaded by every primitive as Layer 0 context.
arguments: <project-slug-or-empty>
---

# /refresh-dossier <project-slug>

> *"Recompile the standing mental model of this project so every primitive starts with full context."*

Invokes `vaultlab.kb.dossier.compile_dossier` to synthesize a fresh ~2000-3000 word dossier for the given project. The dossier is the answer to *"what does the agent know about this project before doing anything?"* — auto-compiled, source-cited, refreshed daily, loaded as Layer 0 before any non-trivial primitive (per SPEC-N).

If no project-slug is given, infers from `.vaultlab-project.json` in the current working directory.

## What the dossier contains

Nine canonical sections:

1. **Why this project exists (the origin)** — synthesized from `intake.md` + early decisions log
2. **Where we are (current state, last 2 weeks)** — from `START_HERE.md`
3. **Methodology commitments** — from `decisions-log.md`
4. **Established findings (high-confidence)** — from `Wiki/Concepts/` + `Output/Reports/`
5. **Active frontier (open questions, last 30 days)** — from START_HERE open-items + grill docs
6. **Pertinent literature backdrop** — top-30 Tier-A summaries from `Wiki/Summaries/`
7. **Cross-project connections** — find-analogs cache + sibling projects
8. **Anticipated PI / advisor questions** — extracted from prior `expert_reviewer` audit reports
9. **What changed in the last 7 days (rolling tail)** — recent outputs

## Lineage

Lifts:
- **Project dossier concept** from `conceptual-deep-dive-project-context-2026-05-08.md` (own work; SPEC-N)
- **Senior-PI mental-model archetype** — virtual-lab team_lead pattern (Swanson 2025)
- **Source-cited synthesis** — PaperQA2 evidence-grounding discipline
- **Daily-brief convention** — own START_HERE.md spec (`tools/knowledge-base-specification.md`)
- **Cumulative recall** — own corpus_recall + abstract_recall pattern (per CLAUDE.md commitment #6)

## Pre-flight checklist

1. Resolve KB root + project slug
2. Verify `Wiki/Projects/<slug>/` exists (run `/onboard-project` first if not)
3. Check current dossier age via `vaultlab.kb.dossier.dossier_age_hours`
4. If <24h old and `--force` not set, skip recompile + load existing instead
5. State-aware preflight: archive any prior dossier before writing new (auto-handled)

## Execution

### Step 1 — Compile

```python
from vaultlab.kb.dossier import compile_dossier
dossier = compile_dossier(kb_root, project_slug, force=False)
```

This:
- Reads project intake, START_HERE, decisions-log, concepts, summaries, audit reports, grill docs
- Synthesizes 9 sections with source attribution
- Archives any prior dossier to `Wiki/Projects/<slug>/Project-Dossier.archive/<timestamp>.md`
- Writes fresh dossier to `Wiki/Projects/<slug>/Project-Dossier.md`

### Step 2 — Surface

Surface to user:
- Confirmation the dossier is at `<path>`
- Per-section "sources consulted" count
- Any sections that hit the "_no source files yet_" fallback (signals where the project needs more KB content)

### Step 3 — Suggest next reads

If section 6 (literature) returned `_No Wiki/Summaries/ found_`, suggest `/lit-arc <topic>`.
If section 8 (anticipated questions) returned the fallback, suggest running `/expert-reviewer-audit` on the project's most-recent concept doc.
If section 7 (cross-project) returned only sibling list (no analogs cached), suggest `/find-analogs <main-concept>`.

## Auto-trigger conditions (future)

The dossier should auto-refresh on:
- Daily session-start (if last compile > 24h ago)
- New audit-clean concept doc landing in `Wiki/Concepts/`
- New decision logged in `decisions-log.md`
- New `/lit-arc` completion (writes new Tier-A summaries)

These hooks are pending; for now, `/refresh-dossier` is on-demand.

## What this is NOT

- Not a replacement for the underlying source files (decisions-log, START_HERE, concepts) — it's the synthesis on top.
- Not a one-shot summary — refreshed continuously as the project evolves.
- Not aspirational — every claim in the dossier links back to the source file that supports it.

## See also

- `vaultlab/src/vaultlab/kb/dossier.py` — compilation module
- `vaultlab/Sources/Notes/conceptual-deep-dive-project-context-2026-05-08.md` — design doc (SPEC-N)
- `vaultlab/Sources/Notes/spec-roadmap-2026-05-07.md` — roadmap entry
- `tests/test_vaultlab_kb/test_dossier.py` — 17 tests covering compilation, freshness gating, archiving, source attribution
