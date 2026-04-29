# `vaultlab.kb.obsidian`

Obsidian setup automation. Owns vault scaffolding, plugin enable list, note-template installation, deep-link `vaultlab kb open` implementation, and install detection.

## Why this lives in vaultlab (not a separate setup script)

VaultLab's async-first feedback loop (CLAUDE.md commitment 5, AGENTS.md invariant 10) requires `vaultlab kb open <path>` to work the moment a user clones the repo. That means the Obsidian-side configuration ships with VaultLab — the user shouldn't have to piece it together from blog posts.

## Public surface

| Function | What it does |
|---|---|
| `init_vault(kb_path)` | Write `.obsidian/` defaults — app settings, core plugins, workspace |
| `configure_plugins(kb_path)` | Write `community-plugins.json` listing recommended plugin IDs |
| `write_templates(kb_path)` | Install vaultlab note templates (paper, note, concept, START_HERE, decisions log) |
| `open_in_obsidian(rel_path, ...)` | Build + launch an `obsidian://advanced-uri` (or `obsidian://open`) deep link |
| `detect_install()` | Locate Obsidian binary + open vault + plugin state |

## The three recommended community plugins

| Plugin | Why VaultLab needs it |
|---|---|
| **Advanced URI** | Required for new-tab opens. Without it, every `vaultlab kb open` reuses the current pane. |
| **Dataview** | Queryable wikilink graph. `_Index.md` and `_Catalog.md` use Dataview blocks to materialize cross-cutting views. |
| **Templater** | Frontmatter helpers for date stamps + slug generation in note templates. |

These are listed in `community-plugins.json` so they auto-enable on install. The user must install them through the Obsidian Community Plugins browser — Obsidian doesn't allow programmatic download of community plugin code.

## Files in this subpackage

- `init.py` — `init_vault()`
- `plugins.py` — `configure_plugins()`, `RECOMMENDED_PLUGINS`, `install_instructions_markdown()`
- `templates.py` — `write_templates()` and the in-source template strings
- `open.py` — `open_in_obsidian()` (the deep-link launcher)
- `detect.py` — `detect_install()` + `summarize_install()` for `vaultlab kb obsidian-doctor`

## See also

- [`docs/setup-obsidian.md`](../../../docs/setup-obsidian.md) — user-facing walkthrough
- [`vaultlab.kb.start_here`](../start_here.py) — the START_HERE.md auto-update logic that is the primary consumer of `open_in_obsidian()`
- [`vaultlab.kb.feedback`](../feedback.py) — async-first grill / decisions-log writers (built next)
