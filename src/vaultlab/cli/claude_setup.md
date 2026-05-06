# `vaultlab claude-setup`

Wire vaultlab into Claude Code globally so its slash commands and dispatch behavior appear in every session, on every project — not just sessions opened in the vaultlab repo.

## What it does

1. **Copies vaultlab's slash commands** from `<vaultlab-repo>/.claude/commands/*.md` to `~/.claude/commands/`. After this, `/lit-arc`, `/build-deck`, `/cite audit`, `/onboard-me`, `/start-project`, `/lit-report`, `/understand-figure` etc. appear in any Claude Code session, anywhere.
2. **Appends a "## VaultLab" pointer block** to `~/.claude/CLAUDE.md` (creates it if it doesn't exist) citing the absolute path to vaultlab's `READ_FIRST.md`. Future Claude Code sessions read this global CLAUDE.md at startup, see the pointer, and know to consult `READ_FIRST.md` for the dispatch table.

## When to run it

- After `pip install vaultlab` + `vaultlab init` (the recommended bootstrap order)
- After `git pull` on the vaultlab repo (refreshes any updated slash commands)
- Any time a new vaultlab slash command lands and you want it globally available

## Idempotent

Safe to re-run. If the CLAUDE.md block is already present, it's not duplicated. Slash command files are overwritten with the latest version on each run.

## Usage

```bash
# Standard
vaultlab claude-setup

# Preview without writing files
vaultlab claude-setup --dry-run
```

## What if pure PyPI install (no repo on disk)?

Slash command copy is skipped (no source available), but the CLAUDE.md pointer block is still written referencing the GitHub URL. To get the slash commands too:

```bash
git clone https://github.com/bobbyni819/vaultlab
pip install -e ./vaultlab    # editable install
vaultlab claude-setup        # now finds the .claude/commands/
```

## Relation to bootstrap scripts

`scripts/bootstrap.ps1` and `scripts/bootstrap.sh` will call `vaultlab claude-setup` as their last step, so users running the bootstrap don't need to invoke it separately.

## What this closes

Friction point that was hit by every fresh user before this command existed: open Claude Code in your project, ask for a literature search, and Claude has no idea vaultlab exists. Now: open Claude Code anywhere, ask for a literature search, and `/lit-arc` is right there.
