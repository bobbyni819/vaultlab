# Slash commands

This directory holds vaultlab's slash command definitions. Each `.md` file is a slash command Claude Code can invoke.

> **Status:** scaffold. Slash commands will be migrated from `bobby-tools/.claude/commands/` and adapted to the vaultlab namespace in upcoming migration commits.

## Structure

Each slash command is a markdown file with frontmatter:

```markdown
---
name: <command-name>
type: pure-capability | orchestrated
backed_by: vaultlab.<package>.<function>
---

# /<command-name>

<description, inputs, outputs, implementation>
```

## v0.1 inventory (planned)

See the master plan (file 10 Q10.2 in the architecture grill) for the full list of ~30 slash commands.

## Adding a slash command

1. Copy [`../../templates/slash_command/`](../../templates/slash_command/)
2. Fill in the template
3. Run `vaultlab claude validate`
4. Add the file to this directory
