---
name: link-repo
type: orchestrated
backed_by: vaultlab.context.code.set_linked_repo
purpose: Associate a code repository with the current vaultlab project so the crosstalk meeting machinery can read scripts + data + recent changes for data-driven reasoning
arguments: <path-to-code-repo>
---

# /link-repo <path-to-code-repo>

Link a code repository to the current vaultlab project. Once linked,
vaultlab's data-driven crosstalk meetings (`Mode.DATA_ANALYSIS`) can
include the repo's source files, recent changes, and data artifacts as
context for analyst / critic / synthesizer reasoning.

The linked repo is *separate* from the KB — the KB holds knowledge
artifacts (papers, summaries, transcripts), the linked repo holds
executable artifacts (source code, scripts, data). One linked repo per
project; multi-repo is deferred.

## What this command produces

- Adds a `linked_repo: "<absolute-path>"` field to the project's
  `.vaultlab-project.json`
- Verifies the repo exists and is a directory
- Prints a summary: which files exist, recent commit (if it's a git
  repo), and how to use the link in a follow-up `/deep-think` or
  `/lit-arc` call

## How to execute

You (Claude Code) parse the path argument, check it exists, and call the
backing Python helper. No LLM judgment needed — this is a config write.

### Step 1 — Resolve the path

```python
from pathlib import Path

repo_path = Path("$ARGUMENTS").expanduser().resolve() if "$ARGUMENTS" else None
if repo_path is None:
    print("Usage: /link-repo <path-to-code-repo>")
    raise SystemExit(1)
if not repo_path.exists():
    print(f"Path does not exist: {repo_path}")
    raise SystemExit(1)
if not repo_path.is_dir():
    print(f"Path is not a directory: {repo_path}")
    raise SystemExit(1)
```

### Step 2 — Resolve the project (cwd-side)

```python
from vaultlab.onboarding import load_project_config_from_cwd

project_cfg = load_project_config_from_cwd()
if project_cfg is None or not project_cfg.project_path:
    print(
        "No vaultlab project found in cwd or any parent. Run "
        "/onboard-project first to create one."
    )
    raise SystemExit(1)
project_path = Path(project_cfg.project_path)
```

### Step 3 — Write the link

```python
from vaultlab.context.code import set_linked_repo

stored_path = set_linked_repo(project_path, repo_path)
print(f"Linked repo {stored_path} to project '{project_cfg.slug}'")
```

### Step 4 — Surface a quick summary

```python
from vaultlab.context.code import list_files, list_recent_changes

n_files = len(list_files(stored_path, max_results=10_000))
recent = list_recent_changes(stored_path, limit=5)
print(f"\nRepo summary:")
print(f"  Files (excluding .git/, __pycache__/, etc.): {n_files}")
if recent:
    print(f"  Recent commits:")
    for c in recent:
        print(f"    {c.sha} {c.date}  {c.author}  {c.subject[:60]}")
else:
    print(f"  Not a git repo (or no commits) — recent-changes feature unavailable")
```

### Step 5 — Tell the user how to use the link

Print:

> Linked. The repo is now available to:
> - `/deep-think` (data-analysis mode) — meeting agendas can reference
>   files in this repo via `vaultlab.context.code.read_file`
> - `/lit-arc` — when running on a topic that overlaps with the repo's
>   work, the meeting machinery can pull recent commits and source
>   files into the analyst's context
>
> To verify what's linked, look at `<project_path>/.vaultlab-project.json`
> for the `linked_repo` field.

## When to use this

- A researcher has a simulation codebase or analysis repo and wants the
  meeting machinery to reason over it
- A user is iterating on data-analysis scripts and wants vaultlab to
  surface "what changed since last meeting" as context
- Setting up a new project that's primarily code-driven rather than
  literature-driven

## Notes

- The linked repo path is stored as an absolute path. If the repo
  moves, re-run `/link-repo` to update.
- vaultlab does NOT auto-execute scripts in the linked repo. The user
  (via Claude Code's Bash tool) decides what to run. The linked-repo
  feature is read-side only at v0.1.x.
- One linked repo per project; if you re-run `/link-repo` with a
  different path, it overwrites the previous link.
