---
name: onboard-project
type: orchestrated
backed_by: vaultlab.onboarding.init_project_from_intake
purpose: Walk vaultlab through a new project so it knows what's there + what to read first
arguments: [path-to-project-folder]
---

# /onboard-project [path]

Onboards a new project into vaultlab so future commands (`/lit-arc`,
`/build-deck`, `/cite audit`, etc.) know the context. The fast path: the
user fills out `project_intake.md` (5 minutes), then runs this command.
The Python side scans the folder, writes the project view, and you (the
slash command) ask 3-5 follow-up questions for any gaps.

## Inputs

- `path` (optional): project root directory. Defaults to current working
  directory.
- `--slug <slug>`: explicit project slug (default: derived from intake topic)

## How to execute

The Python orchestrator does the deterministic work. YOU (Claude Code)
do the conversational fill + the follow-up questions.

### Step 1 — Resolve the project path

```python
from pathlib import Path

project_path = Path("$ARGUMENTS").expanduser().resolve() if "$ARGUMENTS" else Path.cwd()
```

If `$ARGUMENTS` is empty, default to `Path.cwd()`. If the resolved path
doesn't exist, ask the user where the project lives.

### Step 2 — Check for `project_intake.md`

```python
intake_path = project_path / "project_intake.md"
```

**If `intake_path` exists:** skip to Step 3.

**If it doesn't exist:** offer the user two paths:

> I don't see a `project_intake.md` in this folder. Two options:
>
> **Option A — Quick interactive fill (~3 min).** I'll ask you the
> 9 intake questions one at a time and save your answers as
> `project_intake.md` in this folder.
>
> **Option B — You fill it yourself.** I'll drop a blank template at
> `<path>/project_intake.md` for you to fill in your editor, and you
> re-run `/onboard-project` when done.

If the user picks **A**: walk through the 9 sections in order
(topic, goal, audience, what-they-have, exclusions, style, PI prefs,
deadlines, free-form). After each answer, build up an `IntakeForm` in
memory. When all 9 are answered, write it:

```python
from vaultlab.onboarding import IntakeForm

form = IntakeForm(
    topic=...,
    goals=[...],         # snake_case keys: understand_literature, build_journal_club_deck, etc.
    audiences=[...],     # self, lab_members, pi, journal_club, conference, ...
    have=[...],          # pdfs, notes, wet_lab_data, prior_drafts, citations_file, nothing
    exclusions={...},    # exclude_preprints: bool, min_year: int, english_only: bool
    style=[...],         # hedged, direct, match_papers, match_prior_writing, no_preference
    pi_preferences="...",
    deadlines=[...],     # one_shot, weekly, specific_date
    free_form="...",
)
intake_path.write_text(form.to_markdown(), encoding="utf-8")
```

If the user picks **B**:

```python
from vaultlab.onboarding import copy_intake_template_to
copy_intake_template_to(project_path)
```

Then print: `Template at <path>. Fill it in and re-run /onboard-project.`
and stop.

### Step 3 — Run the orchestrator

```python
from vaultlab.context import resolve_kb_root, KbRootNotConfigured
from vaultlab.onboarding import init_project_from_intake

# Multi-tenant KB-root resolution (Layer A, 2026-04-30): resolver walks
# env-var -> vaultlab config -> bobby_kb compat -> first-run prompt.
# Bobby's existing bobby_kb config keeps working invisibly. New users
# (including this very command, on a fresh laptop) land on the first-run
# prompt exactly once and the choice is persisted to locations.toml.
try:
    kb_root = resolve_kb_root()
except KbRootNotConfigured as exc:
    print(f"No KB configured. Run `vaultlab init` (default: {exc.suggested_default}).")
    raise SystemExit(1)

result = init_project_from_intake(
    intake_path=intake_path,
    kb_root=kb_root,
    project_path=project_path,
)
```

If `resolve_kb_root` raises (non-interactive shell with no config),
stop and point the user at `vaultlab init`. Users with multiple KBs
(research / dcp / tools) can pick one for the session by setting
`$VAULTLAB_KB_ROOT`.

### Step 4 — Ask the follow-up questions

`result.follow_up_questions` is a list of 3-5 specific gaps. Ask them
one at a time in chat. After each answer, log it as a decision:

```python
from vaultlab.kb.feedback import log_decision

log_decision(
    kb_path=kb_root,
    project_slug=result.slug,
    decision=user_answer,
    why=f"Answered onboarding follow-up: {question}",
)
```

If the answer changes any structured field (e.g. user gave a data path),
update `result.config` and re-save:

```python
from vaultlab.onboarding import save_config
result.config.data_dirs.append(user_provided_path)
save_config(result.config, project_path)
```

### Step 5 — Print the summary + open command

```
Project onboarded: <slug>

Files written:
  - <kb>/Wiki/Projects/<slug>/START_HERE.md
  - <kb>/Wiki/Projects/<slug>/intake.md
  - <kb>/Wiki/Projects/<slug>/decisions-log.md
  - <project>/.vaultlab-project.json

What I learned:
  Topic: <topic>
  Goals: <comma-separated goals>
  Audience: <comma-separated>
  Folder: <total_files> files (<top categories>)

Next steps:
  - /lit-arc "<topic>"        — build the literature lineage arc
  - /build-deck "<topic>"     — compose a deck from your KB (v0.1.0)
  - /cite audit               — verify citations in any draft

To open: bobby-kb open vaultlab/Wiki/Projects/<slug>/START_HERE
```

## Anti-laziness rules (per AGENTS.md)

When asking follow-ups:

1. Quote specific filenames from `result.inventory.samples` so the user
   knows you actually read the folder.
2. If the user's answer is ambiguous, mark it `[unconfirmed]` rather
   than guessing.
3. Don't fabricate data dirs — only list paths from `result.inventory`
   or paths the user explicitly typed.
4. The follow-up loop is capped at 5 questions. Stop after 5 even if
   gaps remain — log them as open questions in `decisions-log.md`.

## Test plan

- [ ] Trial dry-run: `python scripts/_trial_onboarding.py`
- [ ] Run on `~/Downloads/CODEX_MALDIIMS/` with a hand-filled intake —
   should produce a START_HERE that lists the wet-lab data dirs
- [ ] Run on a folder without `project_intake.md` — should offer the
   interactive fill OR template-drop choice
- [ ] Run twice on the same folder — second run should refresh
   `last_updated` in `.vaultlab-project.json` without losing data

## Related commands

- `/start-project "<topic>"` — faster path for users without an existing
  folder yet (no folder-walk, no intake)
- `/lit-arc <topic>` — once a project is onboarded, the lit-arc lineage
  arc is the canonical next step
- `/research-status` — quick status of an onboarded project
