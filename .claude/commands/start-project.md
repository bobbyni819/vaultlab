---
name: start-project
type: orchestrated
backed_by: vaultlab.onboarding
purpose: Bootstrap a minimal project scaffold for a topic — no folder-walk, no intake required
arguments: <topic>
---

# /start-project "<topic>"

The fastest path into vaultlab. For users who don't have a project
folder yet — they just want to scope a topic and run `/lit-arc` on it.

This command is the lightweight sibling of `/onboard-project`:
- `/onboard-project` = full onboarding for an existing project folder
  (scans files, fills a `.vaultlab-project.json`, asks 3-5 follow-ups)
- `/start-project` = minimal scaffold for a fresh topic (~30 seconds,
  no questions)

## Inputs

- `<topic>`: required. The topic in plain English. Used to derive the
  slug and seed the intake form.

## How to execute

### Step 1 — Resolve the KB root

```python
from pathlib import Path
from vaultlab.context import resolve_kb_root, KbRootNotConfigured

# Multi-tenant KB-root resolution (Layer A, 2026-04-30): walks env-var ->
# vaultlab config -> bobby_kb compat -> first-run prompt.
try:
    kb_root = resolve_kb_root()
except KbRootNotConfigured as exc:
    print(f"No KB configured. Run `vaultlab init` (default: {exc.suggested_default}).")
    raise SystemExit(1)
```

If `resolve_kb_root` raises, point the user at `vaultlab init` and stop.
Otherwise proceed.

### Step 2 — Build a minimal IntakeForm

```python
from vaultlab.onboarding import IntakeForm
from vaultlab.kb.paths import slugify_topic

topic = "$ARGUMENTS"  # full quoted topic
slug = slugify_topic(topic)

form = IntakeForm(
    topic=topic,
    goals=["understand_literature"],   # default — most /start-project users want lit context
    audiences=["self"],                 # default — they're scoping for themselves
)
```

The `goals` and `audiences` defaults are deliberate: a user running
`/start-project` is almost always exploring a topic for personal
context (scoping). They can edit the intake later with
`/onboard-project` if they want richer onboarding.

### Step 3 — Write the project scaffold

`/start-project` doesn't have a project folder, so we skip
`init_project_from_intake` and write the KB-side files directly:

```python
from vaultlab.kb.paths import (
    ensure_parent,
    project_intake_path,
    project_state_path,
    project_decisions_path,
)
from datetime import datetime

now = datetime.now().strftime("%Y-%m-%d %H:%M")

# 1. Save the (mostly-empty) intake
intake_p = ensure_parent(project_intake_path(kb_root, slug))
intake_p.write_text(form.to_markdown(), encoding="utf-8")

# 2. Minimal START_HERE
sh_p = ensure_parent(project_state_path(kb_root, slug))
sh_p.write_text(f"""---
slug: {slug}
schema: vaultlab-start-here/v1
last_updated: {now}
managed_by: vaultlab.onboarding (start-project)
version: 1
---

# START_HERE — {slug}

> **What this is.** vaultlab maintains this file automatically.
> Created via `/start-project` on {now}.

## Topic

{topic}

## Status

Just-scoped. No folder, no data yet — this is a topic-only scaffold.

## Next steps

- `/lit-arc "{topic}"` — build the literature lineage arc
- `/onboard-project <path>` — when you have a project folder ready,
  upgrade to full onboarding

## Recent activity

- **{now}** — Project scoped via `/start-project`
""", encoding="utf-8")

# 3. Decisions log seed
dec_p = ensure_parent(project_decisions_path(kb_root, slug))
dec_p.write_text(f"""# Decisions log — {slug}

## {now} — Project scoped via /start-project

- **Topic:** {topic}
- **Mode:** quick scope (no folder, no intake-fill)
- **Why:** User wanted to start exploring the topic immediately. Use
  `/onboard-project` later for full onboarding.
""", encoding="utf-8")
```

### Step 4 — Print the summary

```
Project scoped: <slug>

Files written:
  - <kb>/Wiki/Projects/<slug>/START_HERE.md
  - <kb>/Wiki/Projects/<slug>/intake.md
  - <kb>/Wiki/Projects/<slug>/decisions-log.md

Next steps:
  - /lit-arc "<topic>"          — build the literature lineage arc
  - /onboard-project <path>     — upgrade to full project onboarding when ready

To open: bobby-kb open vaultlab/Wiki/Projects/<slug>/START_HERE
```

## When to use which

| Situation | Command |
|---|---|
| "I have a folder with code/data/papers, help me onboard it" | `/onboard-project <path>` |
| "I just want to explore topic X" | `/start-project "X"` |
| "Non-research use case (personal finance, marathon training, etc.)" | `/start-project "..."` works fine — vaultlab is generic |

## Test plan

- [ ] Run on a fresh KB with topic `"galectin-4 sulfatide binding"` —
   should produce 3 files under `Wiki/Projects/galectin-4-sulfatide-binding/`
- [ ] Re-running with the same topic should refresh `last_updated`
   without losing prior content
- [ ] Verify the resulting scaffold is enough to run `/lit-arc` next

## Related commands

- `/onboard-project [path]` — full onboarding when you have a folder
- `/lit-arc <topic>` — natural next step after `/start-project`
