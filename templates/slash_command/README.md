# Template: slash command

To add a new slash command to vaultlab:

1. Copy `command.md` to `.claude/commands/<command-name>.md`
2. Fill in: description, inputs, outputs, implementation, test plan
3. Run `vaultlab claude validate`
4. Smoke-test by invoking in Claude Code on a tiny test project

## Slash command type

Pick one (per AGENTS.md Invariant 9):

- **Pure capability** — single-purpose; calls one capability subpackage. Examples: `/lit-search`, `/figure-gen`.
- **Orchestrated** — multi-agent meeting or plan-execute-verify-refine loop. Examples: `/research-pipeline`, `/build-deck`.

## `command.md` template

```markdown
---
name: <slash-command-name>
type: pure-capability | orchestrated
backed_by: vaultlab.<package>.<function>
---

# /<slash-command-name>

<One-paragraph description>

## Inputs

- `<arg1>`: <type> — <description>
- `<arg2>` (optional): <type> — <description>

## Outputs

- <where outputs land in KB / Output/>

## Implementation

```python
from vaultlab.<package> import <function>

result = <function>(<args>)
# ... what claude code does with the result
```

## Test plan

- [ ] Smoke test: invoke on demo project; verify outputs exist
- [ ] Verify slash command shows up in `vaultlab claude validate --list`
```
