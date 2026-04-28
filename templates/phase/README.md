# Template: pipeline phase

To add a new pipeline phase to `/research-pipeline`:

1. Run `vaultlab phase scaffold <phase_name>` (CLI scaffolds the files automatically)
2. Or manually: copy this directory's contents to `src/vaultlab/workflows/<phase>.py + .md` and `.claude/commands/research-<phase>.md`
3. Register in `.claude/commands/research-pipeline.md`
4. Add tests in `tests/test_vaultlab/test_workflows/`

## Phase categories

vaultlab's `/research-pipeline` chains 7 phases by default. New phases typically fit one of these categories:

| Category | Examples |
|---|---|
| Data verification | `verify-data` |
| Reasoning / analysis | `reason`, `synthesize` |
| Figure generation | `figures` |
| Writing | `write` |
| Review / audit | `review`, `cite-watch` |
| Stakeholder gates | `pi-review`, `ethics-check` |

## Required artifacts per phase

```
src/vaultlab/workflows/<phase>.py    # plan + run functions
src/vaultlab/workflows/<phase>.md    # description (frontmatter + prose)
.claude/commands/research-<phase>.md # slash command wrapper
tests/test_vaultlab/test_workflows/test_<phase>.py
```

## See also

- [`../slash_command/`](../slash_command/) — for the slash command itself
- [`../role/`](../role/) — if the phase needs new agent roles
