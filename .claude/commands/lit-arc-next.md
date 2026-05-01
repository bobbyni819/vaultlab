---
name: lit-arc-next
type: orchestrated
backed_by: vaultlab.research.next_topic.propose_next_topics
purpose: Propose 3-5 next-best lineage-arc topics by reading the project's prior decisions log + open questions
arguments: [--project SLUG] [--n 5]
---

# /lit-arc-next [--project SLUG] [--n 5]

Reads the current project's `decisions-log.md` and prior arcs' "open
questions" sections, then asks YOU (Claude Code, as the LLM) to
propose the next-best topics to run `/lit-arc` on.

## When to use

After you've used vaultlab for a while and the project's KB has
accumulated several lineage arcs, this command saves you from inventing
the next topic from scratch. Inputs are entirely KB-side — no API
calls, no search, just reading what you've already built.

## What this command produces

A ranked list of 3-5 next-best topic proposals printed to the console
(or pasted into the project's decisions-log if `--log`). Each proposal
includes:

- The topic string (passable directly to `/lit-arc`)
- 1-3 sentence rationale grounded in prior runs / open questions
- Which prior topics it builds on
- Which open question (if any) it directly addresses
- A priority rank (1 = strongest pick)

You then pick one and run `/lit-arc <chosen-topic>`.

## How to execute

### Step 1 — Parse args

```python
import shlex
raw_args = shlex.split("$ARGUMENTS") if "$ARGUMENTS" else []
project_slug_arg: str = ""
target_n: int = 5
i = 0
while i < len(raw_args):
    tok = raw_args[i]
    if tok == "--project" and i + 1 < len(raw_args):
        project_slug_arg = raw_args[i + 1]; i += 2
    elif tok == "--n" and i + 1 < len(raw_args):
        target_n = int(raw_args[i + 1]); i += 2
    else:
        i += 1
```

### Step 2 — Resolve project + KB root

```python
from pathlib import Path
from vaultlab.context import resolve_kb_root, KbRootNotConfigured
from vaultlab.onboarding import load_project_config_from_cwd

try:
    kb_root = resolve_kb_root()
except KbRootNotConfigured as exc:
    print(f"No KB configured. Run `vaultlab init`.")
    raise SystemExit(1)

project_cfg = load_project_config_from_cwd()
project_slug = project_slug_arg
if not project_slug and project_cfg is not None and project_cfg.slug:
    project_slug = project_cfg.slug
if not project_slug:
    print("No --project flag and no .vaultlab-project.json in cwd. "
          "Run /onboard-project first or pass --project <slug>.")
    raise SystemExit(1)
```

### Step 3 — Build the task (no LLM yet)

```python
from vaultlab.research.next_topic import prepare_next_topic_task

task = prepare_next_topic_task(
    kb_root=kb_root,
    project_slug=project_slug,
    target_n=target_n,
)
```

### Step 4 — Run the LLM step (YOU)

The task carries `system`, `prompt`, and `response_schema`. Read the
prompt — it lists the prior topics + open questions extracted from the
KB. Produce a JSON response matching `task.response_schema`:

```json
{
  "proposals": [
    {
      "topic": "<topic string>",
      "rationale": "<grounded reason>",
      "builds_on": ["<prior topic>", ...],
      "addresses_question": "<text or empty>"
    },
    ...
  ]
}
```

Rules for good proposals:
- Build on what's in `task.prior_topics` and `task.open_questions`
- Don't propose duplicates of prior topics (or trivial reframings)
- Rank strongest pick first (response order = rank)

### Step 5 — Render + print

```python
from vaultlab.research.next_topic import render_topics_from_response

response = {"proposals": [...]}  # YOUR JSON from step 4
proposals = render_topics_from_response(response, task)

if not proposals:
    print(f"No next-topic proposals returned for project {project_slug!r}.")
    raise SystemExit(0)

print(f"\nNext-best topics for project '{project_slug}':\n")
for p in proposals:
    print(f"  {p.priority_rank}. {p.topic}")
    print(f"     Rationale: {p.rationale}")
    if p.builds_on:
        print(f"     Builds on: {', '.join(p.builds_on)}")
    if p.addresses_question:
        snippet = p.addresses_question[:80]
        print(f"     Addresses: {snippet}...")
    print()

print(f"To run a chosen topic: /lit-arc \"<topic>\"")
```

## When the project has no prior runs

The task's prompt explicitly notes "this would be the project's first
lit-arc" and asks you to propose based on the project's intake (topic +
goals + audience) instead. In that case, prior_topics will be empty
and the proposals should anchor on the intake's stated topic.

## Limitations

- Only reads decisions-log entries with the standard
  ``## YYYY-MM-DDTHH:MM:SS — lit-arc run`` heading. Custom entries are
  skipped.
- "Open questions" section extraction looks for headings:
  ``## Open questions`` / ``## Limitations & future directions`` /
  ``## Future directions``. Default SHORT-scope arcs don't have those
  sections, so the open-questions input will be empty for SHORT-only
  projects (they only get the prior-topics signal).
- Doesn't currently cross-reference vaultlab papers manifests or the
  citation graph — a v0.2 candidate to make proposals smarter.
