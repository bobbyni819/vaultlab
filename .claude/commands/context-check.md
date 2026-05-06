---
name: context-check
description: Print what KB context the harness would load for a sub-agent in this project. Verify the agent has the right context BEFORE running an expensive orchestrator.
arguments: [optional-project-slug]
---

# /context-check [project-slug]

> Verify the harness's KB-context preamble before running an expensive orchestrator. Closes CLAUDE.md commitment #7 — the context-preservation invariant.

Reports what `vaultlab.runner.kb_context.compose_preamble()` would return for the current project (or specified slug). Useful when:

- A new lab member is testing vaultlab and wants to see what context Claude actually inherits
- An orchestrator (e.g., `/next-analysis`, `/debug`) is producing weird output and you suspect it's running with stale or missing context
- Before invoking expensive multi-agent rounds where the context preamble matters most

## Execution

```python
from vaultlab.runner.kb_context import compose_preamble, KbStateUnreadable

# If user gave a slug, use it; else infer from .vaultlab-project.json
project_slug = argv[0] if argv else _infer_from_cwd()

try:
    bundle = compose_preamble(project_slug, return_bundle=True)
except KbStateUnreadable as e:
    print(f"❌ KB state unreadable: {e}")
    print(f"   Cannot proceed with any sub-agent invocation in this project.")
    print(f"   Fix: run /onboard-me or /start-project first.")
    return 1
```

## Output

Format the bundle to a human-readable summary:

```
✅ KB context for project: <slug>
   KB root: <kb_root>
   Token estimate: <N> (budget: 4000)
   Truncated: <Yes/No>

✅ START_HERE.md loaded (<X> chars)
   First line: <first non-empty line>

<🟡 / ❌ depending> decisions-log.md
   <If present:> last 30 days has <N> entries; date range <start> .. <end>
   <If empty:> no decisions logged in the last 30 days

✅ Tier-A summaries loaded (<N>)
   <For each:>
   - <doi-slug>
     <first 80 chars of body>

<🟡 / ❌> Recent Output/*.md
   <For each:>
   - <filename> (mtime: <date>)
     <first 80 chars>

📜 Full preamble length: ~<token_estimate> tokens
   Run /context-check --full to print the entire preamble verbatim.
```

When `--full` flag is given, also print the full preamble string verbatim (useful for debugging).

## When to invoke

- Before any expensive multi-agent round (e.g., `/next-analysis` on a fresh project)
- When an orchestrator's output looks wrong and you want to verify the context it had
- New-user onboarding diagnostic

## When NOT to invoke

- Mid-session, after an orchestrator just ran cleanly — context is fine
- For one-shot LLM calls (no sub-agents → no preamble → nothing to check)

## Lineage

The slash command itself follows gstack's pattern of "expose a diagnostic for any complex internal state." The underlying `compose_preamble()` lifts virtual-lab's team_lead-distributes-shared-context pattern; this command is the inspector for it.
