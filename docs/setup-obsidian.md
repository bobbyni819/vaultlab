# Setting up Obsidian for vaultlab

vaultlab uses [Obsidian](https://obsidian.md) as the recommended (but not required) GUI for browsing your knowledge base. The KB itself is just a folder of markdown files; you can use any markdown editor. Obsidian gives you wikilinks, graph view, plugin support, and a clean local-first experience.

**Total setup time: ~10 minutes.** Cross-platform (Windows / macOS / Linux).

## Step 1: Download Obsidian

1. Go to https://obsidian.md
2. Click the big "Get Obsidian" button — it auto-detects your OS
3. Run the installer

Obsidian is **free for personal and academic use**. You don't need an account. (Obsidian Sync is paid; you don't need it — your KB is already on Google Drive or wherever you put it.)

## Step 2: Open your vaultlab KB as a vault

After installing:

1. Open Obsidian → **"Open folder as vault"**
2. Navigate to your KB root: `G:/My Drive/Knowledge/<your-project-kb>` (or wherever you set it during `vaultlab setup`)
3. Click "Open"

Obsidian creates a `.obsidian/` config folder inside the vault. That's normal and expected.

You should now see a sidebar with `Sources/`, `Wiki/`, `Output/`, and your `_Index.md` + `_Catalog.md` files.

## Step 3: Install the recommended plugins

vaultlab works best with three Obsidian plugins. Install them via Settings → Community plugins.

| Plugin | What it does | Required? |
|---|---|---|
| **Advanced URI** | Lets `vaultlab kb open <path>` open files in new Obsidian tabs (rather than replacing the current tab). | Recommended |
| **Dataview** | Lets you write queries against your KB frontmatter — e.g., *"show me all Findings with status=verified."* | Recommended |
| **Templater** | Lets vaultlab-generated note templates auto-fill frontmatter. | Optional |

To install each:

1. Settings → Community plugins → Turn on community plugins (Obsidian asks once; click "Turn on")
2. Click "Browse"
3. Search for the plugin name → Install → Enable

(Once `vaultlab kb init` lands in v0.1.0, this happens automatically.)

## Step 4: (Optional) Set up new-tab behavior

By default, Obsidian opens links in the current tab. For research workflows, opening in new tabs is much friendlier. After installing the Advanced URI plugin:

1. Settings → Community plugins → Advanced URI → toggle on
2. Now `vaultlab kb open <path>` opens files in new tabs

## Step 5: Verify with vaultlab

```bash
vaultlab kb open <your-project>/START_HERE
```

This should open the START_HERE.md for your project in a new Obsidian tab. If it does, you're set.

## Workspace tips for research project mode

These are personal preferences but they make vaultlab much more usable in research contexts:

### Two-pane layout

Split the workspace: left pane shows the current document (e.g., your manuscript draft); right pane shows the relevant KB note (e.g., the Finding being cited). Right-click a tab → "Split right" to open side-by-side.

### Quick Switcher

`Cmd/Ctrl+O` opens Obsidian's Quick Switcher. Type the first letters of any file in the vault to jump to it. Indispensable when navigating across `Sources/`, `Wiki/`, and `Output/`.

### Graph view

`Cmd/Ctrl+G` (or click the graph icon) opens the graph view — visualizes how KB notes link to each other. Useful for spotting orphan notes (no inbound links) or hub notes (lots of links).

### Daily notes

Settings → Core plugins → Daily notes (turn on). Sets up a simple daily-journal pattern. Pairs well with vaultlab's `/eod` and `/brief` commands.

## Without Obsidian

If you don't want Obsidian, vaultlab still works:

- The KB is just a folder of `.md` files; any markdown editor (VS Code, Typora, plain notepad) renders them
- `vaultlab kb open <path>` falls back to your default editor when Obsidian isn't installed
- You lose: graph view, fast cross-file search, plugin ecosystem, the polished UX

## Multi-vault setup (one Obsidian per KB)

If you have multiple research projects with multiple KBs, you can:

- **Option A** (recommended): One Obsidian app, multiple vaults. Switch between them via Obsidian's vault switcher (top-left corner). Each vault is independent.
- **Option B**: Multiple Obsidian profiles or installs. Heavyweight; only do this if the vaults need different plugin sets.

vaultlab's `vaultlab kb switch <name>` updates which vault is the default for slash commands.

## Troubleshooting

| Issue | Fix |
|---|---|
| `vaultlab kb open` doesn't open Obsidian | Make sure the Advanced URI plugin is installed and enabled. Without it, vaultlab falls back to your default editor. |
| Plugins don't appear in "Browse" | Settings → Community plugins → toggle "Restricted mode" off |
| Graph view is sluggish | Filter the graph (top-right of graph) to focus on a single folder |
| Vault won't open from Drive | Google Drive sometimes locks files mid-sync. Wait for sync to settle, then try again. |

## See also

- [`getting-started.md`](getting-started.md) — first 10 minutes with vaultlab
- [`vaultlab.kb.obsidian` API reference](../src/vaultlab/kb/obsidian.md) — the Python integration
- [Obsidian docs](https://help.obsidian.md/Home) — official documentation
