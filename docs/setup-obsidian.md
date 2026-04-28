# Setting up Obsidian for vaultlab

> **Status:** stub. Will be populated as part of `vaultlab.kb.obsidian/` migration.

vaultlab uses [Obsidian](https://obsidian.md) as the recommended (but not required) GUI for browsing your knowledge base. The KB itself is just a folder of markdown files; you can use any markdown editor.

## Required

- **Obsidian Desktop** — free download from obsidian.md
- **Advanced URI plugin** — for `vaultlab kb open` deep links
- **Dataview plugin** — for queryable wikilinks in KB notes
- **Templater plugin** — for vaultlab-generated note templates

## Walkthrough (planned)

1. Install Obsidian Desktop
2. Run `vaultlab kb init` — creates the vault folder + plugin config
3. Open Obsidian → Open vault as folder → point at the vault directory
4. Plugins auto-configured by `vaultlab kb init`; just toggle them on
5. Test with `vaultlab kb open START_HERE`

## Without Obsidian

vaultlab works without Obsidian. The KB is just a folder of `.md` files; any editor renders them. `vaultlab kb open <path>` falls back to your default text editor when Obsidian isn't installed.

## Coming in this doc

- Screenshots of vault initialization
- Plugin settings explanations
- Vault hopper / Quick Switcher tips for vaultlab-specific use
- Workspace layout for "research project mode"
